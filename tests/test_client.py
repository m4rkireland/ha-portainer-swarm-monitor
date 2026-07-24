import pytest

from custom_components.portainer_swarm.client import (
    PortainerAuthenticationError,
    PortainerClient,
    PortainerConnectionError,
    PortainerResponseError,
)


class FakeResponse:
    def __init__(self, status: int, payload=None) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses) -> None:
        self.responses = iter(responses)
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.asyncio
async def test_client_fetches_read_only_swarm_snapshot_without_leaking_token() -> None:
    session = FakeSession(
        [
            FakeResponse(200, {"Version": "2.39.0"}),
            FakeResponse(200, [{"Id": 1, "Name": "primary", "Type": 2, "Status": 1}]),
            FakeResponse(200, {"ServerVersion": "28.0.1"}),
            FakeResponse(200, []),
            FakeResponse(200, []),
            FakeResponse(200, []),
            FakeResponse(200, []),
            FakeResponse(200, []),
        ]
    )
    client = PortainerClient(session, "https://portainer.example", "secret-token", verify_ssl=True)

    endpoints = await client.async_get_endpoints()
    snapshot = await client.async_get_snapshot(1)

    assert endpoints[0]["Name"] == "primary"
    assert snapshot["portainer_version"] == "2.39.0"
    assert snapshot["info"]["ServerVersion"] == "28.0.1"
    assert all(kwargs["headers"] == {"X-API-Key": "secret-token"} for _, kwargs in session.requests)
    assert "secret-token" not in repr(client)
    assert all(
        request[0].startswith("https://portainer.example/api/") for request in session.requests
    )


@pytest.mark.asyncio
async def test_client_maps_unauthorized_response() -> None:
    client = PortainerClient(
        FakeSession([FakeResponse(401, {})]), "https://portainer.example", "secret", True
    )
    with pytest.raises(PortainerAuthenticationError):
        await client.async_get_endpoints()


@pytest.mark.asyncio
async def test_client_maps_transport_error_without_secret() -> None:
    client = PortainerClient(
        FakeSession([OSError("secret network detail")]), "https://portainer.example", "secret", True
    )
    with pytest.raises(PortainerConnectionError) as exc:
        await client.async_get_endpoints()
    assert "secret" not in str(exc.value)


@pytest.mark.asyncio
async def test_snapshot_fetches_portainer_version_on_fresh_client() -> None:
    session = FakeSession(
        [
            FakeResponse(200, {"Version": "2.39.0"}),
            FakeResponse(200, {"ServerVersion": "28.0.1"}),
            FakeResponse(200, []),
            FakeResponse(200, []),
            FakeResponse(200, []),
            FakeResponse(200, []),
            FakeResponse(200, []),
        ]
    )
    client = PortainerClient(session, "https://portainer.example", "secret", True)

    snapshot = await client.async_get_snapshot(1)

    assert snapshot["portainer_version"] == "2.39.0"
    assert snapshot["info"]["ServerVersion"] == "28.0.1"


@pytest.mark.asyncio
async def test_client_rejects_malformed_success_payload() -> None:
    client = PortainerClient(
        FakeSession([FakeResponse(200, []), FakeResponse(200, {})]),
        "https://portainer.example",
        "secret",
        True,
    )
    with pytest.raises(PortainerResponseError, match="status"):
        await client.async_get_endpoints()


@pytest.mark.asyncio
async def test_client_detects_swarm_manager_from_docker_info() -> None:
    client = PortainerClient(
        FakeSession(
            [
                FakeResponse(
                    200,
                    {"Swarm": {"LocalNodeState": "active", "ControlAvailable": True}},
                )
            ]
        ),
        "https://portainer.example",
        "secret",
        True,
    )
    assert await client.async_validate_swarm_endpoint(7) is True
