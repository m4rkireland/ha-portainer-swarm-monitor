"""Data coordinator for Portainer Swarm Monitor."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import PortainerAuthenticationError, PortainerClient, PortainerError
from .const import CONF_ENDPOINT_ID, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .summary import build_summary

_LOGGER = logging.getLogger(__name__)


class PortainerSwarmCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll one Portainer Swarm endpoint."""

    def __init__(self, hass, entry: ConfigEntry, client: PortainerClient) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(
                    CONF_SCAN_INTERVAL,
                    entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                )
            ),
            config_entry=entry,
        )
        self.entry = entry
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            snapshot = await self.client.async_get_snapshot(self.entry.data[CONF_ENDPOINT_ID])
        except PortainerAuthenticationError as err:
            raise ConfigEntryAuthFailed("Portainer authentication failed") from err
        except PortainerError as err:
            raise UpdateFailed("Unable to update Portainer Swarm data") from err
        summary = build_summary(
            info=snapshot["info"],
            nodes=snapshot["nodes"],
            services=snapshot["services"],
            tasks=snapshot["tasks"],
            stacks=snapshot["stacks"],
            containers=snapshot["containers"],
        )
        summary["portainer_version"] = snapshot.get("portainer_version")
        summary["last_successful_poll"] = datetime.now(UTC)
        return summary


PortainerSwarmConfigEntry = ConfigEntry[PortainerSwarmCoordinator]
