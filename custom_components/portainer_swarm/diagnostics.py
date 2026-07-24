"""Diagnostics for Portainer Swarm Monitor."""


async def async_get_config_entry_diagnostics(hass, config_entry):
    """Return an allowlisted config and bounded coordinator data."""
    entry_data = config_entry.as_dict().get("data", {})
    return {
        "config_entry": {
            "endpoint_id": entry_data.get("endpoint_id"),
            "endpoint_name": entry_data.get("endpoint_name"),
            "verify_ssl": entry_data.get("verify_ssl"),
            "options": dict(getattr(config_entry, "options", {})),
        },
        "data": config_entry.runtime_data.data,
    }
