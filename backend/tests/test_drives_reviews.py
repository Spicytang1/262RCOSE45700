import uuid

from app.models import Recording
from fastapi.testclient import TestClient

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
)


def _token(client: TestClient, username: str, password: str) -> str:
    return login(client, username, password).json()["access_token"]


def test_drive_start_stays_on_the_open_session_until_end(client: TestClient) -> None:
    token = _token(client, OPERATOR_NUMBER, OPERATOR_PASSWORD)
    headers = auth_header(token)
    first = client.post("/api/drives", headers=headers)
    second = client.post("/api/drives", headers=headers)
    assert first.status_code == 200, first.text
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["number"] == 1
    assert first.json()["ended_at"] is None

    ended = client.post(f"/api/drives/{first.json()['id']}/end", headers=headers)
    assert ended.status_code == 200, ended.text
    again = client.post(f"/api/drives/{first.json()['id']}/end", headers=headers)
    assert again.json()["ended_at"] == ended.json()["ended_at"]

    third = client.post("/api/drives", headers=headers)
    assert third.json()["number"] == 2
    assert third.json()["id"] != first.json()["id"]


def test_drive_is_hidden_from_another_operator_and_visible_to_admin(client: TestClient) -> None:
    owner = _token(client, OPERATOR_NUMBER, OPERATOR_PASSWORD)
    other = _token(client, OTHER_NUMBER, OTHER_PASSWORD)
    admin = _token(client, ADMIN_NUMBER, ADMIN_PASSWORD)
    started = client.post("/api/drives", headers=auth_header(owner))
    drive_id = started.json()["id"]

    hidden = client.post(f"/api/drives/{drive_id}/end", headers=auth_header(other))
    assert hidden.status_code == 404
    own_list = client.get("/api/drives", headers=auth_header(other))
    assert own_list.json() == []
    admin_list = client.get("/api/drives", headers=auth_header(admin))
    assert [item["id"] for item in admin_list.json()] == [drive_id]


def test_upload_attaches_only_an_open_drive(client: TestClient, db) -> None:
    token = _token(client, OPERATOR_NUMBER, OPERATOR_PASSWORD)
    other = _token(client, OTHER_NUMBER, OTHER_PASSWORD)
    started = client.post("/api/drives", headers=auth_header(token))
    drive_id = started.json()["id"]

    denied = upload(client, other, drive_session_id=drive_id)
    assert denied.status_code == 422

    saved = upload(client, token, drive_session_id=drive_id)
    assert saved.status_code == 200, saved.text
    assert saved.json()["drive_session_id"] == drive_id
    recording = db.get(Recording, uuid.UUID(saved.json()["recording_id"]))
    assert recording is not None
    assert str(recording.drive_session_id) == drive_id

    client.post(f"/api/drives/{drive_id}/end", headers=auth_header(token))
    closed = upload(client, token, drive_session_id=drive_id)
    assert closed.status_code == 422


def test_review_save_keeps_audio_and_blocks_other_operator(client: TestClient, db) -> None:
    token = _token(client, OPERATOR_NUMBER, OPERATOR_PASSWORD)
    other = _token(client, OTHER_NUMBER, OTHER_PASSWORD)
    uploaded = upload(client, token)
    recording_id = uploaded.json()["recording_id"]
    recording = db.get(Recording, uuid.UUID(recording_id))
    assert recording is not None
    audio_path = recording.audio_path

    missing = client.get(f"/api/reviews/{recording_id}", headers=auth_header(token))
    assert missing.status_code == 404

    payload = {
        "title": "보행자 급감속",
        "status": "reviewed",
        "note": "확인함",
        "fields": {"roadType": "직선로", "targetType": "보행자"},
        "other_fields": ["reaction"],
        "other_field_values": {"reaction": "수동 감속"},
    }
    saved = client.put(f"/api/reviews/{recording_id}", headers=auth_header(token), json=payload)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["recording_id"] == recording_id
    assert body["fields"]["roadType"] == "직선로"
    assert body["other_field_values"]["reaction"] == "수동 감속"

    payload["note"] = "다시 확인"
    updated = client.put(f"/api/reviews/{recording_id}", headers=auth_header(token), json=payload)
    assert updated.json()["id"] == body["id"]
    assert updated.json()["note"] == "다시 확인"
    listed = client.get("/api/reviews", headers=auth_header(token))
    assert [item["id"] for item in listed.json()] == [body["id"]]

    hidden = client.get(f"/api/reviews/{recording_id}", headers=auth_header(other))
    assert hidden.status_code == 404
    db.refresh(recording)
    assert recording.audio_path == audio_path
    assert db.get(Recording, recording.id).issue is not None
