from custom_components.portainer_swarm.summary import build_summary


def _service(service_id: str, name: str, replicas: int = 1) -> dict:
    return {
        "ID": service_id,
        "Spec": {"Name": name, "Mode": {"Replicated": {"Replicas": replicas}}},
    }


def _task(service_id: str, desired: str, state: str) -> dict:
    return {
        "ServiceID": service_id,
        "DesiredState": desired,
        "Status": {"State": state},
    }


def test_build_summary_reports_healthy_swarm() -> None:
    summary = build_summary(
        info={"ServerVersion": "28.0.1", "Swarm": {"Managers": 1}},
        nodes=[
            {
                "ID": "m1",
                "Spec": {"Role": "manager", "Availability": "active"},
                "Status": {"State": "ready"},
                "ManagerStatus": {"Reachability": "reachable"},
                "Description": {"Hostname": "manager"},
            },
            {
                "ID": "w1",
                "Spec": {"Role": "worker", "Availability": "active"},
                "Status": {"State": "ready"},
                "Description": {"Hostname": "worker"},
            },
        ],
        services=[_service("s1", "web", 2)],
        tasks=[_task("s1", "running", "running"), _task("s1", "running", "running")],
        stacks=[{"Id": 1, "Name": "apps", "Status": 1}],
        containers=[{"State": "running", "Status": "Up 2 hours (healthy)"}],
    )

    assert summary["healthy"] is True
    assert summary["nodes_total"] == 2
    assert summary["nodes_ready"] == 2
    assert summary["managers_reachable"] == 1
    assert summary["services_total"] == 1
    assert summary["services_healthy"] == 1
    assert summary["desired_replicas"] == 2
    assert summary["running_replicas"] == 2
    assert summary["under_replicated_services"] == []
    assert summary["failed_tasks"] == 0
    assert summary["rejected_tasks"] == 0
    assert summary["unhealthy_containers"] == []
    assert summary["stacks_unhealthy"] == []


def test_build_summary_ignores_historical_failed_tasks_but_reports_active_failures() -> None:
    summary = build_summary(
        info={},
        nodes=[
            {
                "ID": "m1",
                "Spec": {"Role": "manager", "Availability": "active"},
                "Status": {"State": "ready"},
                "ManagerStatus": {"Reachability": "reachable"},
                "Description": {"Hostname": "manager"},
            }
        ],
        services=[_service("s1", "api", 2)],
        tasks=[
            _task("s1", "running", "running"),
            _task("s1", "running", "rejected"),
            _task("s1", "shutdown", "failed"),
        ],
        stacks=[{"Id": 1, "Name": "broken", "Status": 2}],
        containers=[{"Names": ["/bad"], "State": "running", "Status": "Up 1 minute (unhealthy)"}],
    )

    assert summary["healthy"] is False
    assert summary["services_healthy"] == 0
    assert summary["under_replicated_services"] == ["api"]
    assert summary["failed_tasks"] == 0
    assert summary["rejected_tasks"] == 1
    assert summary["unhealthy_containers"] == ["bad"]
    assert summary["stacks_unhealthy"] == ["broken"]


def test_build_summary_reports_unavailable_node_and_manager() -> None:
    summary = build_summary(
        info={},
        nodes=[
            {
                "ID": "m1",
                "Spec": {"Role": "manager", "Availability": "pause"},
                "Status": {"State": "down"},
                "ManagerStatus": {"Reachability": "unreachable"},
                "Description": {"Hostname": "manager"},
            }
        ],
        services=[],
        tasks=[],
        stacks=[],
        containers=[],
    )

    assert summary["nodes_ready"] == 0
    assert summary["nodes_unavailable"] == ["manager"]
    assert summary["managers_reachable"] == 0
    assert summary["healthy"] is False


def test_global_service_uses_engine_service_status_not_all_nodes() -> None:
    summary = build_summary(
        info={},
        nodes=[
            {
                "ID": "m1",
                "Spec": {"Role": "manager"},
                "Status": {"State": "ready"},
                "ManagerStatus": {"Reachability": "reachable"},
            },
            {
                "ID": "w1",
                "Spec": {"Role": "worker"},
                "Status": {"State": "ready"},
            },
        ],
        services=[
            {
                "ID": "g1",
                "Spec": {
                    "Name": "manager-only",
                    "Mode": {"Global": {}},
                    "TaskTemplate": {"Placement": {"Constraints": ["node.role == manager"]}},
                },
                "ServiceStatus": {"DesiredTasks": 1, "RunningTasks": 1},
            }
        ],
        tasks=[_task("g1", "running", "running")],
        stacks=[],
        containers=[],
    )
    assert summary["services"][0]["mode"] == "global"
    assert summary["desired_replicas"] == 1
    assert summary["running_replicas"] == 1
    assert summary["healthy"] is True


def test_job_modes_are_not_treated_as_continuous_replicas() -> None:
    summary = build_summary(
        info={},
        nodes=[],
        services=[
            {
                "ID": "j1",
                "Spec": {
                    "Name": "job",
                    "Mode": {"ReplicatedJob": {"MaxConcurrent": 1}},
                },
            },
            {
                "ID": "j2",
                "Spec": {"Name": "global-job", "Mode": {"GlobalJob": {}}},
            },
        ],
        tasks=[],
        stacks=[],
        containers=[],
    )
    assert [service["mode"] for service in summary["services"]] == [
        "replicated_job",
        "global_job",
    ]
    assert summary["desired_replicas"] == 0
    assert summary["under_replicated_services"] == []


def test_manager_quorum_is_required_for_healthy_swarm() -> None:
    nodes = []
    for number, reachability in enumerate(("reachable", "unreachable", "unreachable"), 1):
        nodes.append(
            {
                "ID": f"m{number}",
                "Spec": {"Role": "manager", "Availability": "active"},
                "Status": {"State": "ready"},
                "ManagerStatus": {"Reachability": reachability},
            }
        )
    summary = build_summary(info={}, nodes=nodes, services=[], tasks=[], stacks=[], containers=[])
    assert summary["managers_quorum"] is False
    assert summary["healthy"] is False


def test_replicated_service_uses_configured_spec_as_desired_state() -> None:
    service = _service("s1", "web", 2)
    service["ServiceStatus"] = {"DesiredTasks": 1, "RunningTasks": 1}
    summary = build_summary(
        info={},
        nodes=[
            {
                "ID": "m1",
                "Spec": {"Role": "manager"},
                "Status": {"State": "ready"},
                "ManagerStatus": {"Reachability": "reachable"},
            }
        ],
        services=[service],
        tasks=[_task("s1", "running", "running")],
        stacks=[],
        containers=[],
    )
    assert summary["desired_replicas"] == 2
    assert summary["under_replicated_services"] == ["web"]


def test_swarm_without_any_manager_is_unhealthy() -> None:
    summary = build_summary(info={}, nodes=[], services=[], tasks=[], stacks=[], containers=[])
    assert summary["managers_quorum"] is False
    assert summary["healthy"] is False
