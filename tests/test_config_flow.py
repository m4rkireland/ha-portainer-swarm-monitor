import hashlib
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portainer_swarm.const import (
    CONF_ENDPOINT_ID,
    CONF_ENDPOINT_NAME,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)


async def test_user_flow_selects_swarm_endpoint(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.portainer_swarm.config_flow.PortainerClient.async_get_endpoints",
        AsyncMock(return_value=[{"Id": 1, "Name": "primary", "Type": 2, "Status": 1}]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://portainer.example/",
                CONF_API_TOKEN: "token",
                CONF_VERIFY_SSL: True,
                CONF_SCAN_INTERVAL: 120,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "endpoint"

    with (
        patch(
            "custom_components.portainer_swarm.async_setup_entry",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.portainer_swarm.config_flow.PortainerClient.async_validate_swarm_endpoint",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENDPOINT_ID: "1"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "primary"
    assert result["data"] == {
        CONF_URL: "https://portainer.example",
        CONF_API_TOKEN: "token",
        CONF_VERIFY_SSL: True,
        CONF_ENDPOINT_ID: 1,
        CONF_ENDPOINT_NAME: "primary",
    }
    assert result["options"] == {CONF_SCAN_INTERVAL: 120}
    assert "portainer.example" not in result["result"].unique_id


async def test_user_flow_rejects_non_swarm_endpoint(hass) -> None:
    with patch(
        "custom_components.portainer_swarm.config_flow.PortainerClient.async_get_endpoints",
        AsyncMock(return_value=[{"Id": 2, "Name": "standalone", "Type": 2, "Status": 1}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_URL: "https://portainer.example",
                CONF_API_TOKEN: "token",
                CONF_VERIFY_SSL: True,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "endpoint"

    with patch(
        "custom_components.portainer_swarm.config_flow.PortainerClient.async_validate_swarm_endpoint",
        AsyncMock(return_value=False),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENDPOINT_ID: "2"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_swarm_endpoint"}


async def test_user_flow_accepts_direct_docker_swarm_endpoint(hass) -> None:
    with patch(
        "custom_components.portainer_swarm.config_flow.PortainerClient.async_get_endpoints",
        AsyncMock(return_value=[{"Id": 3, "Name": "direct", "Type": 1, "Status": 1}]),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_URL: "https://portainer.example",
                CONF_API_TOKEN: "token",
                CONF_VERIFY_SSL: True,
            },
        )
    assert result["step_id"] == "endpoint"
    with (
        patch(
            "custom_components.portainer_swarm.config_flow.PortainerClient.async_validate_swarm_endpoint",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.portainer_swarm.async_setup_entry",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ENDPOINT_ID: "3"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_rejects_url_with_embedded_credentials(hass) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_URL: "https://user:password@portainer.example",
            CONF_API_TOKEN: "token",
            CONF_VERIFY_SSL: True,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}


async def test_user_flow_maps_invalid_auth(hass) -> None:
    from custom_components.portainer_swarm.client import PortainerAuthenticationError

    with patch(
        "custom_components.portainer_swarm.config_flow.PortainerClient.async_get_endpoints",
        AsyncMock(side_effect=PortainerAuthenticationError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_URL: "https://portainer.example",
                CONF_API_TOKEN: "bad",
                CONF_VERIFY_SSL: True,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow_changes_polling_interval(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="primary",
        data={CONF_URL: "https://portainer.example"},
        options={CONF_SCAN_INTERVAL: 60},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 180}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SCAN_INTERVAL: 180}


async def test_reauth_updates_api_token(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="primary",
        unique_id="https://portainer.example#1",
        data={
            CONF_URL: "https://portainer.example",
            CONF_API_TOKEN: "old-token",
            CONF_VERIFY_SSL: True,
            CONF_ENDPOINT_ID: 1,
            CONF_ENDPOINT_NAME: "primary",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "custom_components.portainer_swarm.config_flow.PortainerClient.async_get_endpoints",
        AsyncMock(return_value=[{"Id": 1, "Name": "primary", "Type": 2, "Status": 1}]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: "new-token"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_TOKEN] == "new-token"


async def test_reconfigure_updates_connection_settings(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="primary",
        unique_id="instance#1",
        data={
            CONF_URL: "https://old.example",
            CONF_API_TOKEN: "old-token",
            CONF_VERIFY_SSL: True,
            CONF_ENDPOINT_ID: 1,
            CONF_ENDPOINT_NAME: "primary",
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "custom_components.portainer_swarm.config_flow.PortainerClient.async_get_endpoints",
            AsyncMock(return_value=[{"Id": 1, "Name": "primary", "Status": 1}]),
        ),
        patch(
            "custom_components.portainer_swarm.config_flow.PortainerClient.async_validate_swarm_endpoint",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://new.example/",
                CONF_API_TOKEN: "new-token",
                CONF_VERIFY_SSL: False,
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_URL] == "https://new.example"
    assert entry.data[CONF_API_TOKEN] == "new-token"
    assert entry.data[CONF_VERIFY_SSL] is False
    assert entry.unique_id == f"{hashlib.sha256(b'https://new.example').hexdigest()[:16]}#1"


async def test_reconfigure_rejects_duplicate_instance_endpoint(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="old",
        unique_id="old-instance#1",
        data={
            CONF_URL: "https://old.example",
            CONF_API_TOKEN: "old-token",
            CONF_VERIFY_SSL: True,
            CONF_ENDPOINT_ID: 1,
            CONF_ENDPOINT_NAME: "primary",
        },
    )
    duplicate_id = f"{hashlib.sha256(b'https://new.example').hexdigest()[:16]}#1"
    duplicate = MockConfigEntry(
        domain=DOMAIN,
        title="duplicate",
        unique_id=duplicate_id,
        data={CONF_URL: "https://new.example"},
    )
    entry.add_to_hass(hass)
    duplicate.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    with (
        patch(
            "custom_components.portainer_swarm.config_flow.PortainerClient.async_get_endpoints",
            AsyncMock(return_value=[{"Id": 1, "Name": "primary", "Status": 1}]),
        ),
        patch(
            "custom_components.portainer_swarm.config_flow.PortainerClient.async_validate_swarm_endpoint",
            AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_URL: "https://new.example",
                CONF_API_TOKEN: "new-token",
                CONF_VERIFY_SSL: True,
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_URL] == "https://old.example"
