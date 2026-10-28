from backend.main import app


def test_all_requested_versioned_contracts_have_documented_response_schemas():
    methods = {
        "/health": "get",
        "/metrics": "get",
        "/network/overview": "get",
        "/nodes": "get",
        "/nodes/{node_id}": "get",
        "/blocks": "get",
        "/transactions": "get",
        "/alerts": "get",
        "/trust/scores": "get",
        "/healing/actions": "get",
        "/healing/actions/{action_id}": "get",
        "/simulation/scenarios": "post",
        "/simulation/start": "post",
        "/simulation/stop": "post",
        "/policies/evaluate": "post",
        "/experiments": "get",
        "/experiments/{experiment_id}": "get",
    }
    schema = app.openapi()
    for path, method in methods.items():
        operation = schema["paths"]["/api/v1" + path][method]
        success = next(
            value for key, value in operation["responses"].items() if key.startswith("2")
        )
        assert success["content"]["application/json"]["schema"]
        if method == "post":
            assert operation["security"]
            assert "401" in operation["responses"] and "403" in operation["responses"]


def test_developer_docs_and_owned_animations_exist():
    import xml.etree.ElementTree as ET
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for name in (
        "IMPLEMENTATION_AUDIT.md",
        "ROADMAP.md",
        "architecture.md",
        "SRS.md",
        "setup-guide.md",
        "API.md",
        "consensus.md",
        "rl-design.md",
        "security-model.md",
        "testing.md",
        "experiments.md",
        "deployment.md",
        "troubleshooting.md",
    ):
        assert (root / "docs" / name).is_file(), name
    readme = (root / "README.md").read_text(encoding="utf-8")
    for name in ("header", "footer"):
        path = root / "docs" / "assets" / (name + ".svg")
        tree = ET.parse(path)
        assert any("animate" in element.tag for element in tree.iter())
        assert f"docs/assets/{name}.svg" in readme
