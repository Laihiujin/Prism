"""
Test analytics endpoints
"""
import pytest


def test_get_analytics(client):
    """Test getting analytics data"""
    response = client.get("/api/v1/analytics/")
    assert response.status_code == 200
    data = response.json()
    assert "code" in data
    assert data["code"] == 200
    assert "summary" in data
    assert "videos" in data
    assert "chartData" in data


def test_get_analytics_with_date_filter(client):
    """Test getting analytics with date filter"""
    response = client.get("/api/v1/analytics/?startDate=2025-01-01&endDate=2025-12-31")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200


def test_analytics_export_csv(client):
    """Test exporting analytics as CSV"""
    response = client.get("/api/v1/analytics/export?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


def test_analytics_export_excel(client):
    """Test exporting analytics as Excel"""
    response = client.get("/api/v1/analytics/export?format=excel")
    assert response.status_code == 200
    # Will either be Excel or fall back to CSV if openpyxl not available
    assert "text/csv" in response.headers["content-type"] or "spreadsheet" in response.headers["content-type"]
