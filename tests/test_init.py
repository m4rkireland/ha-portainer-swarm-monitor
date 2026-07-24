from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.portainer_swarm.const import CONF_ENDPOINT_ID, CONF_ENDPOINT_NAME, DOMAIN


async def test_setup_creates_read_only_health_entities(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="primary",
        unique_id="https://portainer.example#1",
        data={
            CONF_URL: "https://portainer.example",
            CONF_API_TOKEN: "token",
            CONF_VERIFY_SSL: True,
            CONF_ENDPOINT_ID: 1,
            CONF_ENDPOINT_NAME: "primary",
        },
    )
    entry.add_to_hass(hass)
    snapshot = {
        "portainer_version": "2.39.0",
        "info": {"ServerVersion": "28.0.1"},
        "nodes": [
            {
                "ID": "m1",
                "Spec": {"Role": "manager", "Availability": "active"},
                "Status": {"State": "ready"},
                "ManagerStatus": {"Reachability": "reachable"},
                "Description": {"Hostname": "manager"},
            }
        ],
        "services": [
            {"ID": "s1", "Spec": {"Name": "web", "Mode": {"Replicated": {"Replicas": 1}}}}
        ],
        "tasks": [{"ServiceID": "s1", "DesiredState": "running", "Status": {"State": "running"}}],
        "stacks": [{"Id": 1, "Name": "apps", "Status": 1}],
        "containers": [{"Names": ["/web"], "State": "running", "Status": "Up (healthy)"}],
    }

    with patch(
        "custom_components.portainer_swarm.coordinator.PortainerClient.async_get_snapshot",
        AsyncMock(return_value=snapshot),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.primary_swarm_health").state == "on"
    assert hass.states.get("sensor.primary_nodes_ready").state == "1"
    assert hass.states.get("sensor.primary_services_healthy").state == "1"
    assert hass.states.get("sensor.primary_under_replicated_services").state == "0"
    assert hass.states.get("sensor.primary_failed_tasks").state == "0"
    assert hass.states.get("sensor.primary_unhealthy_containers").state == "0"
    assert not any(
        state.domain in {"switch", "button"} and state.name.startswith("primary")
        for state in hass.states.async_all()
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.primary_swarm_health").state == "unavailable"


async def test_new_service_entity_is_registered_after_coordinator_update(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="primary",
        unique_id="instance#1",
        data={
            CONF_URL: "https://portainer.example",
            CONF_API_TOKEN: "token",
            CONF_VERIFY_SSL: True,
            CONF_ENDPOINT_ID: 1,
            CONF_ENDPOINT_NAME: "primary",
        },
    )
    entry.add_to_hass(hass)

    def snapshot(services):
        return {
            "portainer_version": "2.39.0",
            "info": {"ServerVersion": "28.0.1"},
            "nodes": [],
            "services": services,
            "tasks": [],
            "stacks": [],
            "containers": [],
        }

    first = snapshot(
        [{"ID": "s1", "Spec": {"Name": "web", "Mode": {"Replicated": {"Replicas": 0}}}}]
    )
    second = snapshot(
        [
            {"ID": "s1", "Spec": {"Name": "web", "Mode": {"Replicated": {"Replicas": 0}}}},
            {"ID": "s2", "Spec": {"Name": "api", "Mode": {"Replicated": {"Replicas": 0}}}},
        ]
    )

    with patch(
        "custom_components.portainer_swarm.coordinator.PortainerClient.async_get_snapshot",
        AsyncMock(side_effect=[first, second]),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await entry.runtime_data.async_request_refresh()
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_service_s2")
        is not None
    )
