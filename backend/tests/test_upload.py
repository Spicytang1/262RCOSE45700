from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import OPERATOR_PASSWORD, auth_header, login, upload, wav_bytes


def _token(client: TestClient) -> str:
    return login(client, "operator1", OPERATOR_PASSWORD).json()["access_token"]


def _stored_files(app) -> list[Path]:
    storage = Path(app.state.settings.storage_dir)
    return list(storage.iterdir()) if storage.exists() else []


def _post_audio(client: TestClient, token: str, filename: str, payload: bytes):
    return client.post(
        "/api/recordings",
        files={"audio": (filename, payload, "application/octet-stream")},
        headers=auth_header(token),
    )


def test_unsupported_extension_is_rejected_and_not_stored(client: TestClient, app) -> None:
    response = _post_audio(client, _token(client), "payload.exe", wav_bytes())
    assert response.status_code == 422
    assert _stored_files(app) == []


def test_missing_extension_is_rejected(client: TestClient, app) -> None:
    response = _post_audio(client, _token(client), "noextension", wav_bytes())
    assert response.status_code == 422
    assert _stored_files(app) == []


def test_oversized_upload_is_rejected_and_removed(client: TestClient, app) -> None:
    app.state.settings.max_upload_mb = 0
    response = upload(client, _token(client))
    assert response.status_code == 413
    assert _stored_files(app) == []


def test_empty_upload_is_rejected_and_removed(client: TestClient, app) -> None:
    response = _post_audio(client, _token(client), "empty.wav", b"")
    assert response.status_code == 422
    assert _stored_files(app) == []


def test_failed_extraction_keeps_audio_and_marks_error(client: TestClient, app) -> None:
    app.state.settings.extractor_provider = "gateway_claude"
    app.state.settings.gateway_api_key = ""
    response = upload(client, _token(client))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "error"
    assert body["transcript"]["corrected_text"]
    assert body["extraction"]["cause"]["value"] is None
    assert "extraction" in body["pipeline_meta"]["errors"]
    assert len(_stored_files(app)) == 1


def test_failed_classification_keeps_transcript(client: TestClient, app) -> None:
    app.state.settings.classifier_provider = "gateway_jev"
    app.state.settings.gateway_api_key = ""
    response = upload(client, _token(client))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "error"
    assert "컷인" in body["transcript"]["corrected_text"]
    assert body["extraction"]["cause"]["value"]
    assert "classification" in body["pipeline_meta"]["errors"]
    assert len(_stored_files(app)) == 1


def test_valid_upload_keeps_audio(client: TestClient, app) -> None:
    response = upload(client, _token(client))
    assert response.status_code == 200
    assert len(_stored_files(app)) == 1
