from types import SimpleNamespace

from custom_components.portainer_swarm.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_allowlists_health_without_topology() -> None:
    entry = SimpleNamespace(
        as_dict=lambda: {
            "unique_id": "https://private.example#1",
            "data": {
                "url": "https://private.example",
                "api_token": "secret-token",
                "endpoint_id": 1,
                "endpoint_name": "private-endpoint",
                "verify_ssl": True,
            },
        },
        options={"scan_interval": 60, "private_option": "private-option-secret"},
        runtime_data=SimpleNamespace(
            data={
                "healthy": False,
                "docker_version": "28.0.0",
                "portainer_version": "2.30.0",
                "nodes_total": 2,
                "nodes_ready": 1,
                "nodes_unavailable": ["private-node"],
                "managers_total": 1,
                "managers_reachable": 1,
                "managers_quorum": True,
                "services_total": 2,
                "services_healthy": 1,
                "desired_replicas": 4,
                "running_replicas": 3,
                "under_replicated_services": ["private-service"],
                "failed_tasks": 1,
                "rejected_tasks": 0,
                "unhealthy_containers": ["private-container"],
                "stacks_total": 2,
                "stacks_unhealthy": ["private-stack"],
                "nodes": [{"id": "private-node-id", "name": "private-node"}],
                "services": [{"id": "private-service-id", "name": "private-service"}],
            }
        ),
    )

    diagnostics = await async_get_config_entry_diagnostics(None, entry)

    rendered = repr(diagnostics)
    for private_value in (
        "secret-token",
        "https://private.example",
        "private-endpoint",
        "private-node",
        "private-node-id",
        "private-service",
        "private-service-id",
        "private-container",
        "private-stack",
        "private-option-secret",
    ):
        assert private_value not in rendered
    assert "unique_id" not in diagnostics["config_entry"]
    assert diagnostics["config_entry"] == {
        "verify_ssl": True,
        "options": {"scan_interval": 60},
    }
    assert diagnostics["data"] == {
        "healthy": False,
        "docker_version": "28.0.0",
        "portainer_version": "2.30.0",
        "nodes_total": 2,
        "nodes_ready": 1,
        "nodes_unavailable_count": 1,
        "managers_total": 1,
        "managers_reachable": 1,
        "managers_quorum": True,
        "services_total": 2,
        "services_healthy": 1,
        "desired_replicas": 4,
        "running_replicas": 3,
        "under_replicated_services_count": 1,
        "failed_tasks": 1,
        "rejected_tasks": 0,
        "unhealthy_containers_count": 1,
        "stacks_total": 2,
        "stacks_unhealthy_count": 1,
    }
