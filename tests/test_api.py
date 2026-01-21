"""API smoke tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from pytest import MonkeyPatch

from shpoet.api.main import create_app
from shpoet.common.types import CharacterInput, SceneInput, UserPlayInput
from shpoet.config.settings import reset_settings
from shpoet.scripts.build_corpus import build_corpus


def _build_input() -> UserPlayInput:
    """Construct a minimal input payload for API tests."""

    return UserPlayInput(
        title="The Ashen Mirror",
        overview="A ruler confronts a mirror that remembers every oath.",
        characters=[
            CharacterInput(
                name="Cassia",
                description="A cautious sovereign testing prophecy.",
                voice_traits=["measured", "wary"],
            ),
        ],
        scenes=[
            SceneInput(
                act=1,
                scene=1,
                setting="A dim hall with a tarnished mirror.",
                summary="Cassia sees old vows shimmer across the glass.",
                participants=["Cassia"],
            )
        ],
    )


def test_health_check() -> None:
    """Ensure the health endpoint returns an OK payload."""

    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_plan_approve_generate_flow(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Ensure plan generation flows through approval and generation."""

    fixture_path = Path("tests/fixtures/sample_lines.txt")
    build_corpus(source_path=fixture_path, output_dir=tmp_path)
    monkeypatch.setenv("SHPOET_PROCESSED_DIR", str(tmp_path))
    reset_settings()

    client = TestClient(create_app())
    request_id = "req-api-flow"
    user_input = _build_input()
    print(f"[test] plan request_id={request_id} title={user_input.title}")

    plan_response = client.post(
        "/plan",
        json={"request_id": request_id, "user_input": user_input.model_dump()},
    )
    assert plan_response.status_code == 200
    plan_payload = plan_response.json()
    plan_id = plan_payload["plan_id"]
    print(f"[test] plan response plan_id={plan_id}")

    approve_response = client.post(
        f"/plan/{plan_id}/approve",
        json={"request_id": request_id, "approve": True, "regenerate": False},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["approved"] is True

    generate_response = client.post(
        "/generate",
        json={"request_id": request_id, "plan_id": plan_id, "config": {}},
    )
    assert generate_response.status_code == 200
    generate_payload = generate_response.json()
    job_id = generate_payload["job_id"]
    print(f"[test] generate response job_id={job_id} status={generate_payload['status']}")

    status_response = client.get(f"/generate/{job_id}", params={"request_id": request_id})
    assert status_response.status_code == 200
    status_payload = status_response.json()
    print(f"[test] status response lines={len(status_payload['output_lines'])}")
    assert status_payload["output_lines"]

    export_response = client.get(f"/export/{job_id}", params={"request_id": request_id})
    assert export_response.status_code == 200
    export_payload = export_response.json()
    print(f"[test] export markdown chars={len(export_payload['markdown'])}")
    assert export_payload["markdown"]
