from unittest.mock import patch

from modules.config import _LEGACY_PBKDF2_ITERATIONS, ProfileManager, _get_fernet, decrypt_value, encrypt_value


def test_encrypt_decrypt_roundtrip():
    original = "senha_secreta"
    encrypted = encrypt_value(original)
    assert encrypted != original
    assert decrypt_value(encrypted) == original


def test_decrypt_falls_back_to_legacy_pbkdf2_iterations(tmp_path):
    # Simula um valor criptografado antes do aumento de PBKDF2_ITERATIONS -
    # decrypt_value precisa continuar lendo perfis salvos por versões
    # anteriores do app em vez de perder o acesso a eles silenciosamente.
    config_path = tmp_path / "profiles.json"
    salt_path = config_path.with_suffix(".salt")
    with patch("modules.config.CONFIG_FILE", config_path):
        legacy_encrypted = _get_fernet(_LEGACY_PBKDF2_ITERATIONS).encrypt(b"senha_antiga").decode("utf-8")
        assert decrypt_value(legacy_encrypted) == "senha_antiga"
    salt_path.unlink(missing_ok=True)


def test_decrypt_plaintext_passthrough():
    # Valores sem prefixo Fernet devem ser retornados sem erro
    assert decrypt_value("texto_plano") == "texto_plano"


def test_save_and_load_profiles(tmp_path):
    config_path = tmp_path / "profiles.json"
    salt_path = tmp_path / "profiles.salt"

    profiles = {
        "Perfil Teste": {
            "config": {
                "sender": "user@example.com",
                "password": "secret123",
                "criado_por": True,
            }
        }
    }

    with patch("modules.config.CONFIG_FILE", config_path), \
         patch("modules.config.salt_file", salt_path, create=True):
        ProfileManager.save_profiles(profiles)
        loaded = ProfileManager.load_profiles()

    assert "Perfil Teste" in loaded
    assert loaded["Perfil Teste"]["config"]["sender"] == "user@example.com"
    assert loaded["Perfil Teste"]["config"]["password"] == "secret123"


def test_load_profiles_missing_file(tmp_path):
    with patch("modules.config.CONFIG_FILE", tmp_path / "nao_existe.json"):
        result = ProfileManager.load_profiles()
    assert result == {}
