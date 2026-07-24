"""Summarise Docker Swarm API responses into stable Home Assistant data."""

from __future__ import annotations

from collections import Counter
from typing import Any


def _name(item: dict[str, Any], fallback: str) -> str:
    names = item.get("Names") or []
    if names:
        return str(names[0]).lstrip("/")
    return str(item.get("Name") or item.get("ID") or fallback)


def build_summary(
    *,
    info: dict[str, Any],
    nodes: list[dict[str, Any]],
    services: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    stacks: list[dict[str, Any]],
    containers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build bounded, current-state Swarm health data.

    Historical Swarm tasks have DesiredState=shutdown and are deliberately ignored
    when calculating current failures and replica health.
    """
    node_details: list[dict[str, Any]] = []
    for node in nodes:
        spec = node.get("Spec", {})
        status = node.get("Status", {})
        manager = node.get("ManagerStatus", {})
        hostname = node.get("Description", {}).get("Hostname") or node.get("ID", "unknown")
        ready = status.get("State") == "ready" and spec.get("Availability", "active") == "active"
        node_details.append(
            {
                "id": node.get("ID"),
                "name": hostname,
                "role": spec.get("Role", "worker"),
                "state": status.get("State", "unknown"),
                "availability": spec.get("Availability", "active"),
                "manager_reachability": manager.get("Reachability"),
                "ready": ready,
            }
        )

    active_tasks = [task for task in tasks if task.get("DesiredState") == "running"]
    task_states = Counter(task.get("Status", {}).get("State", "unknown") for task in active_tasks)
    by_service: dict[str, list[dict[str, Any]]] = {}
    for task in active_tasks:
        by_service.setdefault(str(task.get("ServiceID", "")), []).append(task)

    service_details: list[dict[str, Any]] = []
    under_replicated: list[str] = []
    unhealthy_services: list[str] = []
    for service in services:
        service_id = str(service.get("ID", ""))
        spec = service.get("Spec", {})
        service_name = str(spec.get("Name") or service_id or "unknown")
        mode = spec.get("Mode", {})
        service_status = service.get("ServiceStatus") or {}
        current = by_service.get(service_id, [])
        task_running = sum(task.get("Status", {}).get("State") == "running" for task in current)
        if "Replicated" in mode:
            desired = int((mode.get("Replicated") or {}).get("Replicas", 0))
            running = int(service_status.get("RunningTasks", task_running))
            mode_name = "replicated"
            continuous = True
        elif "Global" in mode:
            desired = int(service_status.get("DesiredTasks", len(current)))
            running = int(service_status.get("RunningTasks", task_running))
            mode_name = "global"
            continuous = True
        elif "ReplicatedJob" in mode:
            desired = running = 0
            mode_name = "replicated_job"
            continuous = False
        elif "GlobalJob" in mode:
            desired = running = 0
            mode_name = "global_job"
            continuous = False
        else:
            desired = running = 0
            mode_name = "unknown"
            continuous = False
        failed = sum(task.get("Status", {}).get("State") == "failed" for task in current)
        rejected = sum(task.get("Status", {}).get("State") == "rejected" for task in current)
        healthy = (not continuous or running >= desired) and failed == 0 and rejected == 0
        if continuous and running < desired:
            under_replicated.append(service_name)
        if not healthy:
            unhealthy_services.append(service_name)
        service_details.append(
            {
                "id": service_id,
                "name": service_name,
                "mode": mode_name,
                "desired": desired,
                "running": running,
                "failed": failed,
                "rejected": rejected,
                "healthy": healthy,
            }
        )

    unhealthy_containers = sorted(
        _name(container, "unknown")
        for container in containers
        if "(unhealthy)" in str(container.get("Status", "")).lower()
        or container.get("State") == "dead"
    )
    unhealthy_stacks = sorted(
        str(stack.get("Name") or stack.get("Id") or "unknown")
        for stack in stacks
        if stack.get("Status") not in (1, "active")
    )
    unavailable_nodes = sorted(str(node["name"]) for node in node_details if not node["ready"])
    managers = [node for node in node_details if node["role"] == "manager"]
    managers_reachable = sum(node["manager_reachability"] == "reachable" for node in managers)
    managers_quorum = bool(managers) and managers_reachable >= (len(managers) // 2 + 1)
    running_replicas = sum(service["running"] for service in service_details)
    desired_replicas = sum(service["desired"] for service in service_details)

    healthy = not (
        unavailable_nodes
        or under_replicated
        or task_states["failed"]
        or task_states["rejected"]
        or unhealthy_containers
        or unhealthy_stacks
        or not managers_quorum
    )

    return {
        "healthy": healthy,
        "docker_version": info.get("ServerVersion"),
        "nodes_total": len(node_details),
        "nodes_ready": len(node_details) - len(unavailable_nodes),
        "nodes_unavailable": unavailable_nodes,
        "managers_total": len(managers),
        "managers_reachable": managers_reachable,
        "managers_quorum": managers_quorum,
        "services_total": len(service_details),
        "services_healthy": len(service_details) - len(unhealthy_services),
        "desired_replicas": desired_replicas,
        "running_replicas": running_replicas,
        "under_replicated_services": sorted(under_replicated),
        "failed_tasks": task_states["failed"],
        "rejected_tasks": task_states["rejected"],
        "unhealthy_containers": unhealthy_containers,
        "stacks_total": len(stacks),
        "stacks_unhealthy": unhealthy_stacks,
        "nodes": node_details,
        "services": service_details,
    }
