
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton,
    QVBoxLayout, QLabel, QDialog, QLineEdit, QHBoxLayout,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt,
    QEasingCurve,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QRect,
    QPoint,
)


class TelaEdicaoPopup(QDialog):
    def __init__(self, texto_atual, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Editar Campo")
        self.setModal(True)
        self.setFixedSize(320, 140)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.FramelessWindowHint
        )

        # Efeito de opacidade
        self.efeito_opacidade = QGraphicsOpacityEffect(self)
        self.efeito_opacidade.setOpacity(1.0)
        self.setGraphicsEffect(self.efeito_opacidade)

        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                border: 2px solid #4a4a4a;
                border-radius: 12px;
            }
            QLabel {
                background-color: transparent;
                color: #ffffff;
                font-size: 13px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #3b3b3b;
                color: #ffffff;
                border: 1px solid #5a5a5a;
                border-radius: 6px;
                padding: 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QPushButton {
                color: #ffffff;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton#btnSalvar {
                background-color: #0078d4;
            }
            QPushButton#btnSalvar:hover {
                background-color: #1085e0;
            }
            QPushButton#btnSalvar:disabled {
                background-color: #555555;
                color: #888888;
            }
            QPushButton#btnCancelar {
                background-color: #444444;
                border: 1px solid #5a5a5a;
            }
            QPushButton#btnCancelar:hover {
                background-color: #555555;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("Digite o novo valor:"))

        self.input_campo = QLineEdit()
        self.input_campo.setText(texto_atual)
        layout.addWidget(self.input_campo)

        layout_botoes = QHBoxLayout()

        self.btn_salvar = QPushButton("Salvar")
        self.btn_salvar.setObjectName("btnSalvar")

        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("btnCancelar")

        layout_botoes.addWidget(self.btn_salvar)
        layout_botoes.addWidget(btn_cancelar)
        layout.addLayout(layout_botoes)

        self.btn_salvar.clicked.connect(self.accept)
        btn_cancelar.clicked.connect(self.reject)

        self.input_campo.textChanged.connect(self.validar_campo)
        self.validar_campo(texto_atual)

        # Mantém as animações referenciadas durante toda a execução
        self.grupo_animacao = None

    def showEvent(self, event):
        super().showEvent(event)

        # Geometria final já posicionada pelo método abrir_popup()
        geometria_final = self.geometry()

        # Geometria inicial: menor e centralizada
        reducao_largura = 20
        reducao_altura = 10

        geometria_inicial = QRect(
            geometria_final.x() + reducao_largura // 2,
            geometria_final.y() + reducao_altura // 2,
            geometria_final.width() - reducao_largura,
            geometria_final.height() - reducao_altura,
        )

        # Zoom
        self.anim_zoom = QPropertyAnimation(self, b"geometry", self)
        self.anim_zoom.setDuration(180)
        self.anim_zoom.setStartValue(geometria_inicial)
        self.anim_zoom.setEndValue(geometria_final)
        self.anim_zoom.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Fade-in
        self.anim_fade = QPropertyAnimation(
            self.efeito_opacidade, b"opacity", self
        )
        self.anim_fade.setDuration(180)
        self.anim_fade.setStartValue(0.0)
        self.anim_fade.setEndValue(1.0)
        self.anim_fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Executa as animações simultaneamente
        self.grupo_animacao = QParallelAnimationGroup(self)
        self.grupo_animacao.addAnimation(self.anim_zoom)
        self.grupo_animacao.addAnimation(self.anim_fade)
        self.grupo_animacao.start()

    def validar_campo(self, texto):
        self.btn_salvar.setEnabled(bool(texto.strip()))

    def obter_texto(self):
        return self.input_campo.text()


class JanelaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Janela Principal")
        self.resize(500, 400)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #888888;
                font-size: 16px;
            }
        """)

        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        layout = QVBoxLayout(widget_central)

        layout.addWidget(QLabel(
            "Texto de fundo 1 (Fica atrás do pop-up)",
            alignment=Qt.AlignmentFlag.AlignCenter,
        ))

        self.lbl_valor = QLabel(
            "Texto Original",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.lbl_valor.setStyleSheet(
            "color: white; font-weight: bold; font-size: 20px;"
        )
        layout.addWidget(self.lbl_valor)

        layout.addWidget(QLabel(
            "Texto de fundo 2 (Fica atrás do pop-up)",
            alignment=Qt.AlignmentFlag.AlignCenter,
        ))

        btn_editar = QPushButton("Editar Campo")
        btn_editar.setStyleSheet("""
            padding: 10px;
            font-size: 14px;
            background-color: #333333;
            color: white;
            border: 1px solid #555555;
        """)
        btn_editar.clicked.connect(self.abrir_popup)
        layout.addWidget(btn_editar)

    def abrir_popup(self):
        popup = TelaEdicaoPopup(self.lbl_valor.text(), self)

        # Centro da janela principal em coordenadas globais
        centro = self.mapToGlobal(
            QPoint(self.width() // 2, self.height() // 2)
        )

        popup.move(
            centro.x() - popup.width() // 2,
            centro.y() - popup.height() // 2,
        )

        resultado = popup.exec()

        if resultado == QDialog.DialogCode.Accepted:
            self.lbl_valor.setText(popup.obter_texto())


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = JanelaPrincipal()
    window.show()

    sys.exit(app.exec())
