import json
import uuid
from datetime import timedelta
from pathlib import Path

from app.models import Issue, IssueEdit, Recording
from app.models.base import utcnow
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.conftest import (
    ADMIN_NUMBER,
    ADMIN_PASSWORD,
    OPERATOR_NUMBER,
    OPERATOR_PASSWORD,
    OTHER_NUMBER,
    OTHER_PASSWORD,
    auth_header,
    login,
    upload,
    wav_bytes,
)


def test_mock_pipeline_upload_and_owner_comes_from_auth(client: TestClient, accounts, db) -> None:
    logged = login(client, OPERATOR_NUMBER, OPERATOR_PASSWORD)
    token = logged.json()["access_token"]
    response = upload(client, token, operator_id=str(accounts["admin"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert "컷인" in body["transcript"]["corrected_text"]
    assert "라바콘" in body["transcript"]["corrected_text"]
    assert body["extraction"]["event_type"]["value"] == "cut_in"
    assert body["extraction"]["event_type"]["probabilities"]
    assert body["extraction"]["event_type"]["confidence"] is not None
    assert body["extraction"]["severity"]["value"] == "high"
    assert body["extraction"]["target_type"]["value"] == "vehicle"
    assert body["extraction"]["ego_reaction"]["value"] == "hard_decel"
    assert body["extraction"]["road_type"]["value"] is None
    assert body["extraction"]["road_type"]["needs_review"] is True
    assert body["extraction"]["ego_action_before"]["value"] is None
    assert body["ticket"]["content"]
    assert "컷인" in body["ticket"]["content"]
    assert "needs_review" in body["extraction"]["location"]
    assert body["status"] == "draft"
    recording = db.get(Recording, uuid.UUID(body["recording_id"]))
    assert recording is not None
    assert recording.user_id == accounts["operator"]
    assert str(recording.user_id) != str(accounts["admin"])


def test_patch_keeps_ai_value_and_editor(client: TestClient, accounts, db) -> None:
    token = login(client, OPERATOR_NUMBER, OPERATOR_PASSWORD).json()["access_token"]
    created = upload(client, token)
    issue_id = created.json()["issue_id"]
    patched = client.patch(
        f"/api/issues/{issue_id}",
        json={"cause": "운전자가 고친 원인", "confirm": True},
        headers=auth_header(token),
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["status"] == "confirmed"
    assert body["final_extraction"]["cause"]["value"] == "운전자가 고친 원인"
    assert body["ai_extraction"]["cause"]["value"] != "운전자가 고친 원인"
    assert body["confirmed_by"] == str(accounts["operator"])
    edit = db.query(IssueEdit).filter(IssueEdit.issue_id == uuid.UUID(issue_id), IssueEdit.field == "cause").one()
    assert json.loads(edit.final_value) == "운전자가 고친 원인"
    assert edit.edited_by == accounts["operator"]
    assert json.loads(edit.ai_value) == body["ai_extraction"]["cause"]["value"]


def test_patch_guide_choice_and_ticket_fields(client: TestClient, db) -> None:
    token = login(client, OPERATOR_NUMBER, OPERATOR_PASSWORD).json()["access_token"]
    created = upload(
        client,
        token,
        vehicle_number="12가3456",
        occurred_on="2026-11-01",
        autonomy_version="ad-0",
        map_version="map-0",
        latitude="37.5",
        longitude="127.0",
    )
    assert created.status_code == 200, created.text
    issue_id = created.json()["issue_id"]
    assert created.json()["ticket"]["vehicle_number"] == "12가3456"
    assert created.json()["ticket"]["occurred_on"] == "2026-11-01"
    patched = client.patch(
        f"/api/issues/{issue_id}",
        json={
            "road_type": "intersection",
            "vehicle_number": "99나9999",
            "content": "수정한 이슈 내용",
            "confirm": True,
        },
        headers=auth_header(token),
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["final_extraction"]["road_type"]["value"] == "intersection"
    assert body["ai_extraction"]["road_type"]["value"] is None
    assert body["ticket"]["vehicle_number"] == "99나9999"
    assert body["ticket"]["content"] == "수정한 이슈 내용"
    assert body["ticket"]["autonomy_version"] == "ad-0"
    road = db.query(IssueEdit).filter(IssueEdit.issue_id == uuid.UUID(issue_id), IssueEdit.field == "road_type").one()
    assert json.loads(road.final_value) == "intersection"
    number = (
        db.query(IssueEdit).filter(IssueEdit.issue_id == uuid.UUID(issue_id), IssueEdit.field == "vehicle_number").one()
    )
    assert json.loads(number.ai_value) == "12가3456"
    assert json.loads(number.final_value) == "99나9999"


def test_permissions_hide_other_issues_and_admin_routes(client: TestClient, accounts) -> None:
    operator = login(client, OPERATOR_NUMBER, OPERATOR_PASSWORD).json()["access_token"]
    other = login(client, OTHER_NUMBER, OTHER_PASSWORD).json()["access_token"]
    admin = login(client, ADMIN_NUMBER, ADMIN_PASSWORD).json()["access_token"]
    created = upload(client, operator)
    issue_id = created.json()["issue_id"]

    assert client.get(f"/api/issues/{issue_id}", headers=auth_header(other)).status_code == 404
    assert client.get(f"/api/issues/{issue_id}/audio", headers=auth_header(other)).status_code == 404
    own_list = client.get("/api/issues", headers=auth_header(operator))
    other_list = client.get("/api/issues", headers=auth_header(other))
    assert issue_id in {item["id"] for item in own_list.json()}
    assert issue_id not in {item["id"] for item in other_list.json()}
    assert client.get(f"/api/issues/{issue_id}", headers=auth_header(admin)).status_code == 200

    assert (
        client.get("/api/summary/weekly", headers=auth_header(operator)).status_code == 422
        or client.get(
            "/api/summary/weekly",
            params={"from": "2026-11-01T00:00:00Z", "to": "2026-11-08T00:00:00Z"},
            headers=auth_header(operator),
        ).status_code
        == 403
    )
    denied = client.get(
        "/api/summary/weekly",
        params={"from": "2026-11-01T00:00:00Z", "to": "2026-11-08T00:00:00Z"},
        headers=auth_header(operator),
    )
    assert denied.status_code == 403
    assert client.get("/api/users", headers=auth_header(operator)).status_code == 403
    assert client.get("/api/users", headers=auth_header(admin)).status_code == 200
    assert client.get("/api/issues", headers=auth_header(admin)).status_code == 200


def test_weekly_summary_matches_sql(client: TestClient, db) -> None:
    admin = login(client, ADMIN_NUMBER, ADMIN_PASSWORD).json()["access_token"]
    first = upload(client, admin)
    second = upload(client, admin)
    end = utcnow() + timedelta(minutes=5)
    start = end - timedelta(days=7)
    recording = db.get(Recording, uuid.UUID(second.json()["recording_id"]))
    assert recording is not None
    recording.recorded_at = start - timedelta(days=1)
    db.commit()

    response = client.get(
        "/api/summary/weekly",
        params={"from": start.isoformat(), "to": end.isoformat()},
        headers=auth_header(admin),
    )
    assert response.status_code == 200, response.text
    stats = response.json()["stats"]
    current = db.scalar(
        select(func.count(Issue.id))
        .join(Recording, Recording.id == Issue.recording_id)
        .where(Recording.recorded_at >= start, Recording.recorded_at < end)
    )
    previous_start = start - (end - start)
    previous = db.scalar(
        select(func.count(Issue.id))
        .join(Recording, Recording.id == Issue.recording_id)
        .where(Recording.recorded_at >= previous_start, Recording.recorded_at < start)
    )
    assert stats["count"] == current
    assert stats["previous_count"] == previous
    assert stats["delta"] == current - previous
    assert str(stats["count"]) in response.json()["narrative"]
    assert first.json()["issue_id"]


def test_upload_stores_original_audio_and_coordinates(client: TestClient, db) -> None:
    token = login(client, OPERATOR_NUMBER, OPERATOR_PASSWORD).json()["access_token"]
    created = upload(client, token)
    assert created.status_code == 200, created.text
    body = created.json()
    recording = db.get(Recording, uuid.UUID(body["recording_id"]))
    issue = db.get(Issue, uuid.UUID(body["issue_id"]))
    assert recording is not None and issue is not None
    assert recording.latitude == 37.5
    assert recording.longitude == 127.0
    assert issue.latitude == 37.5
    assert issue.longitude == 127.0
    assert Path(recording.audio_path).read_bytes() == wav_bytes()


def test_upload_without_coordinates_is_rejected(client: TestClient) -> None:
    token = login(client, OPERATOR_NUMBER, OPERATOR_PASSWORD).json()["access_token"]
    response = client.post(
        "/api/recordings",
        files={"audio": ("sample.wav", wav_bytes(), "audio/wav")},
        headers=auth_header(token),
    )
    assert response.status_code == 422


def test_issue_soft_delete_hides_issue_and_keeps_audio(client: TestClient, db) -> None:
    token = login(client, OPERATOR_NUMBER, OPERATOR_PASSWORD).json()["access_token"]
    created = upload(client, token)
    body = created.json()
    issue_id = body["issue_id"]
    recording = db.get(Recording, uuid.UUID(body["recording_id"]))
    assert recording is not None
    audio_path = Path(recording.audio_path)
    deleted = client.delete(f"/api/issues/{issue_id}", headers=auth_header(token))
    assert deleted.status_code == 204
    assert client.get(f"/api/issues/{issue_id}", headers=auth_header(token)).status_code == 404
    listed = client.get("/api/issues", headers=auth_header(token))
    assert issue_id not in {item["id"] for item in listed.json()}
    issue = db.get(Issue, uuid.UUID(issue_id))
    assert issue is not None and issue.deleted_at is not None
    assert audio_path.is_file()
    assert client.delete(f"/api/issues/{issue_id}", headers=auth_header(token)).status_code == 404
