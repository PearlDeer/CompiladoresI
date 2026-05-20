"""
IDE para Compilador - Entorno de Desarrollo Integrado
=====================================================
Interfaz grafica modular que invoca a un compilador externo.
El compilador funciona de forma independiente (system call).
Comunicacion IDE <-> Compilador via archivos temporales / parametros.
"""

import sys
import os
import subprocess
import json
import tempfile
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QWidget,
    QDockWidget, QTabWidget, QFileDialog, QToolBar,
    QStatusBar, QLabel, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QMessageBox,
    QTextEdit
)
from PyQt6.QtGui import (
    QAction, QPainter, QColor, QTextFormat, QFont,
    QSyntaxHighlighter, QTextCharFormat, QIcon, QKeySequence,
    QTextCursor
)
from PyQt6.QtCore import Qt, QRect, QSize, QRegularExpression, QProcess


# =============================================================================
# Paleta de colores del IDE
# =============================================================================
class Colores:
    FONDO_PRINCIPAL     = "#1b1f24"   # Fondo del editor (gris azulado oscuro)
    FONDO_PANEL         = "#161a1e"   # Paneles
    FONDO_BARRA         = "#121519"   # Barras
    FONDO_LINEA_NUM     = "#1b1f24"   # Fondo nÃºmeros de lÃ­nea
    FONDO_LINEA_ACTUAL  = "#242a30"   # LÃ­nea actual

    TEXTO               = "#d0d7de"   # Texto principal
    TEXTO_SECUNDARIO    = "#9aa4ad"   # Texto secundario
    TEXTO_LINEA_NUM     = "#6e7681"   # NÃºmeros de lÃ­nea

    ACENTO              = "#4f7cff"   # Azul sobrio
    ACENTO_HOVER        = "#6b8cff"

    VERDE               = "#5fb3a2"   # Ã‰xito / tokens vÃ¡lidos
    AMARILLO            = "#c9b458"   # Advertencias
    ROJO                = "#d16969"   # Errores
    NARANJA             = "#d7a55f"   # NÃºmeros / constantes
    ROSA                = "#c586c0"   # Strings
    LAVANDA             = "#8aa3ff"   # Keywords

    BORDE               = "#2a2f36"   # Bordes
    SELECCION           = "#30363d"   # SelecciÃ³n
    TAB_ACTIVO          = "#1b1f24"   # Tab activo
    TAB_INACTIVO        = "#161a1e"   # Tab inactivo


# =============================================================================
# Hoja de estilos global
# =============================================================================
STYLESHEET = f"""
QMainWindow {{
    background-color: {Colores.FONDO_PRINCIPAL};
}}

QMenuBar {{
    background-color: {Colores.FONDO_BARRA};
    color: {Colores.TEXTO};
    border-bottom: 1px solid {Colores.BORDE};
    padding: 2px 0px;
    font-size: 13px;
}}

QMenuBar::item {{
    padding: 6px 12px;
    border-radius: 4px;
    margin: 2px 1px;
}}

QMenuBar::item:selected {{
    background-color: {Colores.SELECCION};
}}

QMenu {{
    background-color: {Colores.FONDO_PANEL};
    color: {Colores.TEXTO};
    border: 1px solid {Colores.BORDE};
    border-radius: 6px;
    padding: 4px;
}}

QMenu::item {{
    padding: 6px 30px 6px 12px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {Colores.SELECCION};
}}

QMenu::separator {{
    height: 1px;
    background-color: {Colores.BORDE};
    margin: 4px 8px;
}}

QToolBar {{
    background-color: {Colores.FONDO_BARRA};
    border-bottom: 1px solid {Colores.BORDE};
    padding: 4px 8px;
    spacing: 4px;
}}

QToolBar QToolButton {{
    background-color: transparent;
    color: {Colores.TEXTO};
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}}

QToolBar QToolButton:hover {{
    background-color: {Colores.SELECCION};
    border-color: {Colores.BORDE};
}}

QToolBar QToolButton:pressed {{
    background-color: {Colores.ACENTO};
    color: {Colores.FONDO_BARRA};
}}

QToolBar::separator {{
    width: 1px;
    background-color: {Colores.BORDE};
    margin: 4px 6px;
}}

QDockWidget {{
    color: {Colores.TEXTO};
    titlebar-close-icon: none;
    font-size: 12px;
}}

QDockWidget::title {{
    background-color: {Colores.FONDO_BARRA};
    padding: 8px 12px;
    border: 1px solid {Colores.BORDE};
    border-radius: 0px;
    font-weight: bold;
    text-align: left;
}}

QTabWidget::pane {{
    background-color: {Colores.FONDO_PANEL};
    border: 1px solid {Colores.BORDE};
    border-top: none;
}}

QTabBar::tab {{
    background-color: {Colores.TAB_INACTIVO};
    color: {Colores.TEXTO_SECUNDARIO};
    padding: 8px 18px;
    border: 1px solid {Colores.BORDE};
    border-bottom: none;
    margin-right: 1px;
    font-size: 12px;
}}

QTabBar::tab:selected {{
    background-color: {Colores.TAB_ACTIVO};
    color: {Colores.ACENTO};
    border-bottom: 2px solid {Colores.ACENTO};
}}

QTabBar::tab:hover:!selected {{
    background-color: {Colores.SELECCION};
    color: {Colores.TEXTO};
}}

QTableWidget {{
    background-color: {Colores.FONDO_PANEL};
    color: {Colores.TEXTO};
    border: none;
    gridline-color: {Colores.BORDE};
    font-size: 12px;
    selection-background-color: {Colores.SELECCION};
}}

QTableWidget::item {{
    padding: 4px 8px;
    border-bottom: 1px solid {Colores.BORDE};
}}

QHeaderView::section {{
    background-color: {Colores.FONDO_BARRA};
    color: {Colores.TEXTO_SECUNDARIO};
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid {Colores.BORDE};
    font-weight: bold;
    font-size: 11px;
    text-transform: uppercase;
}}

QTreeWidget {{
    background-color: {Colores.FONDO_PANEL};
    color: {Colores.TEXTO};
    border: none;
    font-size: 12px;
    selection-background-color: {Colores.SELECCION};
}}

QTreeWidget::item {{
    padding: 3px 0px;
}}

QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {{
    border-image: none;
}}

QTextEdit, QPlainTextEdit {{
    background-color: {Colores.FONDO_PANEL};
    color: {Colores.TEXTO};
    border: none;
    font-size: 13px;
    selection-background-color: {Colores.SELECCION};
}}

QStatusBar {{
    background-color: {Colores.FONDO_BARRA};
    color: {Colores.TEXTO_SECUNDARIO};
    border-top: 1px solid {Colores.BORDE};
    font-size: 12px;
    padding: 2px;
}}

QStatusBar QLabel {{
    color: {Colores.TEXTO_SECUNDARIO};
    padding: 0px 12px;
    font-size: 12px;
}}

QScrollBar:vertical {{
    background-color: {Colores.FONDO_PANEL};
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {Colores.SELECCION};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {Colores.TEXTO_LINEA_NUM};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {Colores.FONDO_PANEL};
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {Colores.SELECCION};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {Colores.TEXTO_LINEA_NUM};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

QSplitter::handle {{
    background-color: {Colores.BORDE};
}}

QMessageBox {{
    background-color: {Colores.FONDO_PANEL};
    color: {Colores.TEXTO};
}}

QMessageBox QLabel {{
    color: {Colores.TEXTO};
}}
"""


