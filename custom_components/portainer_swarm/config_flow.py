"""Config flow for Portainer Swarm Monitor."""

from __future__ import annotations

import hashlib
from typing import Any, override
from urllib.parse import urlsplit, urlunsplit

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import (
    PortainerAuthenticationError,
    PortainerClient,
    PortainerConnectionError,
    PortainerError,
)
from .const import (
    CONF_ENDPOINT_ID,
    CONF_ENDPOINT_NAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_API_TOKEN): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=30, max=900)
        ),
    }
)


def _normalise_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if (
        parts.scheme.lower() not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Invalid Portainer URL")
    return urlunsplit((parts.scheme.lower(), parts.netloc, parts.path.rstrip("/"), "", ""))


class PortainerSwarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a Portainer Swarm endpoint."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the polling options flow."""
        return PortainerSwarmOptionsFlow()

    def __init__(self) -> None:
        self._connection_data: dict[str, Any] = {}
        self._endpoints: dict[str, dict[str, Any]] = {}
        self._client: PortainerClient | None = None

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            try:
                data[CONF_URL] = _normalise_url(data[CONF_URL])
            except ValueError:
                errors["base"] = "invalid_url"
            else:
                client = PortainerClient(
                    async_get_clientsession(self.hass),
                    data[CONF_URL],
                    data[CONF_API_TOKEN],
                    data[CONF_VERIFY_SSL],
                )
                try:
                    endpoints = await client.async_get_endpoints()
                except PortainerAuthenticationError:
                    errors["base"] = "invalid_auth"
                except PortainerConnectionError:
                    errors["base"] = "cannot_connect"
                except PortainerError:
                    errors["base"] = "unknown"
                else:
                    active_endpoints = {str(endpoint["Id"]): endpoint for endpoint in endpoints}
                    if not active_endpoints:
                        errors["base"] = "no_swarm_endpoints"
                    else:
                        self._connection_data = data
                        self._endpoints = active_endpoints
                        self._client = client
                        return await self.async_step_endpoint()
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_endpoint(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            endpoint_id = str(user_input[CONF_ENDPOINT_ID])
            endpoint = self._endpoints[endpoint_id]
            assert self._client is not None
            try:
                is_swarm = await self._client.async_validate_swarm_endpoint(int(endpoint_id))
            except PortainerAuthenticationError:
                errors["base"] = "invalid_auth"
            except PortainerConnectionError:
                errors["base"] = "cannot_connect"
            except PortainerError:
                errors["base"] = "unknown"
            else:
                if not is_swarm:
                    errors["base"] = "not_swarm_endpoint"
                else:
                    instance_id = (
                        self._client.instance_id
                        or hashlib.sha256(self._connection_data[CONF_URL].encode()).hexdigest()[:16]
                    )
                    await self.async_set_unique_id(f"{instance_id}#{endpoint_id}")
                    self._abort_if_unique_id_configured()
                    scan_interval = self._connection_data.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    )
                    connection_data = {
                        key: value
                        for key, value in self._connection_data.items()
                        if key != CONF_SCAN_INTERVAL
                    }
                    return self.async_create_entry(
                        title=str(endpoint.get("Name") or f"Endpoint {endpoint_id}"),
                        data={
                            **connection_data,
                            CONF_ENDPOINT_ID: int(endpoint_id),
                            CONF_ENDPOINT_NAME: str(
                                endpoint.get("Name") or f"Endpoint {endpoint_id}"
                            ),
                        },
                        options={CONF_SCAN_INTERVAL: scan_interval},
                    )
        choices = {key: str(value.get("Name") or key) for key, value in self._endpoints.items()}
        return self.async_show_form(
            step_id="endpoint",
            data_schema=vol.Schema({vol.Required(CONF_ENDPOINT_ID): vol.In(choices)}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data):
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Validate and store a replacement API token."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            client = PortainerClient(
                async_get_clientsession(self.hass),
                entry.data[CONF_URL],
                user_input[CONF_API_TOKEN],
                entry.data[CONF_VERIFY_SSL],
            )
            try:
                endpoints = await client.async_get_endpoints()
            except PortainerAuthenticationError:
                errors["base"] = "invalid_auth"
            except PortainerConnectionError:
                errors["base"] = "cannot_connect"
            except PortainerError:
                errors["base"] = "unknown"
            else:
                if any(
                    endpoint.get("Id") == entry.data[CONF_ENDPOINT_ID] for endpoint in endpoints
                ):
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                    )
                errors["base"] = "no_swarm_endpoints"
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Update Portainer connection settings."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            try:
                data[CONF_URL] = _normalise_url(data[CONF_URL])
            except ValueError:
                errors["base"] = "invalid_url"
            else:
                client = PortainerClient(
                    async_get_clientsession(self.hass),
                    data[CONF_URL],
                    data[CONF_API_TOKEN],
                    data[CONF_VERIFY_SSL],
                )
                try:
                    endpoints = await client.async_get_endpoints()
                    endpoint = next(
                        (
                            item
                            for item in endpoints
                            if item.get("Id") == entry.data[CONF_ENDPOINT_ID]
                        ),
                        None,
                    )
                    is_swarm = endpoint is not None and await client.async_validate_swarm_endpoint(
                        entry.data[CONF_ENDPOINT_ID]
                    )
                except PortainerAuthenticationError:
                    errors["base"] = "invalid_auth"
                except PortainerConnectionError:
                    errors["base"] = "cannot_connect"
                except PortainerError:
                    errors["base"] = "unknown"
                else:
                    if not is_swarm:
                        errors["base"] = "not_swarm_endpoint"
                    else:
                        assert endpoint is not None
                        instance_id = (
                            client.instance_id
                            or hashlib.sha256(data[CONF_URL].encode()).hexdigest()[:16]
                        )
                        new_unique_id = f"{instance_id}#{entry.data[CONF_ENDPOINT_ID]}"
                        if any(
                            candidate.entry_id != entry.entry_id
                            and candidate.unique_id == new_unique_id
                            for candidate in self.hass.config_entries.async_entries(DOMAIN)
                        ):
                            return self.async_abort(reason="already_configured")
                        return self.async_update_reload_and_abort(
                            entry,
                            unique_id=new_unique_id,
                            data_updates={
                                CONF_URL: data[CONF_URL],
                                CONF_API_TOKEN: data[CONF_API_TOKEN],
                                CONF_VERIFY_SSL: data[CONF_VERIFY_SSL],
                                CONF_ENDPOINT_NAME: str(
                                    endpoint.get("Name") or entry.data[CONF_ENDPOINT_NAME]
                                ),
                            },
                        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=entry.data[CONF_URL]): str,
                    vol.Required(CONF_API_TOKEN, default=entry.data[CONF_API_TOKEN]): str,
                    vol.Required(CONF_VERIFY_SSL, default=entry.data[CONF_VERIFY_SSL]): bool,
                }
            ),
            errors=errors,
        )


class PortainerSwarmOptionsFlow(config_entries.OptionsFlowWithReload):
    """Configure behavioral options."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=30, max=900)
                    )
                }
            ),
        )
