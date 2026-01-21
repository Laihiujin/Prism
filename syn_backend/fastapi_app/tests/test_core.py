"""
Test system core endpoints
"""
import pytest


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["version"] == "2.0.0"


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "2.0.0"
    assert "timestamp" in data


def test_api_ping(client):
    """Test ping endpoint"""
    response = client.get("/api/v1/ping")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "pong"


def test_openapi_spec(client):
    """Test OpenAPI specification"""
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert data["info"]["title"] == "SynapseAutomation API"
    assert data["info"]["version"] == "2.0.0"
    assert "paths" in data
    # Check that we have a reasonable number of endpoints
    assert len(data["paths"]) > 50


def test_docs_endpoint(client):
    """Test Swagger UI docs endpoint"""
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert b"swagger-ui" in response.content.lower()


def test_redoc_endpoint(client):
    """Test ReDoc endpoint"""
    response = client.get("/api/redoc")
    assert response.status_code == 200
    assert b"redoc" in response.content.lower()