# =============================================================================
# Resaltador de sintaxis basico
# =============================================================================
class ResaltadorSintaxis(QSyntaxHighlighter):
    """Resaltador de sintaxis para el editor.

    Colores segun PDF (Fase Analisis Lexico):
        Color 1 - Numeros enteros y reales       -> NARANJA (#d7a55f)
        Color 2 - Identificadores                 -> VERDE (#5fb3a2)
        Color 3 - Comentarios (una y multi linea) -> GRIS ITALICA (#6e7681)
        Color 4 - Palabras reservadas             -> LAVANDA (#8aa3ff) bold
                  if, else, end, do, while, switch, case, int, float, main, cin, cout
        Color 5 - Operadores aritmeticos          -> CYAN (#6b8cff)
                  +, -, *, /, %, ^, ++, --
        Color 6 - Operadores relacionales/logicos -> AMARILLO (#c9b458)
                  <, <=, >, >=, !=, ==, &&, ||, !
        
        Sin color especifico:
        - Simbolos: (, ), {, }, ,, ;
        - Asignacion: =
        - Cadenas "..." y Caracteres '...'        -> ROSA (#c586c0)
    
    NOTA: El orden de las reglas importa. Se aplican en secuencia y las
    ultimas sobrescriben a las anteriores. Por eso:
    1. Primero numeros (para que 32.0 en "32.0algo" se coloree)
    2. Luego identificadores (para que "algo" despues del numero se coloree)
    3. Finalmente keywords (para sobrescribir identificadores que son reservados)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.reglas = []

        # Guardamos los formatos para uso posterior
        self.fmt_keyword = QTextCharFormat()
        self.fmt_keyword.setForeground(QColor(Colores.LAVANDA))
        self.fmt_keyword.setFontWeight(QFont.Weight.Bold)
        
        self.fmt_identificador = QTextCharFormat()
        self.fmt_identificador.setForeground(QColor(Colores.VERDE))
        
        self.fmt_numeros = QTextCharFormat()
        self.fmt_numeros.setForeground(QColor(Colores.NARANJA))
        
        self.fmt_op_aritmetico = QTextCharFormat()
        self.fmt_op_aritmetico.setForeground(QColor(Colores.ACENTO_HOVER))
        
        self.fmt_op_rel_log = QTextCharFormat()
        self.fmt_op_rel_log.setForeground(QColor(Colores.AMARILLO))
        
        self.fmt_string = QTextCharFormat()
        self.fmt_string.setForeground(QColor(Colores.ROSA))
        
        self.fmt_comentario = QTextCharFormat()
        self.fmt_comentario.setForeground(QColor(Colores.TEXTO_LINEA_NUM))
        self.fmt_comentario.setFontItalic(True)

        # Lista de palabras reservadas
        self.keywords = [
            "if", "else", "end", "do", "while", "switch", "case",
            "int", "float", "main", "cin", "cout"
        ]

        # ---- ORDEN DE REGLAS (importante para el resaltado correcto) ----
        
        # 1. Color 1: Numeros enteros y reales PRIMERO
        # Regex mejorada que reconoce:
        # - Numeros reales completos: 32.0, 3.14, 0.5 (con digitos despues del punto)
        # - Numeros enteros: 123, 0, 42
        # 
        # Comportamiento deseado:
        # - "32.0algo" -> "32.0" naranja (real valido), "algo" verde (identificador)
        # - "32.algo"  -> "32" naranja (entero), "." sin color, "algo" verde
        # - "123abc"   -> se manejara como error en el compilador, aqui solo se colorea
        #
        # (?<![a-zA-Z_]) = lookbehind negativo: no debe haber letra/guion antes
        # \d+\.\d+ = numero real (digitos, punto, digitos obligatorios)
        # \d+ = numero entero
        self.reglas.append((
            QRegularExpression("(?<![a-zA-Z_])\\d+\\.\\d+|(?<![a-zA-Z_.])\\d+"),
            self.fmt_numeros
        ))

        # 2. Color 2: Identificadores (letras y digitos, no empiezan con digito)
        self.reglas.append((
            QRegularExpression("\\b[a-zA-Z_][a-zA-Z0-9_]*\\b"),
            self.fmt_identificador
        ))

        # 3. Color 4: Palabras reservadas AL FINAL para sobrescribir identificadores
        for kw in self.keywords:
            self.reglas.append((
                QRegularExpression(f"\\b{kw}\\b"),
                self.fmt_keyword
            ))

        # 4. Color 5: Operadores aritmeticos: +, -, *, /, %, ^, ++, --
        # Primero los dobles (++ --) para evitar conflictos
        self.reglas.append((
            QRegularExpression("\\+\\+|--|[+\\-*/%^]"),
            self.fmt_op_aritmetico
        ))

        # 5. Color 6: Operadores relacionales y logicos (mismo color segun PDF)
        # Relacionales: <, <=, >, >=, !=, ==
        # Logicos: && (and), || (or), ! (not)
        # Primero los dobles para evitar conflictos con simples
        self.reglas.append((
            QRegularExpression("<=|>=|!=|==|&&|\\|\\||[<>!]"),
            self.fmt_op_rel_log
        ))

        # 6. Cadenas con comillas dobles: "..."
        self.reglas.append((QRegularExpression('"[^"]*"'), self.fmt_string))

        # 7. Caracteres con comillas simples: '...'
        self.reglas.append((QRegularExpression("'[^']*'"), self.fmt_string))

        # 8. Color 3: Comentarios de una linea //
        self.reglas.append((
            QRegularExpression("//[^\n]*"),
            self.fmt_comentario
        ))

    def highlightBlock(self, text):
        """Aplica resaltado de sintaxis incluyendo comentarios multilinea."""

        # Aplicar reglas de una sola linea
        for pattern, fmt in self.reglas:
            match_iter = pattern.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                start = match.capturedStart()
                length = match.capturedLength()
                self.setFormat(start, length, fmt)

        # ---- Color 3: Comentarios multilinea /* ... */ ----
        # Estado 0 = normal, 1 = dentro de comentario de bloque
        self.setCurrentBlockState(0)

        start_index = 0
        if self.previousBlockState() != 1:
            # Buscar inicio de comentario /*
            start_index = text.find("/*")
        else:
            # Ya estamos dentro de un bloque de comentario
            start_index = 0

        while start_index >= 0:
            if self.previousBlockState() == 1 and start_index == 0:
                # Continuacion de comentario de bloque previo
                end_index = text.find("*/", start_index)
            else:
                end_index = text.find("*/", start_index + 2)

            if end_index == -1:
                # Comentario no se cierra en esta linea
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + 2

            self.setFormat(start_index, comment_length, self.fmt_comentario)

            # Buscar siguiente inicio de comentario
            if end_index == -1:
                break
            start_index = text.find("/*", end_index + 2)

        # Si estamos en estado de comentario previo y no encontramos /*
        if self.previousBlockState() == 1 and text.find("/*") == -1:
            end_index = text.find("*/")
            if end_index == -1:
                self.setCurrentBlockState(1)
                self.setFormat(0, len(text), self.fmt_comentario)
            else:
                self.setFormat(0, end_index + 2, self.fmt_comentario)


# =============================================================================
# Widget de numeros de linea
# =============================================================================
class NumeroLineas(QWidget):
    """Widget lateral que muestra los numeros de linea del editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.ancho_numero_linea(), 0)

    def paintEvent(self, event):
        self.editor.numero_lineas_paint(event)


