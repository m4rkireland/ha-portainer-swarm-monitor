"""Portainer Swarm Monitor integration."""

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import PortainerClient
from .const import PLATFORMS
from .coordinator import PortainerSwarmCoordinator


async def async_setup_entry(hass, entry) -> bool:
    """Set up Portainer Swarm Monitor."""
    client = PortainerClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data[CONF_API_TOKEN],
        entry.data[CONF_VERIFY_SSL],
    )
    coordinator = PortainerSwarmCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry) -> bool:
    """Unload Portainer Swarm Monitor."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
