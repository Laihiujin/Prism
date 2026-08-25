from automation.gemini_computer_use import GeminiComputerUseRecovery
from platforms.registry import normalize_platform_code


def test_tiktok_and_youtube_platform_codes_are_registered():
    assert normalize_platform_code("tiktok") == 6
    assert normalize_platform_code("youtube") == 7
    assert normalize_platform_code("yt") == 7


def test_computer_use_is_opt_in(monkeypatch):
    monkeypatch.delenv("PRISM_GEMINI_COMPUTER_USE_ENABLED", raising=False)
    recovery = GeminiComputerUseRecovery(api_key="test")

    assert recovery.enabled is False
