"""Fragmento QSS: campos de entrada (line edit, text edit, tabela, progress bar, combobox, checkbox/radio)."""

QSS_INPUTS = """
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
"""
