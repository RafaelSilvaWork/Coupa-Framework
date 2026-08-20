"""Logger centralizado do framework.

Padroniza timestamp, nivel (INFO, WARNING, ERROR) e cores em todos os widgets.
Elimina a duplicacao de codigo de formatacao de log que existia em 5 widgets diferentes.

Uso:
    from modules.logger import UILogger
    UILogger.info(txt_logs, "Mensagem")
    UILogger.warning(txt_logs, "Aviso")
    UILogger.error(txt_logs, "Erro")
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtWidgets import QTextEdit


def _setup_file_logger() -> logging.Logger:
    """Item 4: Configura RotatingFileHandler em %APPDATA%\\CoupaFramework\\logs\\."""
    log_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "CoupaFramework" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "coupa_framework.log"

    logger = logging.getLogger("CoupaFramework")
    if logger.handlers:
        return logger  # já configurado

    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(
        log_file,
        maxBytes=2 * 1024 * 1024,  # 2 MB por arquivo
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    return logger


_file_logger = _setup_file_logger()


class UILogger:
    """Utilitario de logging padronizado para areas de log (QTextEdit).

    Fornece 3 niveis com prefixos e cores distintas:
    - INFO (azul): informacoes gerais
    - WARNING (amarelo): avisos
    - ERROR (vermelho): erros
    """

    @staticmethod
    def _format(level: str, color: str, msg: str) -> str:
        horario = datetime.now().strftime("%H:%M:%S")
        return (
            f'<span style="color: #94a3b8;">[{horario}]</span> '
            f'<span style="color: {color}; font-weight: bold;">[{level}]</span> '
            f'<span style="color: #e2e8f0;">{msg}</span>'
        )

    @staticmethod
    def info(log_widget: QTextEdit | None, msg: str) -> None:
        """Loga uma mensagem informativa (azul claro)."""
        _file_logger.info(msg)
        if log_widget is None:
            return
        html = UILogger._format("INFO", "#60a5fa", msg)
        log_widget.append(html)

    @staticmethod
    def warning(log_widget: QTextEdit | None, msg: str) -> None:
        """Loga um aviso (amarelo)."""
        _file_logger.warning(msg)
        if log_widget is None:
            return
        html = UILogger._format("AVISO", "#fbbf24", msg)
        log_widget.append(html)

    @staticmethod
    def error(log_widget: QTextEdit | None, msg: str) -> None:
        """Loga um erro (vermelho)."""
        _file_logger.error(msg)
        if log_widget is None:
            return
        html = UILogger._format("ERRO", "#f87171", msg)
        log_widget.append(html)

    @staticmethod
    def success(log_widget: QTextEdit | None, msg: str) -> None:
        """Loga uma mensagem de sucesso (verde)."""
        _file_logger.info(msg)
        if log_widget is None:
            return
        html = UILogger._format("OK", "#4ade80", msg)
        log_widget.append(html)

    @staticmethod
    def plain(log_widget: QTextEdit | None, msg: str) -> None:
        """Loga mensagem em texto plano (sem HTML), compatível com logs antigos."""
        _file_logger.info(msg)
        if log_widget is None:
            return
        horario = datetime.now().strftime("%H:%M:%S")
        log_widget.append(f"[{horario}] {msg}")

    @staticmethod
    def auto(log_widget: QTextEdit | None, msg: str) -> None:
        """Detecta o nível automaticamente por emoji/palavra-chave e loga."""
        if log_widget is None:
            return
        msg_lower = msg.lower()
        eh_erro = "❌" in msg or "✖" in msg or ("erro" in msg_lower and msg_lower.startswith("erro"))
        eh_sucesso = (
            "✅" in msg or "🎉" in msg or "🏁" in msg or "🔒" in msg or "🔓" in msg
            or "concluí" in msg_lower or "concluido" in msg_lower
            or "finalizado" in msg_lower or "sucesso" in msg_lower
        )
        if eh_erro:
            UILogger.error(log_widget, msg)
        elif "⚠️" in msg or "aviso" in msg_lower or "atenção" in msg_lower or "atencao" in msg_lower:
            UILogger.warning(log_widget, msg)
        elif eh_sucesso:
            UILogger.success(log_widget, msg)
        else:
            UILogger.info(log_widget, msg)

