import json
import sys
from pathlib import Path

MODULE_DEFINITIONS: list[tuple[str, str]] = [
    ("extrator", "📦 Extrator Inteligente"),
    ("downloader", "📥 Baixador de Orçamentos"),
    ("pdf", "📄 Gerador de PDF de Pedidos"),
    ("renomeador", "📝 Renomeador"),
    ("organizador", "🗂️ Organizador"),
    ("email", "📧 Disparo de E-mails"),
    ("perfis", "👥 Gerenciar Perfis"),
]


def _default_selection() -> dict[str, bool]:
    return {name: True for name, _ in MODULE_DEFINITIONS}


def _selection_file_path() -> Path:
    try:
        executable_dir = Path(sys.executable).resolve().parent
    except Exception:
        executable_dir = Path(__file__).resolve().parent.parent
    return executable_dir / "module_selection.json"


def load_enabled_modules() -> dict[str, bool]:
    config_path = _selection_file_path()
    if not config_path.exists():
        return _default_selection()

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw_value = json.load(handle)
    except (json.JSONDecodeError, OSError, TypeError):
        return _default_selection()

    if not isinstance(raw_value, dict):
        return _default_selection()

    selection = _default_selection()
    for module_name, _ in MODULE_DEFINITIONS:
        value = raw_value.get(module_name)
        if isinstance(value, bool):
            selection[module_name] = value
    return selection


def save_enabled_modules(selection: dict[str, bool]) -> Path:
    normalized = {name: bool(selection.get(name, True)) for name, _ in MODULE_DEFINITIONS}
    config_path = _selection_file_path()
    config_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_path


def build_selection_for_modules(module_names: list[str]) -> dict[str, bool]:
    selection = {name: False for name, _ in MODULE_DEFINITIONS}
    for module_name in module_names:
        if module_name in selection:
            selection[module_name] = True
    return selection


def is_module_enabled(module_name: str) -> bool:
    return load_enabled_modules().get(module_name, True)
