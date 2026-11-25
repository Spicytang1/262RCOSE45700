import json
import uuid
from datetime import timedelta
from pathlib import Path

from app.domain.taxonomy.loader import choice_keys, event_type_keys, load_taxonomy, severity_keys
from app.models import Issue, IssueEdit, Recording
from app.models.base import utcnow
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests.conftest import (
    ADMIN_CODE,
    OPERATOR_CODE,
    OTHER_CODE,
    auth_header,
    login,
    upload,
    wav_bytes,
)


def test_mock_pipeline_upload_and_owner_comes_from_auth(client: TestClient, accounts, db) -> None:
    logged = login(client, OPERATOR_CODE)
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
    token = login(client, OPERATOR_CODE).json()["access_token"]
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
    token = login(client, OPERATOR_CODE).json()["access_token"]
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
    operator = login(client, OPERATOR_CODE).json()["access_token"]
    other = login(client, OTHER_CODE).json()["access_token"]
    admin = login(client, ADMIN_CODE).json()["access_token"]
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
    admin = login(client, ADMIN_CODE).json()["access_token"]
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
    token = login(client, OPERATOR_CODE).json()["access_token"]
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


def test_upload_without_location_is_saved_with_reason(client: TestClient, db) -> None:
    token = login(client, OPERATOR_CODE).json()["access_token"]
    response = client.post(
        "/api/recordings",
        files={"audio": ("sample.wav", wav_bytes(), "audio/wav")},
        data={"location_status": "denied", "duration_sec": "12.5", "start_trigger": "button"},
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["location"] == {
        "status": "denied",
        "latitude": None,
        "longitude": None,
        "accuracy_m": None,
        "requested_at": None,
        "captured_at": None,
    }
    assert body["duration_sec"] == 12.5
    assert body["start_trigger"] == "button"
    detail = client.get(f"/api/issues/{body['issue_id']}", headers=auth_header(token)).json()
    assert detail["location"]["status"] == "denied"
    assert detail["duration_sec"] == 12.5

    default_reason = client.post(
        "/api/recordings", files={"audio": ("sample.wav", wav_bytes(), "audio/wav")}, headers=auth_header(token)
    )
    assert default_reason.json()["location"]["status"] == "unavailable"


def test_upload_keeps_location_details(client: TestClient) -> None:
    token = login(client, OPERATOR_CODE).json()["access_token"]
    response = upload(
        client,
        token,
        location_accuracy_m="12.5",
        location_requested_at="2026-11-25T01:00:00Z",
        location_captured_at="2026-11-25T01:00:03Z",
    )
    assert response.status_code == 200, response.text
    location = response.json()["location"]
    assert location["status"] == "available"
    assert (location["latitude"], location["longitude"], location["accuracy_m"]) == (37.5, 127.0, 12.5)
    assert location["requested_at"].startswith("2026-11-25T01:00:00")
    assert location["captured_at"].startswith("2026-11-25T01:00:03")


def test_upload_rejects_inconsistent_location(client: TestClient) -> None:
    token = login(client, OPERATOR_CODE).json()["access_token"]
    audio = {"audio": ("sample.wav", wav_bytes(), "audio/wav")}
    cases = [
        {"latitude": "37.5"},
        {"latitude": "37.5", "longitude": "127.0", "location_status": "denied"},
        {"location_status": "available"},
        {"latitude": "91", "longitude": "127.0"},
        {"location_status": "nowhere"},
        {"start_trigger": "voice"},
        {"duration_sec": "-1"},
    ]
    for data in cases:
        response = client.post("/api/recordings", files=audio, data=data, headers=auth_header(token))
        assert response.status_code == 422, data


def test_trash_restore_and_permanent_delete_lifecycle(client: TestClient, db) -> None:
    token = login(client, OPERATOR_CODE).json()["access_token"]
    headers = auth_header(token)
    created = upload(client, token).json()
    issue_id, recording_id = created["issue_id"], created["recording_id"]
    recording = db.get(Recording, uuid.UUID(recording_id))
    assert recording is not None
    audio_path = Path(recording.audio_path)
    client.put(
        f"/api/reviews/{recording_id}",
        json={"title": "검토", "status": "reviewed"},
        headers=headers,
    )

    # 정상 이슈는 바로 영구 삭제할 수 없다.
    assert client.delete(f"/api/issues/{issue_id}", headers=headers).status_code == 409
    assert audio_path.is_file()

    trashed = client.post(f"/api/issues/{issue_id}/trash", headers=headers)
    assert trashed.status_code == 200, trashed.text
    first_time = trashed.json()["trashed_at"]
    assert first_time is not None
    assert client.post(f"/api/issues/{issue_id}/trash", headers=headers).json()["trashed_at"] == first_time

    active = client.get("/api/issues", headers=headers).json()
    in_trash = client.get("/api/issues", params={"trashed": "true"}, headers=headers).json()
    assert issue_id not in {item["id"] for item in active}
    assert [item["id"] for item in in_trash] == [issue_id]
    detail = client.get(f"/api/issues/{issue_id}", headers=headers)
    assert detail.status_code == 200 and detail.json()["trashed_at"] == first_time
    assert client.get(f"/api/issues/{issue_id}/audio", headers=headers).status_code == 200
    assert client.patch(f"/api/issues/{issue_id}", json={"cause": "x"}, headers=headers).status_code == 409
    assert client.get("/api/reviews", headers=headers).json() == []
    assert client.get(f"/api/reviews/{recording_id}", headers=headers).status_code == 404

    restored = client.post(f"/api/issues/{issue_id}/restore", headers=headers)
    assert restored.status_code == 200 and restored.json()["trashed_at"] is None
    assert issue_id in {item["id"] for item in client.get("/api/issues", headers=headers).json()}
    assert len(client.get("/api/reviews", headers=headers).json()) == 1
    assert client.get("/api/issues", params={"trashed": "true"}, headers=headers).json() == []
    assert client.patch(f"/api/issues/{issue_id}", json={"cause": "복원 뒤 수정"}, headers=headers).status_code == 200

    client.post(f"/api/issues/{issue_id}/trash", headers=headers)
    assert client.delete(f"/api/issues/{issue_id}", headers=headers).status_code == 204
    assert client.get(f"/api/issues/{issue_id}", headers=headers).status_code == 404
    assert client.get("/api/issues", params={"trashed": "true"}, headers=headers).json() == []
    assert client.post(f"/api/issues/{issue_id}/restore", headers=headers).status_code == 404
    assert client.delete(f"/api/issues/{issue_id}", headers=headers).status_code == 404
    db.expire_all()
    assert db.get(Issue, uuid.UUID(issue_id)) is None
    assert db.get(Recording, uuid.UUID(recording_id)) is None
    assert db.query(IssueEdit).filter(IssueEdit.issue_id == uuid.UUID(issue_id)).count() == 0
    assert not audio_path.exists()


def test_trash_is_scoped_to_owner_and_excluded_from_summary(client: TestClient) -> None:
    operator = login(client, OPERATOR_CODE).json()["access_token"]
    other = login(client, OTHER_CODE).json()["access_token"]
    admin = login(client, ADMIN_CODE).json()["access_token"]
    issue_id = upload(client, operator).json()["issue_id"]

    assert client.post(f"/api/issues/{issue_id}/trash", headers=auth_header(other)).status_code == 404
    assert client.delete(f"/api/issues/{issue_id}", headers=auth_header(other)).status_code == 404

    window = {"from": (utcnow() - timedelta(days=7)).isoformat(), "to": (utcnow() + timedelta(days=1)).isoformat()}
    before = client.get("/api/summary/weekly", params=window, headers=auth_header(admin)).json()["stats"]["count"]
    client.post(f"/api/issues/{issue_id}/trash", headers=auth_header(operator))
    after = client.get("/api/summary/weekly", params=window, headers=auth_header(admin)).json()["stats"]["count"]
    assert (before, after) == (1, 0)
    assert issue_id in {
        item["id"] for item in client.get("/api/issues", params={"trashed": "true"}, headers=auth_header(admin)).json()
    }
    assert client.delete(f"/api/issues/{issue_id}", headers=auth_header(admin)).status_code == 204


def test_taxonomy_endpoint_matches_yaml_and_accepts_only_listed_keys(client: TestClient) -> None:
    token = login(client, OPERATOR_CODE).json()["access_token"]
    assert client.get("/api/taxonomy").status_code == 401
    body = client.get("/api/taxonomy", headers=auth_header(token)).json()
    taxonomy = load_taxonomy()
    assert body["version"] == taxonomy.version
    assert [item["key"] for item in body["event_types"]] == event_type_keys()
    assert [item["key"] for item in body["severity_levels"]] == severity_keys()
    assert {item["label"] for item in body["event_types"]} >= {"끼어들기", "급제동"}
    assert [group["id"] for group in body["guide"]] == ["road_type", "ego_action_before", "target_type", "ego_reaction"]
    assert [group["review_field"] for group in body["guide"]] == [
        "roadType",
        "previousAction",
        "targetType",
        "reaction",
    ]
    assert [option["key"] for option in body["guide"][0]["options"]] == choice_keys("road_type")
    assert "keywords" not in str(body)

    issue_id = upload(client, token).json()["issue_id"]
    bad = client.patch(f"/api/issues/{issue_id}", json={"event_type": "not_in_taxonomy"}, headers=auth_header(token))
    assert bad.status_code == 422
    assert client.get("/api/issues", params={"event_type": "nope"}, headers=auth_header(token)).status_code == 422
    good = client.get("/api/issues", params={"event_type": "cut_in"}, headers=auth_header(token))
    assert good.status_code == 200
