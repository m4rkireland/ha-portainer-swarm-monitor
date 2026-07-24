"""Health binary sensors for Portainer Swarm Monitor."""

from typing import override

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .entity import PortainerSwarmEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    known_nodes: set[str] = set()
    known_services: set[str] = set()

    def async_add_new_resources() -> None:
        entities = []
        for node in coordinator.data["nodes"]:
            if node["id"] not in known_nodes:
                known_nodes.add(node["id"])
                entities.append(NodeHealthBinarySensor(coordinator, node["id"], node["name"]))
        for service in coordinator.data["services"]:
            if service["id"] not in known_services:
                known_services.add(service["id"])
                entities.append(
                    ServiceHealthBinarySensor(coordinator, service["id"], service["name"])
                )
        if entities:
            async_add_entities(entities)

    async_add_entities([SwarmHealthBinarySensor(coordinator)])
    async_add_new_resources()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_resources))


class SwarmHealthBinarySensor(PortainerSwarmEntity, BinarySensorEntity):
    _attr_translation_key = "swarm_health"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_swarm_health"

    @property
    @override
    def is_on(self) -> bool:
        return self.coordinator.data["healthy"]


class NodeHealthBinarySensor(PortainerSwarmEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, node_id: str, name: str) -> None:
        super().__init__(coordinator)
        self._node_id = node_id
        self._attr_name = f"{name} node health"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_node_{node_id}"

    @property
    @override
    def available(self) -> bool:
        return super().available and any(
            node["id"] == self._node_id for node in self.coordinator.data["nodes"]
        )

    @property
    @override
    def is_on(self) -> bool:
        return next(
            (
                node["ready"]
                for node in self.coordinator.data["nodes"]
                if node["id"] == self._node_id
            ),
            False,
        )


class ServiceHealthBinarySensor(PortainerSwarmEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, service_id: str, name: str) -> None:
        super().__init__(coordinator)
        self._service_id = service_id
        self._attr_name = f"{name} service health"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_service_{service_id}"

    @property
    @override
    def available(self) -> bool:
        return super().available and any(
            service["id"] == self._service_id for service in self.coordinator.data["services"]
        )

    @property
    @override
    def is_on(self) -> bool:
        return next(
            (
                service["healthy"]
                for service in self.coordinator.data["services"]
                if service["id"] == self._service_id
            ),
            False,
        )
