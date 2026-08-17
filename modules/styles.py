"""Tema dark/tech do Coupa Framework.

Folha de estilo global (QSS) + uns utilitários pra manter a aparência
consistente em todas as abas. Visual escuro, inspirado em VS Code / GitHub Dark.

Paleta de Cores:
  - Background App:     #0d1117  (fundo principal)
  - Background Painel:  #161b22  (cards, grupos, inputs)
  - Background Elevado: #1c2128  (hover / elementos elevados)
  - Border:             #30363d
  - Border Hover:       #3d444d
  - Accent Primary:     #58a6ff  (azul - ações padrão / foco)
  - Accent Primary Dk:  #388bfd
  - Accent Cyan:        #22d3ee  (detalhes / progresso)
  - Success:            #3fb950  (verde)
  - Warning:             #d29922 (âmbar)
  - Danger:              #f85149 (vermelho)
  - Text Primary:        #e6edf3
  - Text Secondary:      #8b949e
  - Text Muted:          #6e7681

Uso do helper `set_status`:
    from modules.styles import set_status
    set_status(self.lbl_status, "success")   # também: "error", "warning", "muted", "normal"
"""

from PyQt6.QtWidgets import QWidget, QScrollArea, QFrame
from PyQt6.QtCore import Qt


def set_status(widget: QWidget, status: str, text: str | None = None) -> None:
    """Aplica um estado visual (cor/estilo) a um QLabel via propriedade QSS.

    Substitui o padrão antigo de `label.setStyleSheet("color: ...")`, que
    fixava cores incompatíveis com o tema escuro. Em vez disso, define a
    propriedade dinâmica `status` e força o Qt a reprocessar o estilo.

    Args:
        widget: o QLabel (ou outro QWidget) a estilizar.
        status: um de "success", "error", "warning", "muted", "normal", "accent".
        text: se informado, também atualiza o texto do widget.
    """
    if text is not None and hasattr(widget, "setText"):
        widget.setText(text)
    widget.setProperty("status", status)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def scrollable(content: QWidget) -> QScrollArea:
    """Envolve um QWidget (geralmente um painel com vários QGroupBox) em uma
    QScrollArea transparente.

    Sem isso, quando a janela não está maximizada e o conteúdo de uma aba
    é mais alto do que o espaço disponível, o Qt pode ser forçado a
    espremer widgets abaixo do seu tamanho mínimo — o que causa
    sobreposição visual (botões/labels "grudados" uns nos outros) em vez de
    simplesmente cortar. Com a QScrollArea, o painel ganha uma barra de
    rolagem vertical nesses casos, e o layout nunca precisa comprimir
    abaixo do mínimo de cada widget.

    Args:
        content: o QWidget cujo conteúdo (já com seu layout definido) deve
            se tornar rolável.
    """
    scroll = QScrollArea()
    scroll.setWidget(content)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    return scroll


APP_STYLESHEET = """
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

/* Line Edit / Input Fields */
QLineEdit {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 13px;
    color: #e6edf3;
    selection-background-color: #1f6feb;
    selection-color: white;
    min-height: 18px;
}

QLineEdit:focus {
    border: 1.5px solid #58a6ff;
    padding: 8.5px 11.5px;
}

QLineEdit:disabled {
    background: #161b22;
    color: #484f58;
}

QLineEdit::placeholder {
    color: #6e7681;
}

/* Text Edit / QTextEdit */
QTextEdit {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 13px;
    color: #e6edf3;
    selection-background-color: #1f6feb;
    selection-color: white;
}

QTextEdit:focus {
    border: 1.5px solid #58a6ff;
}

/* Read-only / Log areas - Terminal look */
QTextEdit[readOnly="true"] {
    background: #010409;
    color: #c9d1d9;
    border: 1px solid #21262d;
    font-family: "Consolas";
    font-size: 13px;
}

/* Table Widget */
QTableWidget {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    gridline-color: #21262d;
    selection-background-color: #1f2937;
    selection-color: #58a6ff;
    font-size: 13px;
}

QTableWidget::item {
    padding: 9px 10px;
    border-bottom: 1px solid #21262d;
}

QTableWidget::item:selected {
    background: #1f2937;
    color: #58a6ff;
    font-weight: 600;
}

QTableWidget::item:hover {
    background: #161b22;
}

QHeaderView::section {
    background: #161b22;
    color: #8b949e;
    padding: 11px 10px;
    border: none;
    border-right: 1px solid #21262d;
    border-bottom: 1px solid #30363d;
    font-weight: 700;
    font-size: 11px;
}

/* Progress Bar */
QProgressBar {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 12px;
    text-align: center;
    font-size: 11px;
    font-weight: 700;
    color: #e6edf3;
    min-height: 20px;
    max-height: 20px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #1f6feb, stop:1 #22d3ee);
    border-radius: 12px;
}

/* ComboBox */
QComboBox {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 13px;
    font-weight: 500;
    color: #e6edf3;
    min-width: 140px;
    min-height: 18px;
}

QComboBox:hover {
    border-color: #58a6ff;
}

QComboBox:focus {
    border: 1.5px solid #58a6ff;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border-left: 1px solid #30363d;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}

QComboBox::down-arrow {
    image: none;
    width: 0;
    height: 0;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #8b949e;
    margin-right: 10px;
}

QComboBox QAbstractItemView {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    selection-background-color: #1f2937;
    selection-color: #58a6ff;
    padding: 6px;
    outline: none;
    font-family: "Segoe UI";
    font-size: 13px;
    color: #e6edf3;
}

/* CheckBox / RadioButton */
QCheckBox, QRadioButton {
    spacing: 10px;
    font-size: 13px;
    font-weight: 500;
    color: #e6edf3;
    min-height: 22px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 2px solid #484f58;
    background: #0d1117;
}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #58a6ff;
    background: #1f2937;
}

QCheckBox::indicator:checked {
    background: #1f6feb;
    border-color: #1f6feb;
    image: none;
}

QRadioButton::indicator {
    border-radius: 10px;
}

QRadioButton::indicator:checked {
    background: #1f6feb;
    border-color: #1f6feb;
}

/* Labels */
QLabel {
    color: #e6edf3;
    font-size: 13px;
    font-weight: 500;
    padding: 2px 0px;
}

QLabel#titleLabel {
    font-size: 19px;
    font-weight: 800;
    color: #f0f6fc;
    padding: 6px 0px;
}

QLabel#statusLabel {
    font-style: italic;
    color: #8b949e;
    font-size: 12px;
    padding: 4px 0px;
}

/* Estados dinâmicos de status (ver helper set_status em modules.styles) */
QLabel[status="muted"] {
    color: #8b949e;
    font-style: italic;
    font-weight: 500;
}

QLabel[status="normal"] {
    color: #e6edf3;
    font-style: normal;
    font-weight: 500;
}

QLabel[status="success"] {
    color: #3fb950;
    font-style: normal;
    font-weight: 700;
}

QLabel[status="error"] {
    color: #f85149;
    font-style: normal;
    font-weight: 700;
}

QLabel[status="warning"] {
    color: #d29922;
    font-style: normal;
    font-weight: 700;
}

QLabel[status="accent"] {
    color: #58a6ff;
    font-style: normal;
    font-weight: 700;
}

/* Scroll Bars - Minimalistas */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border: none;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #484f58;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border: none;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #30363d;
    border-radius: 4px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #484f58;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Splitter / Layout spacing */
QSplitter::handle {
    background: #30363d;
    width: 2px;
}

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
