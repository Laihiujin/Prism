from fastapi_app.agent import hermes_update


def test_update_preferences_are_stored_in_preserved_home(monkeypatch, tmp_path):
    home = tmp_path / "hermes-home"
    monkeypatch.setattr(hermes_update, "get_hermes_home_path", lambda: home)

    saved = hermes_update.save_update_settings(enabled=False, interval_hours=12, branch="dev")

    assert saved == {"enabled": False, "interval_hours": 12, "branch": "dev"}
    assert hermes_update.get_update_settings() == saved
    assert (home / "update-settings.json").exists()


def test_update_interval_is_bounded(monkeypatch, tmp_path):
    monkeypatch.setattr(hermes_update, "get_hermes_home_path", lambda: tmp_path)

    saved = hermes_update.save_update_settings(enabled=True, interval_hours=999, branch="")

    assert saved["interval_hours"] == 168
    assert saved["branch"] == "main"
