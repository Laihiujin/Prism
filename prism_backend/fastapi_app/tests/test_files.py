"""
Test file management endpoints
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fastapi_app.core.config import settings
from fastapi_app.main import app
from fastapi_app.api.v1.files.services import FileService
from fastapi_app.db.session import get_main_db


def test_list_files(client):
    """Test listing files"""
    response = client.get("/api/v1/files/")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_file_stats(client):
    """Test file statistics"""
    response = client.get("/api/v1/files/stats/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_files" in data
    assert "total_size_mb" in data


def test_filter_files_by_status(client):
    """Test filtering files by status"""
    response = client.get("/api/v1/files/?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data


def test_filter_files_by_group(client):
    """Test filtering files by group"""
    response = client.get("/api/v1/files/?group=AI")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data


def test_get_file_not_found(client):
    """Test getting non-existent file"""
    response = client.get("/api/v1/files/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_save_record_with_local_video(test_db_pool):
    """
    Ensure we can register an existing local video into the material library.
    Uses the already-downloaded assets under videoFile to avoid synthetic fixtures.
    """
    sample_dir = Path(settings.VIDEO_FILES_DIR)
    sample_file = next(sample_dir.glob("*.mp4"), None)

    if not sample_file:
        pytest.skip("No sample video found in videoFile directory")

    service = FileService()
    filesize_mb = sample_file.stat().st_size / (1024 * 1024)

    with test_db_pool.get_connection() as conn:
        new_id = await service.save_file_record(
            conn,
            filename=sample_file.name,
            file_path=str(sample_file),
            filesize_mb=round(filesize_mb, 2),
            note="test-import",
            group_name="auto-test",
        )

    assert new_id > 0


def test_upload_and_save_endpoint_with_local_video(test_db_pool):
    """
    Exercise the upload-save API using a real local video and a temp database,
    ensuring the endpoint wiring works for the material library.
    """
    sample_dir = Path(settings.VIDEO_FILES_DIR)
    sample_file = next(sample_dir.glob("*.mp4"), None)

    if not sample_file:
        pytest.skip("No sample video found in videoFile directory")

    saved_path = None

    def override_get_db():
        with test_db_pool.get_connection() as conn:
            yield conn

    app.dependency_overrides[get_main_db] = override_get_db

    try:
        with sample_file.open("rb") as f, TestClient(app) as local_client:
            custom_name = f"custom_{sample_file.stem}.mp4"
            response = local_client.post(
                "/api/v1/files/upload-save",
                files={"file": (sample_file.name, f, "video/mp4")},
                data={"note": "test upload", "group": "auto-test", "filename": custom_name},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload.get("success") is True
        assert payload["data"]["filename"] == custom_name
        saved_path = payload["data"]["file_path"]
        assert Path(saved_path).name != sample_file.name  # unique file name

    finally:
        app.dependency_overrides.pop(get_main_db, None)
        if saved_path and Path(saved_path).exists():
            Path(saved_path).unlink()