# =============================================================================
# Editor de codigo con numeracion de lineas
# =============================================================================
class EditorCodigo(QPlainTextEdit):
    """Editor de texto con numeracion de lineas, resaltado de linea actual
    y syntax highlighting."""

    def __init__(self):
        super().__init__()

        # Fuente monoespaciada
        fuente = QFont("Consolas", 13)
        fuente.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(fuente)

        # Desactivar word wrap (como VS Code por defecto)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Tab width
        metrics = self.fontMetrics()
        self.setTabStopDistance(4 * metrics.horizontalAdvance(' '))

        # Area de numeros
        self.numero_area = NumeroLineas(self)

        # Senales
        self.blockCountChanged.connect(self.actualizar_ancho)
        self.updateRequest.connect(self.actualizar_area)
        self.cursorPositionChanged.connect(self.resaltar_linea)

        # Resaltador de sintaxis
        self.highlighter = ResaltadorSintaxis(self.document())

        # Estilo del editor
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {Colores.FONDO_PRINCIPAL};
                color: {Colores.TEXTO};
                border: none;
                padding-left: 4px;
                font-size: 14px;
                selection-background-color: {Colores.SELECCION};
                selection-color: {Colores.TEXTO};
            }}
        """)

        self.actualizar_ancho(0)
        self.resaltar_linea()
        
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                cursor = self.textCursor()
                cursor.insertBlock()
                self.setTextCursor(cursor)
                return
        super().keyPressEvent(event)

    def ancho_numero_linea(self):
        """Calcula el ancho necesario para mostrar los numeros de linea."""
        digits = len(str(max(1, self.blockCount())))
        space = 14 + self.fontMetrics().horizontalAdvance('9') * digits
        return space
    

    def actualizar_ancho(self, _):
        """Actualiza el margen izquierdo del viewport para los numeros."""
        self.setViewportMargins(self.ancho_numero_linea(), 0, 0, 0)

    def actualizar_area(self, rect, dy):
        """Actualiza el area de numeros al hacer scroll."""
        if dy:
            self.numero_area.scroll(0, dy)
        else:
            self.numero_area.update(
                0, rect.y(), self.numero_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.actualizar_ancho(0)

    def resizeEvent(self, event):
        """Reposiciona el area de numeros al redimensionar."""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.numero_area.setGeometry(
            QRect(cr.left(), cr.top(), self.ancho_numero_linea(), cr.height())
        )

    def numero_lineas_paint(self, event):
        """Dibuja los numeros de linea en el area lateral."""
        painter = QPainter(self.numero_area)
        painter.fillRect(event.rect(), QColor(Colores.FONDO_LINEA_NUM))

        block = self.firstVisibleBlock()
        numero = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block)
            .translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())

        # Linea actual para resaltado del numero
        linea_actual = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                numero_texto = str(numero + 1)
                if numero == linea_actual:
                    painter.setPen(QColor(Colores.TEXTO))
                else:
                    painter.setPen(QColor(Colores.TEXTO_LINEA_NUM))

                painter.drawText(
                    0, top,
                    self.numero_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    numero_texto
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            numero += 1

        painter.end()

    def resaltar_linea(self):
        """Resalta la linea actual del cursor con un fondo diferenciado."""
        selecciones = []
        if not self.isReadOnly():
            seleccion = QTextEdit.ExtraSelection()
            color_linea = QColor(Colores.FONDO_LINEA_ACTUAL)
            seleccion.format.setBackground(color_linea)
            seleccion.format.setProperty(
                QTextFormat.Property.FullWidthSelection, True
            )
            seleccion.cursor = self.textCursor()
            seleccion.cursor.clearSelection()
            selecciones.append(seleccion)
        self.setExtraSelections(selecciones)

    def obtener_posicion_cursor(self):
        """Retorna (linea, columna) actuales del cursor."""
        cursor = self.textCursor()
        linea = cursor.blockNumber() + 1
        columna = cursor.columnNumber() + 1
        return linea, columna


# =============================================================================
# Funciones auxiliares para crear tablas de resultados
# =============================================================================
def crear_tabla(columnas, filas=None):
    """Crea un QTableWidget estilizado con las columnas dadas."""
    tabla = QTableWidget()
    tabla.setColumnCount(len(columnas))
    tabla.setHorizontalHeaderLabels(columnas)
    tabla.horizontalHeader().setStretchLastSection(True)
    tabla.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch
    )
    tabla.setAlternatingRowColors(False)
    tabla.verticalHeader().setVisible(False)
    tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

    if filas:
        for fila in filas:
            row = tabla.rowCount()
            tabla.insertRow(row)
            for col, valor in enumerate(fila):
                tabla.setItem(row, col, QTableWidgetItem(str(valor)))

    return tabla


def crear_panel_errores(columnas=None):
    """Crea una tabla estandar para mostrar errores."""
    if columnas is None:
        columnas = ["Linea", "Columna", "Tipo", "Descripcion"]
    return crear_tabla(columnas)


# =============================================================================
# Ventana principal del IDE
# =============================================================================
class VentanaPrincipal(QMainWindow):
    """Ventana principal del IDE. Gestiona todos los paneles, menus,
    toolbar y la comunicacion con el compilador externo."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("IDE Compilador")
        self.setMinimumSize(1200, 700)
        self.showMaximized()

        self.ruta_archivo = None
        self.archivo_modificado = False

        # ----- Editor central -----
        self.editor = EditorCodigo()
        self.editor.textChanged.connect(self._on_texto_cambiado)
        self.editor.cursorPositionChanged.connect(self._actualizar_pos_cursor)
        self.setCentralWidget(self.editor)

        # ----- Crear paneles de resultados -----
        self._crear_paneles()

        # ----- Menu -----
        self._crear_menu()

        # ----- Toolbar -----
        self._crear_toolbar()

        # ----- Status bar -----
        self._crear_statusbar()

        self._actualizar_titulo()

    # -----------------------------------------------------------------
    # Creacion de paneles
    # -----------------------------------------------------------------
    def _crear_paneles(self):
        """Crea todos los paneles dock del IDE."""

        # ===== Panel derecho: Resultados de analisis =====
        self.dock_derecho = QDockWidget("Resultados de Analisis", self)
        self.dock_derecho.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.tabs_derecho = QTabWidget()

        # Tab: Lexico
        self.tabla_lexico = crear_tabla(
            ["No.", "Token", "Tipo", "Linea", "Columna"]
        )
        self.tabs_derecho.addTab(self.tabla_lexico, "Lexico")

        # Tab: Sintactico
        self.arbol_sintactico = QTreeWidget()
        self.arbol_sintactico.setColumnCount(1)
        self.arbol_sintactico.setHeaderLabels(["Arbol Sintactico Abstracto"])
        self.arbol_sintactico.setAlternatingRowColors(False)
        self.arbol_sintactico.setWordWrap(False)
        self.arbol_sintactico.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.arbol_sintactico.header().setStretchLastSection(True)
        self.arbol_sintactico.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.tabs_derecho.addTab(self.arbol_sintactico, "Sintactico")

        # Tab: Tabla de Simbolos
        self.tabla_simbolos = crear_tabla(
            ["ID", "Nombre", "Tipo", "Valor", "Scope", "Linea"]
        )
        self.tabs_derecho.addTab(self.tabla_simbolos, "Tabla de Simbolos")

        self.dock_derecho.setWidget(self.tabs_derecho)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.dock_derecho
        )

        # ===== Panel inferior: Errores y Resultados =====
        self.dock_inferior = QDockWidget("Consola", self)
        self.dock_inferior.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.tabs_inferior = QTabWidget()

        # Tab: Errores Lexicos
        self.tabla_err_lexico = crear_panel_errores()
        self.tabs_inferior.addTab(self.tabla_err_lexico, "Errores Lexicos")

        # Tab: Errores Sintacticos
        self.tabla_err_sintactico = crear_panel_errores()
        self.tabs_inferior.addTab(
            self.tabla_err_sintactico, "Errores Sintacticos"
        )

        # Tab: Resultados generales
        self.texto_resultados = QPlainTextEdit()
        self.texto_resultados.setReadOnly(True)
        fuente_res = QFont("Consolas", 12)
        fuente_res.setStyleHint(QFont.StyleHint.Monospace)
        self.texto_resultados.setFont(fuente_res)
        self.texto_resultados.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {Colores.FONDO_PANEL};
                color: {Colores.VERDE};
                border: none;
                padding: 8px;
            }}
        """)
        self.tabs_inferior.addTab(self.texto_resultados, "Resultados")

        self.dock_inferior.setWidget(self.tabs_inferior)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_inferior
        )

    # -----------------------------------------------------------------
    # Menu
    # -----------------------------------------------------------------
    def _crear_menu(self):
        """Crea la barra de menu con Archivo, Compilar y Ver."""
        barra = self.menuBar()

        # ===== Menu Archivo =====
        menu_archivo = barra.addMenu("Archivo")

        self.act_nuevo = QAction("Nuevo", self)
        self.act_nuevo.setShortcut(QKeySequence("Ctrl+N"))
        self.act_nuevo.triggered.connect(self.nuevo_archivo)

        self.act_abrir = QAction("Abrir", self)
        self.act_abrir.setShortcut(QKeySequence("Ctrl+O"))
        self.act_abrir.triggered.connect(self.abrir_archivo)

        self.act_cerrar = QAction("Cerrar", self)
        self.act_cerrar.setShortcut(QKeySequence("Ctrl+W"))
        self.act_cerrar.triggered.connect(self.cerrar_archivo)

        self.act_guardar = QAction("Guardar", self)
        self.act_guardar.setShortcut(QKeySequence("Ctrl+S"))
        self.act_guardar.triggered.connect(self.guardar_archivo)

        self.act_guardar_como = QAction("Guardar como...", self)
        self.act_guardar_como.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_guardar_como.triggered.connect(self.guardar_como)

        self.act_salir = QAction("Salir", self)
        self.act_salir.setShortcut(QKeySequence("Alt+F4"))
        self.act_salir.triggered.connect(self.close)

        menu_archivo.addAction(self.act_nuevo)
        menu_archivo.addAction(self.act_abrir)
        menu_archivo.addAction(self.act_cerrar)
        menu_archivo.addSeparator()
        menu_archivo.addAction(self.act_guardar)
        menu_archivo.addAction(self.act_guardar_como)
        menu_archivo.addSeparator()
        menu_archivo.addAction(self.act_salir)

        # ===== Menu Compilar =====
        menu_compilar = barra.addMenu("Compilar")

        self.act_ejecutar = QAction("Ejecutar", self)
        self.act_ejecutar.setShortcut(QKeySequence("F5"))
        self.act_ejecutar.triggered.connect(self.ejecutar_analisis)

        menu_compilar.addAction(self.act_ejecutar)

        # ===== Menu Ver =====
        menu_ver = barra.addMenu("Ver")

        act_panel_derecho = QAction("Panel de Resultados", self)
        act_panel_derecho.setCheckable(True)
        act_panel_derecho.setChecked(True)
        act_panel_derecho.triggered.connect(
            lambda checked: self.dock_derecho.setVisible(checked)
        )

        act_panel_inferior = QAction("Panel de Consola", self)
        act_panel_inferior.setCheckable(True)
        act_panel_inferior.setChecked(True)
        act_panel_inferior.triggered.connect(
            lambda checked: self.dock_inferior.setVisible(checked)
        )

        menu_ver.addAction(act_panel_derecho)
        menu_ver.addAction(act_panel_inferior)

    # -----------------------------------------------------------------
    # Toolbar
    # -----------------------------------------------------------------
    def _crear_toolbar(self):
        """Crea la barra de herramientas con botones de acceso rapido."""
        toolbar = QToolBar("Compilacion")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Botones de archivo
        btn_nuevo = QAction("Nuevo", self)
        btn_nuevo.triggered.connect(self.nuevo_archivo)
        toolbar.addAction(btn_nuevo)

        btn_abrir = QAction("Abrir", self)
        btn_abrir.triggered.connect(self.abrir_archivo)
        toolbar.addAction(btn_abrir)

        btn_guardar = QAction("Guardar", self)
        btn_guardar.triggered.connect(self.guardar_archivo)
        toolbar.addAction(btn_guardar)
        
        btn_guardar_como = QAction("Guardar como", self)
        btn_guardar_como.triggered.connect(self.guardar_como)
        toolbar.addAction(btn_guardar_como)

        btn_salir = QAction("Salir", self)
        btn_salir.triggered.connect(self.close)
        toolbar.addAction(btn_salir)
        
        

        toolbar.addSeparator()

        # Boton unico de compilacion: ejecuta lexico + sintactico.
        btn_ejecutar = QAction("Ejecutar [F5]", self)
        btn_ejecutar.triggered.connect(self.ejecutar_analisis)
        toolbar.addAction(btn_ejecutar)

    # -----------------------------------------------------------------
    # Status bar
    # -----------------------------------------------------------------
    def _crear_statusbar(self):
        """Crea la barra de estado con posicion del cursor."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.label_posicion = QLabel("Ln 1, Col 1")
        self.label_archivo = QLabel("Sin archivo")
        self.label_estado = QLabel("Listo")

        self.status_bar.addPermanentWidget(self.label_estado)
        self.status_bar.addPermanentWidget(self.label_archivo)
        self.status_bar.addPermanentWidget(self.label_posicion)

    # -----------------------------------------------------------------
    # Gestion de archivos
    # -----------------------------------------------------------------
    def _actualizar_titulo(self):
        """Actualiza el titulo de la ventana con el nombre del archivo."""
        nombre = os.path.basename(self.ruta_archivo) if self.ruta_archivo else "Sin titulo"
        modificado = " *" if self.archivo_modificado else ""
        self.setWindowTitle(f"{nombre}{modificado} - IDE Compilador")
        nombre_archivo = self.ruta_archivo if self.ruta_archivo else "Sin archivo"
        self.label_archivo.setText(nombre_archivo)

    def _on_texto_cambiado(self):
        """Marca el archivo como modificado cuando cambia el texto."""
        self.archivo_modificado = True
        self._actualizar_titulo()

    def _actualizar_pos_cursor(self):
        """Actualiza la posicion del cursor en la barra de estado."""
        linea, columna = self.editor.obtener_posicion_cursor()
        self.label_posicion.setText(f"Ln {linea}, Col {columna}")

    def _confirmar_si_no_guardado(self):
        """Pregunta al usuario si desea guardar cambios no guardados.
        Retorna True si se puede continuar, False si cancelo."""
        if not self.archivo_modificado:
            return True

        respuesta = QMessageBox.question(
            self, "Cambios sin guardar",
            "El archivo tiene cambios sin guardar.\n"
            "Desea guardar antes de continuar?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save
        )

        if respuesta == QMessageBox.StandardButton.Save:
            self.guardar_archivo()
            return True
        elif respuesta == QMessageBox.StandardButton.Discard:
            return True
        else:
            return False

    def nuevo_archivo(self):
        """Crea un nuevo archivo vacio."""
        if not self._confirmar_si_no_guardado():
            return
        self.editor.clear()
        self.ruta_archivo = None
        self.archivo_modificado = False
        self._limpiar_paneles()
        self._actualizar_titulo()
        self.label_estado.setText("Nuevo archivo creado")

    def abrir_archivo(self):
        """Abre un archivo existente."""
        if not self._confirmar_si_no_guardado():
            return
        archivo, _ = QFileDialog.getOpenFileName(
            self, "Abrir archivo", "",
            "Archivos de texto (*.txt);;Todos los archivos (*.*)"
        )
        if archivo:
            try:
                with open(archivo, "r", encoding="utf-8") as f:
                    self.editor.setPlainText(f.read())
                self.ruta_archivo = archivo
                self.archivo_modificado = False
                self._limpiar_paneles()
                self._actualizar_titulo()
                self.label_estado.setText(f"Archivo abierto: {archivo}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Error al abrir",
                    f"No se pudo abrir el archivo:\n{str(e)}"
                )

    def cerrar_archivo(self):
        """Cierra el archivo actual."""
        if not self._confirmar_si_no_guardado():
            return
        self.editor.clear()
        self.ruta_archivo = None
        self.archivo_modificado = False
        self._limpiar_paneles()
        self._actualizar_titulo()
        self.label_estado.setText("Archivo cerrado")

    def guardar_archivo(self):
        """Guarda el archivo actual."""
        if self.ruta_archivo:
            try:
                with open(self.ruta_archivo, "w", encoding="utf-8") as f:
                    f.write(self.editor.toPlainText())
                self.archivo_modificado = False
                self._actualizar_titulo()
                self.label_estado.setText(f"Guardado: {self.ruta_archivo}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Error al guardar",
                    f"No se pudo guardar el archivo:\n{str(e)}"
                )
        else:
            self.guardar_como()

    def guardar_como(self):
        """Guarda el archivo con un nuevo nombre."""
        archivo, _ = QFileDialog.getSaveFileName(
            self, "Guardar como", "",
            "Archivos de texto (*.txt);;Todos los archivos (*.*)"
        )
        if archivo:
            try:
                with open(archivo, "w", encoding="utf-8") as f:
                    f.write(self.editor.toPlainText())
                self.ruta_archivo = archivo
                self.archivo_modificado = False
                self._actualizar_titulo()
                self.label_estado.setText(f"Guardado como: {archivo}")
            except Exception as e:
                QMessageBox.critical(
                    self, "Error al guardar",
                    f"No se pudo guardar el archivo:\n{str(e)}"
                )

    def closeEvent(self, event):
        """Confirma antes de cerrar la aplicacion."""
        if self._confirmar_si_no_guardado():
            event.accept()
        else:
            event.ignore()

    # -----------------------------------------------------------------
    # Limpiar paneles
    # -----------------------------------------------------------------
    def _limpiar_paneles(self):
        """Limpia todos los paneles de resultados y errores."""
        self.tabla_lexico.setRowCount(0)
        self.arbol_sintactico.clear()
        self.tabla_simbolos.setRowCount(0)
        self.tabla_err_lexico.setRowCount(0)
        self.tabla_err_sintactico.setRowCount(0)
        self.texto_resultados.clear()

    # -----------------------------------------------------------------
    # Comunicacion con compilador externo (system call)
    # -----------------------------------------------------------------
    def _guardar_temporal(self):
        """Guarda el contenido del editor en un archivo temporal.
        Retorna la ruta del archivo temporal."""
        codigo = self.editor.toPlainText()
        if not codigo.strip():
            QMessageBox.warning(
                self, "Editor vacio",
                "No hay codigo para compilar."
            )
            return None

        fd, ruta = tempfile.mkstemp(suffix=".txt", prefix="ide_src_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(codigo)
        return ruta

    def _invocar_compilador(self, fase, archivo_entrada):
        """Invoca al compilador externo como proceso independiente.

        El compilador se ejecuta como:
            python compilador.py <fase> <archivo_entrada> <archivo_salida>

        Donde <fase> puede ser: lexico o sintactico.

        El compilador escribe su salida en formato JSON al archivo de salida.
        La interfaz no realiza analisis lexico ni sintactico; solo invoca el
        compilador externo y muestra sus resultados.

        Args:
            fase: Nombre de la fase a ejecutar
            archivo_entrada: Ruta del archivo fuente temporal

        Returns:
            dict con los resultados o None si hubo error
        """
        fd_out, archivo_salida = tempfile.mkstemp(
            suffix=".json", prefix="ide_out_"
        )
        os.close(fd_out)

        # Buscar compilador externo
        directorio_ide = os.path.dirname(os.path.abspath(__file__))
        compilador_path = os.path.join(directorio_ide, "compilador.py")

        if os.path.exists(compilador_path):
            # ------- Compilador externo existe: system call -------
            try:
                resultado = subprocess.run(
                    [
                        sys.executable, compilador_path,
                        fase, archivo_entrada, archivo_salida
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if os.path.exists(archivo_salida):
                    with open(archivo_salida, "r", encoding="utf-8") as f:
                        contenido = f.read().strip()
                        if contenido:
                            return json.loads(contenido)

                # Si no genero archivo, intentar leer de stdout
                if resultado.stdout.strip():
                    try:
                        return json.loads(resultado.stdout.strip())
                    except json.JSONDecodeError:
                        return {
                            "salida": resultado.stdout,
                            "errores": resultado.stderr
                        }

                if resultado.returncode != 0:
                    return {
                        "errores": [
                            {
                                "linea": 0,
                                "columna": 0,
                                "tipo": "Error del compilador",
                                "descripcion": resultado.stderr or "Error desconocido"
                            }
                        ]
                    }

            except subprocess.TimeoutExpired:
                return {
                    "errores": [
                        {
                            "linea": 0,
                            "columna": 0,
                            "tipo": "Timeout",
                            "descripcion": "El compilador excedio el tiempo limite (30s)"
                        }
                    ]
                }
            except Exception as e:
                return {
                    "errores": [
                        {
                            "linea": 0,
                            "columna": 0,
                            "tipo": "Error de ejecucion",
                            "descripcion": str(e)
                        }
                    ]
                }
            finally:
                self._limpiar_temporal(archivo_salida)

        else:
            # ------- Compilador externo NO existe -------
            self._limpiar_temporal(archivo_salida)
            return {
                "errores": [
                    {
                        "linea": 0,
                        "columna": 0,
                        "tipo": "Error del compilador",
                        "descripcion": "No se encontro scripts/compilador.py"
                    }
                ]
            }

    def _limpiar_temporal(self, ruta):
        """Elimina un archivo temporal de forma segura."""
        try:
            if ruta and os.path.exists(ruta):
                os.remove(ruta)
        except OSError:
            pass

    # -----------------------------------------------------------------
    # Mostrar resultados en los paneles
    # -----------------------------------------------------------------
    def _mostrar_tokens(self, tokens):
        """Muestra la lista de tokens en la tabla de Lexico."""
        self.tabla_lexico.setRowCount(0)
        for tok in tokens:
            row = self.tabla_lexico.rowCount()
            self.tabla_lexico.insertRow(row)
            self.tabla_lexico.setItem(row, 0, QTableWidgetItem(str(tok.get("no", ""))))
            self.tabla_lexico.setItem(row, 1, QTableWidgetItem(tok.get("token", "")))
            self.tabla_lexico.setItem(row, 2, QTableWidgetItem(tok.get("tipo", "")))
            self.tabla_lexico.setItem(row, 3, QTableWidgetItem(str(tok.get("linea", ""))))
            self.tabla_lexico.setItem(row, 4, QTableWidgetItem(str(tok.get("columna", ""))))

    def _mostrar_arbol(self, nodo, parent_item=None):
        """Muestra el arbol sintactico de forma recursiva en el QTreeWidget."""
        texto_nodo = nodo.get("nodo", "")
        texto_valor = nodo.get("valor", "")
        texto_tipo = nodo.get("tipo", "")
        partes = [texto_nodo]
        if texto_valor:
            partes.append(f"valor: {texto_valor}")
        if texto_tipo:
            partes.append(f"tipo: {texto_tipo}")
        etiqueta = " | ".join(partes)

        if parent_item is None:
            item = QTreeWidgetItem(self.arbol_sintactico)
        else:
            item = QTreeWidgetItem(parent_item)

        item.setText(0, etiqueta)
        item.setToolTip(0, etiqueta)

        for hijo in nodo.get("hijos", []):
            self._mostrar_arbol(hijo, item)

        item.setExpanded(True)

    def _mostrar_tabla_simbolos(self, simbolos):
        """Muestra la tabla de simbolos."""
        self.tabla_simbolos.setRowCount(0)
        for sim in simbolos:
            row = self.tabla_simbolos.rowCount()
            self.tabla_simbolos.insertRow(row)
            self.tabla_simbolos.setItem(row, 0, QTableWidgetItem(str(sim.get("id", ""))))
            self.tabla_simbolos.setItem(row, 1, QTableWidgetItem(sim.get("nombre", "")))
            self.tabla_simbolos.setItem(row, 2, QTableWidgetItem(sim.get("tipo", "")))
            self.tabla_simbolos.setItem(row, 3, QTableWidgetItem(str(sim.get("valor", ""))))
            self.tabla_simbolos.setItem(row, 4, QTableWidgetItem(sim.get("scope", "")))
            self.tabla_simbolos.setItem(row, 5, QTableWidgetItem(str(sim.get("linea", ""))))

    def _mostrar_errores(self, errores, tabla):
        """Muestra errores en la tabla de errores correspondiente."""
        tabla.setRowCount(0)
        for err in errores:
            row = tabla.rowCount()
            tabla.insertRow(row)

            item_linea = QTableWidgetItem(str(err.get("linea", "")))
            item_linea.setForeground(QColor(Colores.ROJO))
            tabla.setItem(row, 0, item_linea)

            tabla.setItem(row, 1, QTableWidgetItem(str(err.get("columna", ""))))
            tabla.setItem(row, 2, QTableWidgetItem(err.get("tipo", "")))

            item_desc = QTableWidgetItem(err.get("descripcion", ""))
            item_desc.setForeground(QColor(Colores.ROJO))
            tabla.setItem(row, 3, item_desc)

    def _procesar_resultado(self, resultado, fase):
        """Procesa el resultado del compilador y lo muestra en los paneles
        correspondientes segun la fase ejecutada."""
        if resultado is None:
            return

        # Tokens
        if "tokens" in resultado:
            self._mostrar_tokens(resultado["tokens"])
            self.tabs_derecho.setCurrentWidget(self.tabla_lexico)
            total = len(resultado["tokens"])
            self.label_estado.setText(f"Analisis lexico: {total} tokens encontrados")

        # Arbol sintactico
        if "arbol" in resultado:
            self.arbol_sintactico.clear()
            self._mostrar_arbol(resultado["arbol"])
            if fase == "sintactico":
                self.tabs_derecho.setCurrentWidget(self.arbol_sintactico)
                self.label_estado.setText("Analisis sintactico completado")

        # Tabla de simbolos
        if "tabla_simbolos" in resultado:
            self._mostrar_tabla_simbolos(resultado["tabla_simbolos"])

        # Errores
        errores = resultado.get("errores", [])
        errores_lex = [e for e in errores if "Lexico" in e.get("tipo", "") or "lexico" in e.get("tipo", "")]
        errores_sin = [e for e in errores if "Sintactico" in e.get("tipo", "") or "sintactico" in e.get("tipo", "")]
        errores_otros = [e for e in errores if e not in errores_lex and e not in errores_sin]

        self._mostrar_errores(errores_lex, self.tabla_err_lexico)
        self._mostrar_errores(errores_sin + errores_otros, self.tabla_err_sintactico)

        if errores_lex:
            self.tabs_inferior.setCurrentWidget(self.tabla_err_lexico)
        elif errores_sin:
            self.tabs_inferior.setCurrentWidget(self.tabla_err_sintactico)

        # Salida generica
        if "salida" in resultado:
            self.texto_resultados.setPlainText(str(resultado["salida"]))
            self.tabs_inferior.setCurrentWidget(self.texto_resultados)

    # -----------------------------------------------------------------
    # Acciones de compilacion
    # -----------------------------------------------------------------
    def ejecutar_analisis(self):
        """Ejecuta lexico y sintactico en una sola accion."""
        self._limpiar_paneles()
        archivo = self._guardar_temporal()
        if archivo:
            self.label_estado.setText("Ejecutando analisis lexico y sintactico...")
            resultado = self._invocar_compilador("sintactico", archivo)
            self._procesar_resultado(resultado, "sintactico")
            self.label_estado.setText("Analisis lexico y sintactico completado")
            self._limpiar_temporal(archivo)

# =============================================================================
# Punto de entrada
# =============================================================================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    ventana = VentanaPrincipal()
    ventana.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
