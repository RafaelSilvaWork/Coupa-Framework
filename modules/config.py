import json
import os
import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

try:
    from dotenv import load_dotenv
    load_dotenv()  # lê o .env da raiz do projeto, se existir (não versionado)
except ImportError:
    pass  # python-dotenv não instalado - segue usando só variáveis de ambiente do sistema

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT_ROOT / "coupa_profiles.json"
INSTANCE_CONFIG_FILE = PROJECT_ROOT / "coupa_instance.json"
POWER_AUTOMATE_CONFIG_FILE = PROJECT_ROOT / "coupa_power_automate.json"

# Connection string do Azure Application Insights usada para telemetria de erros.
# Fica vazia em código-fonte (telemetria desligada) — o workflow de release no
# GitHub Actions substitui esta linha pelo valor do secret APPINSIGHTS_CONNECTION_STRING
# antes de compilar o executável, então o valor real nunca fica no histórico do git.
APPINSIGHTS_CONNECTION_STRING = ""


@dataclass(frozen=True)
class FrameworkSettings:
    """Configuração centralizada do framework com defaults seguros e tipados."""

    project_root: Path = PROJECT_ROOT
    config_file: Path = CONFIG_FILE
    coupa_base_url: str = os.environ.get("COUPA_BASE_URL", "https://sua-instancia.coupahost.com")
    map_fornecedores: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MAP_FORNECEDORES", str(PROJECT_ROOT / "mapeamento_fornecedores.xlsx"))
        )
    )
    map_unidades: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MAP_UNIDADES", str(PROJECT_ROOT / "mapeamento_unidades.xlsx"))
        )
    )
    map_solicitantes: Path = field(
        default_factory=lambda: Path(
            os.environ.get("MAP_SOLICITANTES", str(PROJECT_ROOT / "mapeamento_solicitantes.xlsx"))
        )
    )
    pasta_saida_padrao_pdf: Path = field(default_factory=lambda: PROJECT_ROOT / "saida_pedidos_pdf")
    perfil_edge_download: Path = field(
        default_factory=lambda: Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        / "CoupaFramework"
        / "PerfilEdgeDownload"
    )
    historico_renomeador: Path = field(
        default_factory=lambda: Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        / "CoupaFramework"
        / "historico_renomeador.csv"
    )
    textos_sem_documento: tuple[str, ...] = ("AGUARDE, EM PROCESSAMENTO!",)
    margens_impressao: Dict[str, str] = field(
        default_factory=lambda: {"top": "0.4in", "bottom": "0.4in", "left": "0.4in", "right": "0.4in"}
    )
    max_tentativas: int = 3
    espera_entre_tentativas: int = 1
    palavras_chave: tuple[str, ...] = (
        "orçamento", "orcamento", "proposta", "cotação", "cotacao", "quotation", "budget",
    )


SETTINGS = FrameworkSettings()

COUPA_BASE_URL = SETTINGS.coupa_base_url
MAP_FORNECEDORES = SETTINGS.map_fornecedores
MAP_UNIDADES = SETTINGS.map_unidades
MAP_SOLICITANTES = SETTINGS.map_solicitantes
PASTA_SAIDA_PADRAO_PDF = SETTINGS.pasta_saida_padrao_pdf
PERFIL_EDGE_DOWNLOAD = SETTINGS.perfil_edge_download
HISTORICO_RENOMEADOR = SETTINGS.historico_renomeador
TEXTOS_SEM_DOCUMENTO = SETTINGS.textos_sem_documento
MARGENS_IMPRESSAO = SETTINGS.margens_impressao
MAX_TENTATIVAS = SETTINGS.max_tentativas
ESPERA_ENTRE_TENTATIVAS = SETTINGS.espera_entre_tentativas
PALAVRAS_CHAVE = SETTINGS.palavras_chave


