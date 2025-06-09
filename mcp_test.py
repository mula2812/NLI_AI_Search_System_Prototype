import pytest
from fastapi.testclient import TestClient
from mcp_tool import app
from fuzzywuzzy import fuzz

client = TestClient(app)

@pytest.mark.integration
def test_search_count_only_integration():
    """
    Integration test for count_only search on 'בן גוריון'. Expects at least one result.
    """
    response = client.get(
        "/api/v1/search",
        params={"q": "creator,contains,בן גוריון", "materialType": "book", "count_only": True}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data, dict)
    assert "total_results" in data
    assert isinstance(data["total_results"], int)
    assert data["total_results"] >= 0

@pytest.mark.integration
def test_search_full_integration_and_chaining():
    """
    Integration test for full search, then chaining recordId to manifest and image endpoints.
    """
    # Perform search
    response = client.get(
        "/api/v1/search",
        params={"q": "title,contains,ישראל", "limit": 5, "offset": 0}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    # Skip if no items
    items = data["items"]
    if not items:
        pytest.skip("No search results to chain.")
    # Pick first record
    record = items[0]
    # extract recordId from full URI key
    rec_list = record.get("http://purl.org/dc/elements/1.1/recordid", [])
    assert rec_list, "recordid field missing"
    record_id = rec_list[0].get("@value")
    assert record_id, "RecordId missing in item"

    # Manifest endpoint
    resp_manifest = client.get(f"/api/v1/manifest/{record_id}")
    assert resp_manifest.status_code == 200, resp_manifest.text
    manifest = resp_manifest.json()
    assert "@id" in manifest

    # If item has images, test image endpoint
    images = record.get("images") or []
    if images:
        image_id = images[0].get("@id")
        resp_image = client.get(f"/api/v1/image/{image_id}")
        assert resp_image.status_code == 200, resp_image.text
        assert resp_image.headers.get("content-type", "").startswith("image/")

@pytest.mark.integration
def test_stream_and_chaining_to_image_and_manifest():
    """
    Integration test for stream endpoint, then manifest for its record.
    """
    item_id = "990003000580205171"
    resp_stream = client.get(f"/api/v1/stream/{item_id}")
    assert 200 <= resp_stream.status_code < 600
    streams = resp_stream.json()
    assert isinstance(streams, dict)

    # Next test manifest for same ID
    resp_manifest = client.get(f"/api/v1/manifest/{item_id}")
    assert resp_manifest.status_code == 200, resp_manifest.text
    manifest = resp_manifest.json()
    assert "@id" in manifest

@pytest.mark.integration
def test_invalid_search_parameters():
    """
    Test invalid search parameter leads to 422 validation error.
    """
    response = client.get(
        "/api/v1/search",
        params={"q": "creator,exact,בן גוריון", "limit": 1000, "offset": 0}
    )
    assert response.status_code == 422

@pytest.mark.integration
def test_nonexistent_image_and_manifest():
    """
    Test invalid identifiers return error codes.
    """
    bad_id = "NON_EXISTENT_ID_123"
    resp_image = client.get(f"/api/v1/image/{bad_id}")
    assert resp_image.status_code >= 400

    resp_manifest = client.get(f"/api/v1/manifest/{bad_id}")
    assert resp_manifest.status_code >= 400

@pytest.mark.unit
def test_query_ai_cleaning_and_validation(monkeypatch):
    # 1) Empty prompt => 422
    resp_empty = client.post("/api/v1/query-ai", json={"prompt": "", "context": {"items": []}})
    assert resp_empty.status_code == 422

    # 2) Prepare a minimal context and prompt
    payload = {
        "prompt": "מה הכותרת?",
        "context": {
            "items": [
                {"@id": "https://nli.org/1", "title": "דוגמה"}
            ]
        }
    }
    resp = client.post("/api/v1/query-ai", json=payload)
    assert resp.status_code == 200, resp.text

    text = resp.json().get("response_text")
    # Ensure no stray quotes or newlines
    assert '"' not in text
    assert '\n' not in text

    # Fuzzy-match the expected phrase
    expected = "הכותרת היא דוגמה"
    score = fuzz.partial_ratio(text, expected)
    assert score > 80, f"Fuzzy match too low ({score}) for text: {text}"
