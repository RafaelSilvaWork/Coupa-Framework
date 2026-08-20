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

from modules.styles_qss.base import QSS_BASE
from modules.styles_qss.buttons import QSS_BUTTONS
from modules.styles_qss.inputs import QSS_INPUTS
from modules.styles_qss.labels import QSS_LABELS
from modules.styles_qss.widgets import QSS_WIDGETS


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
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
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


def _sem_quebra_inicial(fragmento: str) -> str:
    """Remove só a quebra de linha introduzida pela abertura do bloco `\"\"\"`."""
    return fragmento[1:] if fragmento.startswith("\n") else fragmento


APP_STYLESHEET = (
    QSS_BASE
    + _sem_quebra_inicial(QSS_BUTTONS)
    + _sem_quebra_inicial(QSS_INPUTS)
    + _sem_quebra_inicial(QSS_LABELS)
    + _sem_quebra_inicial(QSS_WIDGETS)
)
