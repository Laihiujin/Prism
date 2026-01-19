"""
Test data center endpoints
"""
import pytest


def test_data_health(client):
    """Test data center health"""
    response = client.get("/api/v1/data/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"


def test_data_center_summary(client):
    """Test data center summary"""
    response = client.get("/api/v1/data/center")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "data" in data
    assert "totals" in data["data"]


def test_data_videos(client):
    """Test data videos endpoint"""
    response = client.get("/api/v1/data/videos")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "items" in data


def test_data_trends(client):
    """Test data trends"""
    response = client.get("/api/v1/data/trends")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "series" in data
    assert isinstance(data["series"], list)


def test_publish_status(client):
    """Test publish status statistics"""
    response = client.get("/api/v1/data/publish-status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "data" in data
    stats = data["data"]
    assert "total" in stats
    assert "published" in stats
    assert "pending" in stats