def _normalize_coupa_base_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def _load_coupa_instance_override() -> str:
    """Lê a instância do Coupa declarada pelo usuário via UI (Gerenciar Perfis), se houver."""
    if not INSTANCE_CONFIG_FILE.exists():
        return ""
    try:
        with open(INSTANCE_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("coupa_base_url", "")).strip()
    except (json.JSONDecodeError, OSError):
        return ""


def get_saved_coupa_instance() -> str:
    """Retorna a instância salva pelo usuário via UI, ou string vazia se nunca foi declarada."""
    return _load_coupa_instance_override()


def get_coupa_base_url() -> str:
    """Retorna a instância do Coupa em uso: a declarada pelo usuário na UI tem prioridade
    sobre a variável de ambiente COUPA_BASE_URL / valor padrão de placeholder."""
    return _load_coupa_instance_override() or COUPA_BASE_URL


def set_coupa_base_url(url: str) -> str:
    """Salva a instância do Coupa declarada pelo usuário na UI. Retorna a URL normalizada."""
    normalized = _normalize_coupa_base_url(url)
    with open(INSTANCE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"coupa_base_url": normalized}, f, indent=2, ensure_ascii=False)
    return normalized


def get_power_automate_url() -> str:
    """Retorna a URL do flow do Power Automate usado para disparo de e-mail
    (compartilhada por todos os compradores), ou string vazia se nunca foi
    configurada. Guardada criptografada (mesmo esquema de encrypt_value) -
    essa URL funciona como uma senha: quem a tiver consegue disparar e-mails
    pelo flow sem login nenhum.
    """
    if not POWER_AUTOMATE_CONFIG_FILE.exists():
        return ""
    try:
        with open(POWER_AUTOMATE_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return decrypt_value(str(data.get("url", "")).strip())
    except (json.JSONDecodeError, OSError):
        return ""


def set_power_automate_url(url: str) -> str:
    """Salva (criptografada) a URL do flow do Power Automate. Retorna a URL normalizada."""
    normalized = (url or "").strip()
    with open(POWER_AUTOMATE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"url": encrypt_value(normalized)}, f, indent=2, ensure_ascii=False)
    return normalized


def get_url_teste_login() -> str:
    return f"{get_coupa_base_url().rstrip('/')}/"


def get_url_base_impressao_pdf(pedido: str) -> str:
    return f"{get_coupa_base_url().rstrip('/')}/order_headers/show_custom/{pedido}?version=1"


