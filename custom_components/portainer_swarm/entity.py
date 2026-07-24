"""Base entities for Portainer Swarm Monitor."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENDPOINT_ID, CONF_ENDPOINT_NAME, DOMAIN


class PortainerSwarmEntity(CoordinatorEntity):
    """Base coordinator entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{entry.data[CONF_ENDPOINT_ID]}")},
            name=entry.data[CONF_ENDPOINT_NAME],
            manufacturer="Portainer",
            configuration_url=entry.data.get("url"),
        )
