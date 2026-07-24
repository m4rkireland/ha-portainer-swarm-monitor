# Portainer Swarm Monitor

A read-only Home Assistant custom integration for monitoring Docker Swarm through the Portainer API.

Unlike Home Assistant's built-in Portainer integration, this integration uses Swarm-level node, service and task APIs. It does not request per-container statistics through a single Docker node, so containers scheduled on remote workers do not break the update.

## Features

- Overall Swarm health
- Ready and unavailable nodes
- Reachable managers
- Healthy and under-replicated services
- Desired and running replicas
- Current failed and rejected tasks (historical shutdown tasks are ignored)
- Unhealthy containers
- Active/unhealthy stacks
- Docker and Portainer versions
- Last successful poll timestamp
- Disabled-by-default diagnostic entities for individual nodes and services
- Configurable 30–900 second polling interval
- Redacted diagnostics
- **No control actions**: no start, stop, restart, prune, redeploy or stack mutation

## Installation with HACS

Until this repository is accepted into the HACS default catalogue:

1. Open HACS in Home Assistant.
2. Select **Custom repositories**.
3. Add `https://github.com/m4rkireland/ha-portainer-swarm-monitor` as an **Integration**.
4. Install **Portainer Swarm Monitor**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration → Portainer Swarm Monitor**.

## Configuration

The UI flow asks for:

- Portainer URL
- Portainer API token
- SSL certificate verification
- Polling interval (30–900 seconds)
- Docker Swarm endpoint

Use a dedicated Portainer user/token with the least privileges available. The integration itself only performs HTTP `GET` requests.

## Health semantics

Only tasks whose `DesiredState` is `running` contribute to current failed/rejected task counts. Old failed tasks retained by Swarm with `DesiredState=shutdown` are intentionally excluded.

A replicated service is healthy when its running task count meets the replica count in its service specification and it has no current failed/rejected desired task. A global service uses Docker Engine's `ServiceStatus.DesiredTasks` and `RunningTasks`, which account for placement constraints and node eligibility. Replicated and global jobs are tracked separately and excluded from continuous replica totals.

Overall health also requires a reachable majority of the managers returned by the Swarm API; an empty manager set is unhealthy.

## Development

```bash
uv python install 3.14.2
uv sync
uv run pytest -q
uv run ruff check .
```

## License

MIT
