from unittest.mock import patch

from modules.config import get_power_automate_url, set_power_automate_url


def test_get_power_automate_url_returns_empty_when_never_configured(tmp_path):
    with patch("modules.config.CONFIG_FILE", tmp_path / "profiles.json"), \
         patch("modules.config.POWER_AUTOMATE_CONFIG_FILE", tmp_path / "power_automate.json"):
        assert get_power_automate_url() == ""


def test_set_and_get_power_automate_url_roundtrip(tmp_path):
    url = "https://example.com/workflows/abc/triggers/manual/paths/invoke?sig=segredo123"
    with patch("modules.config.CONFIG_FILE", tmp_path / "profiles.json"), \
         patch("modules.config.POWER_AUTOMATE_CONFIG_FILE", tmp_path / "power_automate.json"):
        set_power_automate_url(url)
        assert get_power_automate_url() == url


def test_power_automate_url_is_stored_encrypted_on_disk(tmp_path):
    url = "https://example.com/workflows/abc/triggers/manual/paths/invoke?sig=segredo123"
    power_automate_file = tmp_path / "power_automate.json"
    with patch("modules.config.CONFIG_FILE", tmp_path / "profiles.json"), \
         patch("modules.config.POWER_AUTOMATE_CONFIG_FILE", power_automate_file):
        set_power_automate_url(url)

    conteudo_bruto = power_automate_file.read_text(encoding="utf-8")
    assert "segredo123" not in conteudo_bruto
    assert url not in conteudo_bruto


def test_set_power_automate_url_strips_whitespace(tmp_path):
    with patch("modules.config.CONFIG_FILE", tmp_path / "profiles.json"), \
         patch("modules.config.POWER_AUTOMATE_CONFIG_FILE", tmp_path / "power_automate.json"):
        normalizado = set_power_automate_url("  https://example.com/invoke  ")
        assert normalizado == "https://example.com/invoke"
        assert get_power_automate_url() == "https://example.com/invoke"
