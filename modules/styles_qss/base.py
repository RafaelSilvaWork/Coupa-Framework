"""Fragmento QSS: chrome global (janela, tooltip, status bar, header, tabs, group boxes)."""

QSS_BASE = """
/* ============================================
   COUPA FRAMEWORK - DARK/TECH THEME v4.0
   ============================================ */

/* --- Global Settings --- */
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: "Segoe UI";
    font-size: 14px;
}

QToolTip {
    background-color: #1c2128;
    color: #e6edf3;
    border: 1px solid #30363d;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
}

/* Header e status bar usam o mesmo fundo do app (#0d1117), não o tom
   "painel" (#161b22) - senão viram duas faixas visivelmente mais claras que
   destoam do resto da tela. A separação visual vem só das bordas. */
QStatusBar {
    background: #0d1117;
    color: #8b949e;
    border-top: 1px solid #30363d;
    font-size: 12px;
}

QLabel#appStatusBarLabel {
    background: transparent;
    color: #8b949e;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 16px;
}

/* --- Header / Barra Superior --- */
QWidget#appHeader {
    background: #0d1117;
    border-bottom: 2px solid #1f6feb;
}

QLabel#appHeaderTitle {
    background: transparent;
    color: #f0f6fc;
    font-size: 17px;
    font-weight: 700;
    padding: 2px 0px;
}

/* Botões de ação do header (Painel, Versões) - sem borda "caixada" contra o
   fundo do header como o #btnClear genérico tem; ficam discretos até o
   hover, igual o título ao lado deles. */
QPushButton#btnHeaderAction {
    background: transparent;
    border: 1px solid transparent;
    color: #8b949e;
    font-weight: 500;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 6px;
    min-width: 28px;
    min-height: 28px;
}

QPushButton#btnHeaderAction:hover {
    background: #1c2128;
    border-color: #3d444d;
    color: #e6edf3;
}

/* --- Tab Widget (Navegação Principal) --- */
QTabWidget::pane {
    border: none;
    background: #0d1117;
    border-top: 1px solid #30363d;
}

QTabBar {
    background: #161b22;
    padding: 0px 12px;
}

QTabBar::tab {
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 12px 20px;
    margin: 0px 4px;
    font-size: 13px;
    font-weight: 600;
    color: #8b949e;
    min-height: 34px;
}

QTabBar::tab:hover {
    background: #1c2128;
    border-radius: 8px 8px 0 0;
    border-bottom: 3px solid #30363d;
    color: #e6edf3;
}

QTabBar::tab:selected {
    background: transparent;
    border-bottom: 3px solid #58a6ff;
    color: #58a6ff;
    font-weight: 700;
}

/* --- Group Boxes (Cards) --- */
QGroupBox {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    margin-top: 22px;
    padding: 22px 18px 16px 18px;
    font-weight: 600;
    font-size: 14px;
    color: #e6edf3;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 5px 16px;
    background: #1f2937;
    color: #58a6ff;
    border: 1px solid #30363d;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 800;
    margin-left: 12px;
}

"""
