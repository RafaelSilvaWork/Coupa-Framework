"""Fragmento QSS: botões (padrão, primary, success, danger, warning, clear field)."""

QSS_BUTTONS = """
/* --- Buttons --- */
QPushButton {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 600;
    color: #e6edf3;
    min-height: 30px;
}

QPushButton:hover {
    background: #30363d;
    border-color: #3d444d;
}

QPushButton:pressed {
    background: #1c2128;
}

QPushButton:disabled {
    background: #161b22;
    color: #484f58;
    border-color: #21262d;
}

/* Primary Action Buttons (Azul) */
QPushButton#btnPrimary,
QPushButton#btnIniciar,
QPushButton#btnGerar,
QPushButton#btnEnviar,
QPushButton#btnSend,
QPushButton#btnAnalisar,
QPushButton#btnExecutar,
QPushButton#btnConfirmar {
    background: #1f6feb;
    border: 1px solid #388bfd;
    color: white;
    font-weight: 700;
    font-size: 14px;
    padding: 11px 26px;
    border-radius: 8px;
    min-height: 38px;
}

QPushButton#btnPrimary:hover,
QPushButton#btnIniciar:hover,
QPushButton#btnGerar:hover,
QPushButton#btnEnviar:hover,
QPushButton#btnSend:hover,
QPushButton#btnAnalisar:hover,
QPushButton#btnExecutar:hover,
QPushButton#btnConfirmar:hover {
    background: #388bfd;
}

QPushButton#btnPrimary:pressed,
QPushButton#btnIniciar:pressed,
QPushButton#btnGerar:pressed,
QPushButton#btnEnviar:pressed,
QPushButton#btnSend:pressed,
QPushButton#btnAnalisar:pressed,
QPushButton#btnExecutar:pressed,
QPushButton#btnConfirmar:pressed {
    background: #1158c7;
}

QPushButton#btnPrimary:disabled,
QPushButton#btnIniciar:disabled,
QPushButton#btnGerar:disabled,
QPushButton#btnEnviar:disabled,
QPushButton#btnSend:disabled,
QPushButton#btnAnalisar:disabled,
QPushButton#btnExecutar:disabled,
QPushButton#btnConfirmar:disabled {
    background: #21262d;
    border-color: #30363d;
    color: #484f58;
}

/* Success Buttons (Verde) */
QPushButton#btnSuccess,
QPushButton#btnSalvar,
QPushButton#btnRenomear,
QPushButton#btnDownload {
    background: #238636;
    border: 1px solid #2ea043;
    color: white;
    font-weight: 700;
    font-size: 14px;
    padding: 11px 26px;
    border-radius: 8px;
    min-height: 38px;
}

QPushButton#btnSuccess:hover,
QPushButton#btnSalvar:hover,
QPushButton#btnRenomear:hover,
QPushButton#btnDownload:hover {
    background: #2ea043;
}

QPushButton#btnSuccess:pressed,
QPushButton#btnSalvar:pressed,
QPushButton#btnRenomear:pressed,
QPushButton#btnDownload:pressed {
    background: #196c2e;
}

QPushButton#btnSuccess:disabled,
QPushButton#btnSalvar:disabled,
QPushButton#btnRenomear:disabled,
QPushButton#btnDownload:disabled {
    background: #21262d;
    border-color: #30363d;
    color: #484f58;
}

/* Danger / Cancel Buttons (Vermelho) */
QPushButton#btnDanger,
QPushButton#btnCancelar,
QPushButton#btnDelete,
QPushButton#btnLimpar {
    background: #da3633;
    border: 1px solid #f85149;
    color: white;
    font-weight: 700;
    font-size: 13px;
    padding: 9px 20px;
    border-radius: 8px;
    min-height: 34px;
}

QPushButton#btnDanger:hover,
QPushButton#btnCancelar:hover,
QPushButton#btnDelete:hover,
QPushButton#btnLimpar:hover {
    background: #f85149;
}

QPushButton#btnDanger:pressed,
QPushButton#btnCancelar:pressed,
QPushButton#btnDelete:pressed,
QPushButton#btnLimpar:pressed {
    background: #a52a2a;
}

QPushButton#btnDanger:disabled,
QPushButton#btnCancelar:disabled,
QPushButton#btnDelete:disabled,
QPushButton#btnLimpar:disabled {
    background: #21262d;
    border-color: #30363d;
    color: #484f58;
}

/* Warning / Pause Buttons (Âmbar) */
QPushButton#btnWarning,
QPushButton#btnPausar,
QPushButton#btnRecarregar {
    background: #9e6a03;
    border: 1px solid #d29922;
    color: white;
    font-weight: 700;
    font-size: 13px;
    padding: 9px 20px;
    border-radius: 8px;
    min-height: 34px;
}

QPushButton#btnWarning:hover,
QPushButton#btnPausar:hover,
QPushButton#btnRecarregar:hover {
    background: #d29922;
}

QPushButton#btnWarning:pressed,
QPushButton#btnPausar:pressed,
QPushButton#btnRecarregar:pressed {
    background: #7a5202;
}

/* Botão outline pequeno para "Limpar campo" (não destrutivo em si) */
QPushButton#btnClearField {
    background: transparent;
    border: 1px solid #30363d;
    color: #f85149;
    font-weight: 700;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
    min-width: 28px;
    min-height: 28px;
}

QPushButton#btnClearField:hover {
    background: rgba(248, 81, 73, 0.12);
    border-color: #f85149;
    color: #ff7b72;
}

"""
