from unittest.mock import AsyncMock

import pytest
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portainer_swarm.client import (
    PortainerAuthenticationError,
    PortainerResponseError,
)
from custom_components.portainer_swarm.const import CONF_ENDPOINT_ID, DOMAIN
from custom_components.portainer_swarm.coordinator import PortainerSwarmCoordinator


def _entry():
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://portainer.example",
            CONF_API_TOKEN: "token",
            CONF_VERIFY_SSL: True,
            CONF_ENDPOINT_ID: 1,
        },
    )


async def test_coordinator_maps_authentication_failure(hass) -> None:
    entry = _entry()
    client = AsyncMock()
    client.async_get_snapshot.side_effect = PortainerAuthenticationError
    coordinator = PortainerSwarmCoordinator(hass, entry, client)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_maps_malformed_response(hass) -> None:
    entry = _entry()
    client = AsyncMock()
    client.async_get_snapshot.side_effect = PortainerResponseError("malformed")
    coordinator = PortainerSwarmCoordinator(hass, entry, client)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
