"""Fragmento QSS: labels (incl. estados dinâmicos de status), scroll bars e splitter."""

QSS_LABELS = """

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
"""
