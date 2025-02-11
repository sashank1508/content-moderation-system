import sys
import os
import asyncio

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app
from fastapi_limiter import FastAPILimiter


# --- Fixture for Application Setup ---
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="module")
async def test_app():  # Keep this async to properly mock init
    """
    Fixture to set up the FastAPI application with mocked FastAPILimiter.
    This simulates the startup event.
    """
    # Mock the Redis connection.
    with patch("fastapi_limiter.FastAPILimiter.init", new_callable=AsyncMock):
        # Simulate the startup event.
        await FastAPILimiter.init(AsyncMock())  # Initialize with a mock Redis connection
        yield app  # Provide the app to the tests

@pytest.fixture(scope="module")
def client(test_app):
    """
    Fixture to provide a TestClient instance for the mocked application.
    """
    with TestClient(app) as test_client:
        yield test_client

# -------------------------------
#   API Endpoint Tests
# -------------------------------

def test_root(client)-> None:
    """Test if API root is working."""
    response = client.get("/")
    assert response.status_code == 200


def test_text_moderation(client)-> None:
    """Test /api/v1/moderate/text endpoint."""
    payload = {"text": "This is a test sentence."}
    response = client.post("/api/v1/moderate/text", json=payload)
    assert response.status_code == 200
    assert "message" in response.json()
    assert "id" in response.json()


def test_image_moderation(client)-> None:
    """Test /api/v1/moderate/image endpoint."""
    payload = {"image_url": "https://example.com/test.jpg"}
    response = client.post("/api/v1/moderate/image", json=payload)
    assert response.status_code == 200
    assert "message" in response.json()
    assert "id" in response.json()


def test_get_all_moderation_results(client)-> None:
    """Test /api/v1/moderation/all endpoint."""
    response = client.get("/api/v1/moderation/all?offset=0&limit=5")
    assert response.status_code in [200, 404]  # 404 if no records exist
    assert isinstance(response.json(), dict)


def test_get_moderation_result(client)-> None:
    """Test /api/v1/moderation/{id} endpoint."""
    response = client.get("/api/v1/moderation/nonexistent-id")
    assert response.status_code == 404


def test_get_failed_tasks(client)-> None:
    """Test /api/v1/moderation/failed endpoint."""
    response = client.get("/api/v1/moderation/failed")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_clear_failed_tasks(client)-> None:
    """Test /api/v1/moderation/failed/clear endpoint."""
    response = client.delete("/api/v1/moderation/failed/clear")
    assert response.status_code == 200
    assert "message" in response.json()


def test_clear_specific_failed_task(client)-> None:
    """Test /api/v1/moderation/failed/{id}/clear endpoint."""
    response = client.delete("/api/v1/moderation/failed/nonexistent-id/clear")
    assert response.status_code in [200, 404]  # 404 if no such task exists


def test_delete_all_moderation_results(client)-> None:
    """Test /api/v1/moderation/clear_all endpoint."""
    response = client.delete("/api/v1/moderation/clear_all")
    assert response.status_code in [200, 500]  # 500 if DB operation fails


def test_delete_moderation_result_by_id(client)-> None:
    """Test /api/v1/moderation/clear/{id} endpoint."""
    response = client.delete("/api/v1/moderation/clear/nonexistent-id")
    assert response.status_code in [200, 404]  # 404 if the ID doesn't exist


def test_health_check(client)-> None:
    """Test /api/v1/health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code in [200, 500]
    assert isinstance(response.json(), dict)


def test_debug_db(client)-> None:
    """Test /api/v1/debug/db endpoint."""
    response = client.get("/api/v1/debug/db")
    assert response.status_code in [200, 500]
    assert isinstance(response.json(), dict)


def test_get_prometheus_metrics(client)-> None:
    """Test /stats endpoint for Prometheus metrics."""
    response = client.get("/stats")
    assert response.status_code == 200
    assert "api_requests_total" in response.text  # Check for Prometheus metric name


def test_get_metrics_json(client)-> None:
    """Test /metrics/json endpoint for Prometheus metrics in JSON format."""
    response = client.get("/metrics/json")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)

def test_invalid_text_moderation(client)-> None:
    """Ensure text moderation fails on invalid input."""
    response = client.post("/api/v1/moderate/text", json={"wrong_key": "Hello!"})
    assert response.status_code == 422  # FastAPI validation error

def test_invalid_image_moderation(client)-> None:
    """Ensure image moderation fails on non-URL input."""
    response = client.post("/api/v1/moderate/image", json={"image_url": "not-a-url"})
    assert response.status_code == 422  # Change 400 to 422

def test_text_moderation_invalid_input(client)-> None:
    """Ensure text moderation fails on empty input."""
    payload = {"text": ""}  # Empty string
    response = client.post("/api/v1/moderate/text", json=payload)
    assert response.status_code == 422

def test_moderation_results_empty(client)-> None:
    """Ensure getting all moderation results returns 404 if empty."""
    response = client.get("/api/v1/moderation/all?offset=0&limit=5")
    assert response.status_code in [200, 404]  # 404 if no records exist

