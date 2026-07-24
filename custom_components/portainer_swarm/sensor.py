"""Sensors for Portainer Swarm Monitor."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory

from .entity import PortainerSwarmEntity


@dataclass(frozen=True, kw_only=True)
class SwarmSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


DESCRIPTIONS = (
    SwarmSensorDescription(
        key="nodes_ready",
        translation_key="nodes_ready",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["nodes_ready"],
        attrs_fn=lambda d: {"total": d["nodes_total"], "unavailable": d["nodes_unavailable"]},
    ),
    SwarmSensorDescription(
        key="managers_reachable",
        translation_key="managers_reachable",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["managers_reachable"],
        attrs_fn=lambda d: {
            "total": d["managers_total"],
            "quorum": d["managers_quorum"],
        },
    ),
    SwarmSensorDescription(
        key="services_healthy",
        translation_key="services_healthy",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["services_healthy"],
        attrs_fn=lambda d: {"total": d["services_total"]},
    ),
    SwarmSensorDescription(
        key="running_replicas",
        translation_key="running_replicas",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["running_replicas"],
        attrs_fn=lambda d: {"desired": d["desired_replicas"]},
    ),
    SwarmSensorDescription(
        key="under_replicated_services",
        translation_key="under_replicated_services",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d["under_replicated_services"]),
        attrs_fn=lambda d: {"services": d["under_replicated_services"]},
    ),
    SwarmSensorDescription(
        key="failed_tasks",
        translation_key="failed_tasks",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["failed_tasks"],
    ),
    SwarmSensorDescription(
        key="rejected_tasks",
        translation_key="rejected_tasks",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["rejected_tasks"],
    ),
    SwarmSensorDescription(
        key="unhealthy_containers",
        translation_key="unhealthy_containers",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d["unhealthy_containers"]),
        attrs_fn=lambda d: {"containers": d["unhealthy_containers"]},
    ),
    SwarmSensorDescription(
        key="stacks_unhealthy",
        translation_key="stacks_unhealthy",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d["stacks_unhealthy"]),
        attrs_fn=lambda d: {"stacks": d["stacks_unhealthy"], "total": d["stacks_total"]},
    ),
    SwarmSensorDescription(
        key="docker_version",
        translation_key="docker_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["docker_version"],
    ),
    SwarmSensorDescription(
        key="portainer_version",
        translation_key="portainer_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["portainer_version"],
    ),
    SwarmSensorDescription(
        key="last_successful_poll",
        translation_key="last_successful_poll",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["last_successful_poll"],
    ),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities(SwarmSensor(entry.runtime_data, description) for description in DESCRIPTIONS)


class SwarmSensor(PortainerSwarmEntity, SensorEntity):
    entity_description: SwarmSensorDescription

    def __init__(self, coordinator, description: SwarmSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

    @property
    @override
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def extra_state_attributes(self):
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
