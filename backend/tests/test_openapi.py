import json

from fastapi.testclient import TestClient

PUBLIC = {
    ("get", "/health"),
    ("post", "/api/auth/login"),
    ("post", "/api/auth/refresh"),
    ("post", "/api/auth/logout"),
}
METHODS = {"get", "post", "patch", "put", "delete"}


def _operations(spec: dict):
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if method in METHODS:
                yield method, path, operation


def test_docs_and_openapi_contract(client: TestClient) -> None:
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "persistAuthorization" in docs.text
    assert client.get("/redoc").status_code == 200

    spec = client.get("/openapi.json").json()
    schemes = spec["components"]["securitySchemes"]
    assert schemes["BearerAuth"]["type"] == "http"
    assert schemes["BearerAuth"]["scheme"] == "bearer"
    assert schemes["RefreshCookie"] == {**schemes["RefreshCookie"], "type": "apiKey", "in": "cookie"}
    assert not any(item.get("type") == "oauth2" for item in schemes.values())

    login = spec["paths"]["/api/auth/login"]["post"]
    assert list(login["requestBody"]["content"]) == ["application/json"]
    assert spec["components"]["schemas"]["LoginRequest"]["required"] == ["code"]

    for method, path, operation in _operations(spec):
        assert operation.get("summary"), path
        assert operation.get("tags"), path
        if (method, path) in PUBLIC:
            continue
        assert operation.get("security"), path
        assert "401" in operation["responses"]


def test_operation_ids_are_explicit_and_unique(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    ids = [operation["operationId"] for _, _, operation in _operations(spec)]
    assert len(ids) == len(set(ids))
    assert all(
        "_api_" not in item and not item.endswith(("_get", "_post", "_patch", "_put", "_delete")) for item in ids
    )
    assert {"login", "listIssues", "trashIssue", "restoreIssue", "deleteIssuePermanently", "getTaxonomy"} <= set(ids)


def test_error_responses_use_shared_schemas(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert "HTTPValidationError" not in json.dumps(spec)
    for method, path, operation in _operations(spec):
        for status, response in operation["responses"].items():
            if not status.startswith(("4", "5")):
                continue
            schema = response["content"]["application/json"]["schema"]["$ref"]
            expected = "UnprocessableBody" if status == "422" else "ErrorBody"
            assert schema.endswith(f"/{expected}"), (method, path, status)


def test_audio_is_binary_and_taxonomy_values_are_enums(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    audio = spec["paths"]["/api/issues/{issue_id}/audio"]["get"]["responses"]["200"]["content"]
    assert audio["audio/wav"]["schema"] == {"type": "string", "format": "binary"}
    assert "application/json" not in audio

    update = spec["components"]["schemas"]["IssueUpdate"]["properties"]
    assert "cut_in" in update["event_type"]["anyOf"][0]["enum"]
    assert "intersection" in update["road_type"]["anyOf"][0]["enum"]
    issue = spec["components"]["schemas"]["IssueOut"]["properties"]
    assert {"trashed_at", "location", "duration_sec", "start_trigger", "drive_session_id"} <= set(issue)