def resolve_edge_executable() -> str | None:
    candidates = [
        os.environ.get("EDGE_EXECUTABLE_PATH"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


# ---- Crypto helpers for ProfileManager ----

def _get_secret() -> bytes:
    """Retorna o segredo usado na derivação da chave de criptografia.

    Melhoria 7: remove o fallback hardcoded "troque-este-valor-no-ambiente".
    Agora:
      1. Usa COUPA_FW_SECRET se definida no ambiente (recomendado).
      2. Caso contrário, gera/persiste uma chave aleatória por máquina no
         arquivo ``coupa_fw.secret`` (na raiz do projeto), evitando chave
         previsível e conhecida publicamente.
    """
    secret_env = os.environ.get("COUPA_FW_SECRET")
    if secret_env:
        return secret_env.encode("utf-8")

    secret_file = PROJECT_ROOT / "coupa_fw.secret"
    try:
        if secret_file.exists():
            return secret_file.read_bytes()
        secret = os.urandom(32)
        secret_file.write_bytes(secret)
        return secret
    except OSError:
        # Se não conseguir persistir, gera uma chave efêmera (perde acesso
        # aos dados criptografados anteriormente, mas não usa segredo fixo).
        return os.urandom(32)


# PBKDF2_ITERATIONS segue a recomendação atual da OWASP para PBKDF2-HMAC-SHA256
# (revisada para cima em relação às 100_000 usadas antes). Perfis já
# criptografados com o valor antigo NÃO ficam ilegíveis: decrypt_value tenta
# o valor atual e, se falhar, cai para _LEGACY_PBKDF2_ITERATIONS antes de
# desistir - e o valor é regravado com o número de iterações atual na
# próxima vez que o perfil for salvo (ProfileManager.save_profiles sempre
# chama encrypt_value, que já usa PBKDF2_ITERATIONS).
PBKDF2_ITERATIONS = 600_000
_LEGACY_PBKDF2_ITERATIONS = 100_000


def _derive_key(salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    """Deriva uma chave AES a partir de um salt fixo + identificador da máquina."""
    machine_id = os.environ.get("COMPUTERNAME", "DEFAULT-MACHINE").encode("utf-8")
    # Melhoria 7: usa COUPA_FW_SECRET ou chave aleatória persistente por máquina.
    secret = _get_secret()
    # amazonq-ignore-next-line
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt + machine_id,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret))


def _get_fernet(iterations: int = PBKDF2_ITERATIONS) -> 'Fernet':
    salt_file = CONFIG_FILE.with_suffix(".salt")
    if salt_file.exists():
        salt = salt_file.read_bytes()
    else:
        salt = os.urandom(16)
        salt_file.write_bytes(salt)
    return Fernet(_derive_key(salt, iterations))


SENSITIVE_FIELDS = ["comprador_email", "template", "sender", "password"]


def encrypt_value(plaintext: str) -> str:
    """Criptografa um valor sensível."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_value(ciphertext: str) -> str:
    """Descriptografa um valor sensível."""
    if not ciphertext:
        return ciphertext
    # Valores em texto plano não começam com o prefixo Fernet - retorna sem tentar descriptografar
    if not ciphertext.startswith("gAAAA"):
        return ciphertext
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        pass  # tenta a chave legada abaixo antes de desistir
    try:
        # Compatibilidade com perfis gravados antes do aumento de
        # PBKDF2_ITERATIONS (ver comentário acima da constante).
        return _get_fernet(_LEGACY_PBKDF2_ITERATIONS).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("decrypt_value falhou: %s", e)
        return ciphertext


def encrypt_sensitive_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Percorre o config e criptografa campos sensíveis."""
    encrypted = dict(config)
    for campo in SENSITIVE_FIELDS:
        if campo in encrypted and encrypted[campo]:
            encrypted[campo] = encrypt_value(str(encrypted[campo]))
    return encrypted

# amazonq-ignore-next-line

def decrypt_sensitive_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Percorre o config e descriptografa campos sensíveis."""
    decrypted = dict(config)
    for campo in SENSITIVE_FIELDS:
        if campo in decrypted and decrypted[campo]:
            decrypted[campo] = decrypt_value(str(decrypted[campo]))
    return decrypted


class ProfileManager:
    @staticmethod
    def load_profiles() -> Dict[str, Any]:
        """Carrega perfis do arquivo JSON com descriptografia de campos sensíveis."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    raw_profiles = json.load(f)
                # Descriptografa os configs sensíveis de cada perfil
                for profile_data in raw_profiles.values():
                    if "config" in profile_data:
                        profile_data["config"] = decrypt_sensitive_config(profile_data["config"])
                return raw_profiles
            except (json.JSONDecodeError, OSError, KeyError) as e:
                import logging
                logging.getLogger(__name__).error("Erro ao carregar perfis: %s", e)
                return {}
        return {}

    @staticmethod
    def save_profiles(profiles: Dict[str, Any]):
        """Salva perfis no arquivo JSON com criptografia de campos sensíveis."""
        # Criptografa os configs sensíveis de cada perfil antes de salvar
        encrypted_profiles = {}
        for profile_name, profile_data in profiles.items():
            encrypted_data = dict(profile_data)
            if "config" in encrypted_data:
                encrypted_data["config"] = encrypt_sensitive_config(encrypted_data["config"])
            encrypted_profiles[profile_name] = encrypted_data

        temp_path = CONFIG_FILE.with_suffix(CONFIG_FILE.suffix + ".tmp")
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(encrypted_profiles, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        # Usa os.replace() que é atômico no Windows e sobrescreve sem PermissionError
        os.replace(str(temp_path), str(CONFIG_FILE))

