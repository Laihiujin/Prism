"""
Test other module endpoints
"""
import pytest


def test_recovery_health(client):
    """Test recovery module health"""
    response = client.get("/api/v1/recovery/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["module"] == "recovery"


def test_scripts_list(client):
    """Test listing available scripts"""
    response = client.get("/api/v1/scripts/list")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "success"
    assert "scripts" in data
    assert isinstance(data["scripts"], list)


def test_campaigns_ping(client):
    """Test campaigns ping"""
    response = client.get("/api/v1/campaigns/ping")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


def test_tasks_health(client):
    """Test tasks health endpoint"""
    response = client.get("/api/v1/tasks/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "enabled" in data


def test_ai_status(client):
    """Test AI status endpoint"""
    response = client.get("/api/v1/ai/status")
    # May return 400 if AI not configured, or 200 if it is
    assert response.status_code in [200, 400]
