"""Minimal read-only Portainer API client."""

from __future__ import annotations

from typing import Any

import aiohttp


class PortainerError(Exception):
    """Base Portainer client error."""


class PortainerAuthenticationError(PortainerError):
    """The Portainer token was rejected."""


class PortainerConnectionError(PortainerError):
    """Portainer could not be reached."""


class PortainerResponseError(PortainerError):
    """Portainer returned an unexpected response."""


class PortainerClient:
    """Read-only client for the subset of Portainer used by this integration."""

    def __init__(
        self, session: aiohttp.ClientSession, base_url: str, api_token: str, verify_ssl: bool
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._verify_ssl = verify_ssl
        self._portainer_version: str | None = None
        self._instance_id: str | None = None

    @property
    def instance_id(self) -> str | None:
        """Return Portainer's non-sensitive instance identifier."""
        return self._instance_id

    def __repr__(self) -> str:
        return f"PortainerClient(base_url={self._base_url!r}, verify_ssl={self._verify_ssl!r})"

    async def _get(self, path: str) -> Any:
        try:
            async with self._session.get(
                f"{self._base_url}{path}",
                headers={"X-API-Key": self._api_token},
                ssl=self._verify_ssl,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                if response.status in (401, 403):
                    raise PortainerAuthenticationError("Portainer authentication failed")
                if response.status != 200:
                    raise PortainerResponseError(f"Portainer returned HTTP {response.status}")
                try:
                    return await response.json()
                except (TypeError, ValueError) as err:
                    raise PortainerResponseError("Portainer returned malformed JSON") from err
        except PortainerError:
            raise
        except (aiohttp.ClientError, OSError, TimeoutError) as err:
            raise PortainerConnectionError("Unable to connect to Portainer") from err

    async def async_get_endpoints(self) -> list[dict[str, Any]]:
        """Validate authentication and list available Portainer endpoints."""
        status = self._expect_dict(await self._get("/api/status"), "status")
        self._portainer_version = status.get("Version")
        self._instance_id = status.get("InstanceID")
        endpoints = self._expect_list(await self._get("/api/endpoints"), "endpoints")
        valid: list[dict[str, Any]] = []
        for endpoint in endpoints:
            if "Id" not in endpoint:
                raise PortainerResponseError("Portainer returned a malformed endpoint")
            if endpoint.get("Status") == 1:
                valid.append(endpoint)
        return valid

    async def async_validate_swarm_endpoint(self, endpoint_id: int) -> bool:
        """Return whether an endpoint exposes a Swarm manager API."""
        info = self._expect_dict(
            await self._get(f"/api/endpoints/{endpoint_id}/docker/info"), "Docker info"
        )
        swarm = info.get("Swarm")
        return bool(
            isinstance(swarm, dict)
            and swarm.get("LocalNodeState") == "active"
            and swarm.get("ControlAvailable") is True
        )

    async def async_get_snapshot(self, endpoint_id: int) -> dict[str, Any]:
        """Fetch a current read-only Swarm snapshot."""
        if self._portainer_version is None:
            status = self._expect_dict(await self._get("/api/status"), "status")
            self._portainer_version = status.get("Version")
            self._instance_id = status.get("InstanceID")
        prefix = f"/api/endpoints/{endpoint_id}/docker"
        info = self._expect_dict(await self._get(f"{prefix}/info"), "Docker info")
        nodes = self._expect_list(await self._get(f"{prefix}/nodes"), "nodes")
        services = self._expect_list(await self._get(f"{prefix}/services?status=true"), "services")
        tasks = self._expect_list(await self._get(f"{prefix}/tasks"), "tasks")
        stacks = self._expect_list(
            await self._get(f"/api/stacks?endpointId={endpoint_id}"), "stacks"
        )
        containers = self._expect_list(
            await self._get(f"{prefix}/containers/json?all=1"), "containers"
        )
        return {
            "portainer_version": self._portainer_version,
            "info": info,
            "nodes": nodes,
            "services": services,
            "tasks": tasks,
            "stacks": stacks,
            "containers": containers,
        }

    @staticmethod
    def _expect_dict(value: Any, resource: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise PortainerResponseError(f"Portainer returned malformed {resource} data")
        return value

    @staticmethod
    def _expect_list(value: Any, resource: str) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise PortainerResponseError(f"Portainer returned malformed {resource} data")
        return value
