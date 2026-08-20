"""Fragmento QSS: estilos específicos por objectName.

Cobre pastaLabel, botões de login, card de módulo bloqueado e btnClear.
"""

QSS_WIDGETS = """

/* --- Specific Widget ObjectName Styles --- */

/* Folder path label (selected path display) */
QLabel#pastaLabel {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e6edf3;
    font-size: 12px;
}

/* Edge/Login buttons (big action buttons) */
QPushButton#btnOpenEdge {
    background: #238636;
    border: 1px solid #2ea043;
    color: white;
    font-weight: 700;
    font-size: 13px;
    padding: 13px 20px;
    border-radius: 8px;
    min-height: 42px;
}

QPushButton#btnOpenEdge:hover {
    background: #2ea043;
}

QPushButton#btnOpenEdge:pressed {
    background: #196c2e;
}

QPushButton#btnConfirmLogin {
    background: #1f6feb;
    border: 1px solid #388bfd;
    color: white;
    font-weight: 700;
    font-size: 13px;
    padding: 13px 20px;
    border-radius: 8px;
    min-height: 42px;
}

QPushButton#btnConfirmLogin:hover {
    background: #388bfd;
}

QPushButton#btnConfirmLogin:pressed {
    background: #1158c7;
}

QPushButton#btnConfirmLogin:disabled,
QPushButton#btnOpenEdge:disabled {
    background: #21262d;
    border-color: #30363d;
    color: #484f58;
}

/* Card da tela de "módulo bloqueado" (não instalado / falhou ao carregar) */
QFrame#lockedModuleCard {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 16px;
}

QLabel#lockedModuleIcon {
    background: #1c2128;
    border-radius: 34px;
    font-size: 30px;
    min-width: 68px;
    max-width: 68px;
    min-height: 68px;
    max-height: 68px;
    qproperty-alignment: AlignCenter;
}

QLabel#lockedModuleIcon[status="warning"] {
    background: rgba(210, 153, 34, 0.12);
}

QLabel#lockedModuleTitle {
    font-size: 18px;
    font-weight: 800;
    color: #f0f6fc;
}

QLabel#lockedModuleDesc {
    font-size: 13px;
    color: #8b949e;
}

/* Small outline buttons (compat: mantém btnClear como alias de btnClearField) */
QPushButton#btnClear {
    background: transparent;
    border: 1px solid #30363d;
    color: #8b949e;
    font-weight: 500;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
    min-width: 28px;
    min-height: 28px;
}

QPushButton#btnClear:hover {
    background: #1c2128;
    border-color: #3d444d;
    color: #e6edf3;
}
"""
