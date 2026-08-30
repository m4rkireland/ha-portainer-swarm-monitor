"""Diagnostics for Portainer Swarm Monitor."""

from .const import CONF_SCAN_INTERVAL

_DIAGNOSTIC_VALUE_KEYS = (
    "healthy",
    "docker_version",
    "portainer_version",
    "nodes_total",
    "nodes_ready",
    "managers_total",
    "managers_reachable",
    "managers_quorum",
    "services_total",
    "services_healthy",
    "desired_replicas",
    "running_replicas",
    "failed_tasks",
    "rejected_tasks",
    "stacks_total",
    "last_successful_poll",
)
_DIAGNOSTIC_LIST_COUNTS = {
    "nodes_unavailable_count": "nodes_unavailable",
    "under_replicated_services_count": "under_replicated_services",
    "unhealthy_containers_count": "unhealthy_containers",
    "stacks_unhealthy_count": "stacks_unhealthy",
}


async def async_get_config_entry_diagnostics(hass, config_entry):
    """Return allowlisted health data without infrastructure topology."""
    entry_data = config_entry.as_dict().get("data", {})
    coordinator_data = config_entry.runtime_data.data
    diagnostics_data = {
        key: coordinator_data[key] for key in _DIAGNOSTIC_VALUE_KEYS if key in coordinator_data
    }
    diagnostics_data.update(
        {
            diagnostic_key: len(coordinator_data.get(source_key) or ())
            for diagnostic_key, source_key in _DIAGNOSTIC_LIST_COUNTS.items()
        }
    )
    return {
        "config_entry": {
            "verify_ssl": entry_data.get("verify_ssl"),
            "options": {
                option_key: config_entry.options[option_key]
                for option_key in (CONF_SCAN_INTERVAL,)
                if option_key in config_entry.options
            },
        },
        "data": diagnostics_data,
    }
