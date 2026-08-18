"""
Test account management endpoints
"""
import pytest


def test_list_accounts(client):
    """Test listing accounts"""
    response = client.get("/api/v1/accounts/")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert data["success"] is True
    assert "items" in data
    assert "total" in data


def test_account_stats(client):
    """Test account statistics"""
    response = client.get("/api/v1/accounts/stats/summary")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert data["success"] is True
    assert "data" in data
    stats = data["data"]
    assert "total" in stats
    assert "valid" in stats
    assert "error" in stats
    assert "by_platform" in stats


def test_filter_accounts_by_platform(client):
    """Test filtering accounts by platform"""
    response = client.post(
        "/api/v1/accounts/filter",
        json={"platform": "douyin"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "items" in data


def test_filter_accounts_by_status(client):
    """Test filtering accounts by status"""
    response = client.post(
        "/api/v1/accounts/filter",
        json={"status": "valid"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "items" in data
