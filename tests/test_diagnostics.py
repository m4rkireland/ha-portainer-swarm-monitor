from types import SimpleNamespace

from custom_components.portainer_swarm.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redacts_url_and_token() -> None:
    entry = SimpleNamespace(
        as_dict=lambda: {
            "unique_id": "https://private.example#1",
            "data": {
                "url": "https://private.example",
                "api_token": "secret-token",
                "endpoint_id": 1,
            },
        },
        runtime_data=SimpleNamespace(data={"healthy": True, "nodes": []}),
    )
    diagnostics = await async_get_config_entry_diagnostics(None, entry)
    rendered = repr(diagnostics)
    assert "secret-token" not in rendered
    assert "https://private.example" not in rendered
    assert "unique_id" not in diagnostics["config_entry"]
    assert diagnostics["data"]["healthy"] is True
