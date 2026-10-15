"""Pruebas de widgets y del proceso real de compilacion, con Qt offscreen."""

import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "code" / "scripts"))

from PyQt6.QtCore import Qt, QEvent, QPoint
from PyQt6.QtGui import QHelpEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QToolTip
from compilador_ide import VentanaPrincipal


class IDETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory(prefix="fase3_ide_")
        self.ventana = VentanaPrincipal()
        self.ventana.directorio_salidas = self.temporal.name

    def tearDown(self):
        self.ventana.archivo_modificado = False
        self.ventana.close()
        self.app.processEvents()
        self.temporal.cleanup()

    def esperar(self):
        limite = time.monotonic() + 10
        while self.ventana.proceso_compilador is not None and time.monotonic() < limite:
            QTest.qWait(10)
        self.assertIsNone(self.ventana.proceso_compilador)
        self.assertIsNotNone(self.ventana.ultimo_resultado)
        return self.ventana.ultimo_resultado

    def compilar(self, codigo):
        self.ventana.editor.setPlainText(codigo)
        self.ventana.act_ejecutar.trigger()
        return self.esperar()

    def test_f5_flujo_real_y_limpieza_temporales(self):
        self.ventana.editor.setPlainText((RAIZ / "pruebas/semantico_valido.txt").read_text(encoding="utf-8"))
        self.assertEqual(self.ventana.act_ejecutar.shortcut().toString(), "F5")
        self.ventana.act_ejecutar.trigger()
        self.assertFalse(self.ventana.act_ejecutar.isEnabled())
        temporales = list(self.ventana._temporales_compilacion)
        r = self.esperar()
        self.assertEqual(r["fase"], "semantico")
        self.assertTrue(r["valido"])
        self.assertTrue(self.ventana.act_ejecutar.isEnabled())
        self.assertTrue(all(not Path(p).exists() for p in temporales))
        self.assertEqual(self.ventana._temporales_compilacion, [])

    def test_arboles_y_comparacion_sincronizada(self):
        self.compilar("main { float x; x = 2; }")
        w = self.ventana
        self.assertEqual(w.arbol_sintactico.topLevelItemCount(), 1)
        self.assertEqual(w.arbol_semantico.topLevelItemCount(), 1)
        self.assertEqual(w.arbol_semantico.columnCount(), 5)
        item = w._items_arbol[w.arbol_comparacion_original]["0.0.1.1"]
        w.arbol_comparacion_original.setCurrentItem(item)
        otro = w.arbol_comparacion_anotado.currentItem()
        self.assertEqual(otro.data(0, Qt.ItemDataRole.UserRole), "0.0.1.1")
        self.assertEqual(otro.toolTip(0), "")
        self.assertIn("int -> float", otro.text(1))

    def test_maestro_motivo_visible_en_los_cuatro_arboles(self):
        r = self.compilar((RAIZ / "pruebas/maestro_condiciones_original.txt").read_text(encoding="utf-8"))
        self.assertEqual(r["errores_sintacticos"], [])
        w = self.ventana
        for arbol, columna_valor, columna_detalle in [
            (w.arbol_sintactico, 1, 2), (w.arbol_semantico, 2, 4),
            (w.arbol_comparacion_original, 1, 2), (w.arbol_comparacion_anotado, 2, 4)]:
            item = next(i for i in w._items_arbol[arbol].values() if i.text(0) == "Seleccion")
            self.assertEqual(item.text(columna_valor), "desconocido")
            self.assertEqual(item.text(columna_detalle), "desconocido: b sin inicializar")
            self.assertEqual(item.toolTip(columna_detalle), "")

    def test_maestro_valido_comparador_y_bucle_true_false(self):
        r = self.compilar((RAIZ / "pruebas/maestro_condiciones_valido.txt").read_text(encoding="utf-8"))
        self.assertTrue(r["valido"])
        items = list(self.ventana._items_arbol[self.ventana.arbol_semantico].values())
        comparador = next(i for i in items if i.text(0).startswith("OperacionRelacional | valor: >"))
        self.assertEqual(comparador.text(2), "true")
        self.assertEqual(comparador.text(4), "true")
        bucle = next(i for i in items if i.text(0) == "RepeticionDoWhile")
        self.assertEqual(bucle.text(2), "false")
        self.assertEqual(bucle.text(4), "false")

    def test_errores_semanticos_en_su_tabla(self):
        r = self.compilar((RAIZ / "pruebas/semantico_errores.txt").read_text(encoding="utf-8"))
        self.assertEqual(len(r["errores_semanticos"]), 11)
        self.assertEqual(self.ventana.tabla_err_sintactico.rowCount(), 0)
        self.assertEqual(self.ventana.tabla_err_semantico.rowCount(), 11)
        self.assertEqual(self.ventana.tabla_err_semantico.item(0, 2).text(), "Error Semantico")
        self.assertTrue(self.ventana.tabla_err_semantico.item(0, 0).text())

    def test_historico_muestra_errores_separados(self):
        self.compilar((RAIZ / "testlexico.txt").read_text(encoding="utf-8"))
        self.assertEqual(self.ventana.tabla_err_sintactico.rowCount(), 2)
        self.assertEqual(self.ventana.tabla_err_semantico.rowCount(), 8)
        self.assertEqual(self.ventana.tabla_simbolos.rowCount(), 6)
        self.assertIn("parcial", self.ventana.label_estado.text())

    def test_tabla_semantica_real(self):
        self.compilar("main { int x; float y; cin >> x; y = x; }")
        tabla = self.ventana.tabla_simbolos
        self.assertEqual(tabla.rowCount(), 2)
        self.assertEqual(tabla.item(0, 2).text(), "int")
        self.assertEqual(tabla.item(1, 2).text(), "float")
        self.assertEqual(tabla.item(0, 5).text(), "global")
        self.assertEqual(tabla.item(1, 6).text(), "1")

    def test_bloqueo_limpia_arboles_y_tabla_anteriores(self):
        self.compilar("main { int x = 1; }")
        self.compilar("main { int x; x = @; }")
        self.assertEqual(self.ventana.arbol_sintactico.topLevelItemCount(), 0)
        self.assertEqual(self.ventana.arbol_semantico.topLevelItemCount(), 0)
        self.assertEqual(self.ventana.arbol_comparacion_original.topLevelItemCount(), 0)
        self.assertEqual(self.ventana.tabla_simbolos.rowCount(), 0)
        self.assertEqual(self.ventana.tabla_err_lexico.rowCount(), 1)
        self.assertEqual(self.ventana.tabla_err_semantico.rowCount(), 0)

    def test_error_tecnico_no_es_sintactico(self):
        self.ventana.ruta_compilador = str(Path(self.temporal.name) / "ausente.py")
        r = self.compilar("main {}")
        self.assertTrue(r["errores_ejecucion"])
        self.assertEqual(self.ventana.tabla_err_sintactico.rowCount(), 0)
        self.assertEqual(self.ventana.tabla_err_semantico.rowCount(), 0)
        self.assertIn("No se encontro", self.ventana.texto_resultados.toPlainText())
        self.assertTrue(self.ventana.act_ejecutar.isEnabled())

    def test_edicion_durante_proceso_identifica_resultado_anterior(self):
        self.ventana.editor.setPlainText("main { int x; }")
        self.ventana.act_ejecutar.trigger()
        self.ventana.editor.setPlainText("main { float y; }")
        r = self.esperar()
        self.assertEqual(r["tabla_simbolos"][0]["nombre"], "x")
        self.assertIn("version anterior", self.ventana.label_estado.text())

    def test_no_inicia_segundo_proceso(self):
        self.ventana.editor.setPlainText("main {}")
        self.ventana.act_ejecutar.trigger()
        proceso = self.ventana.proceso_compilador
        temporales = list(self.ventana._temporales_compilacion)
        self.ventana.ejecutar_analisis()
        self.assertIs(self.ventana.proceso_compilador, proceso)
        self.assertEqual(self.ventana._temporales_compilacion, temporales)
        self.esperar()

    def test_tooltips_bloqueados_en_arboles_tablas_y_errores(self):
        self.compilar("main { int y = 6; y = y + 9; cout << ausente; }")
        w = self.ventana
        for arbol in (w.arbol_sintactico, w.arbol_semantico,
                      w.arbol_comparacion_original, w.arbol_comparacion_anotado):
            for item in w._items_arbol[arbol].values():
                self.assertTrue(all(item.toolTip(c) == "" for c in range(arbol.columnCount())))
        for tabla in (w.tabla_lexico, w.tabla_simbolos, w.tabla_err_lexico,
                      w.tabla_err_sintactico, w.tabla_err_semantico):
            for fila in range(tabla.rowCount()):
                self.assertTrue(all(tabla.item(fila, c).toolTip() == "" for c in range(tabla.columnCount())))
        for vista in (w.arbol_semantico, w.arbol_comparacion_original,
                      w.tabla_simbolos, w.tabla_err_semantico):
            for objeto in (vista.viewport(), vista.header() if hasattr(vista, "header") else vista.horizontalHeader()):
                punto = QPoint(10, 10)
                evento = QHelpEvent(QEvent.Type.ToolTip, punto, objeto.mapToGlobal(punto))
                self.assertTrue(self.app.sendEvent(objeto, evento))
                self.assertFalse(QToolTip.isVisible())

    def test_arbol_muestra_valor_quince_y_linea_repetida(self):
        r = self.compilar("main {\n int y;\n y = 5 + 2 - 1;\n y = y + 9;\n}")
        arbol = self.ventana.arbol_semantico
        item = self.ventana._items_arbol[arbol]["0.0.2"]
        self.assertEqual(item.text(2), "15")
        self.assertEqual(self.ventana.tabla_simbolos.item(0, 3).text(), "2, 3, 4, 4")
        self.assertEqual(r["tabla_simbolos"][0]["valor_actual"], 15)

    def test_resultado_booleano_en_original_anotado_y_comparacion(self):
        self.compilar("main { int x = 4; while x > 2 && x != 0 x--; end }")
        w = self.ventana
        for arbol, columna in ((w.arbol_sintactico, 1), (w.arbol_comparacion_original, 1),
                               (w.arbol_semantico, 2), (w.arbol_comparacion_anotado, 2)):
            item = w._items_arbol[arbol]["0.0.1.0"]
            self.assertEqual(item.text(columna), "true")

    def test_do_while_resultado_explicito_sin_sufijos(self):
        for x, y, esperado in [(4, 8, "true"), (4, 9, "false"), (3, 8, "false")]:
            with self.subTest(x=x, y=y):
                self.compilar(f"main {{ int x={x}, y={y}; do cout << x; while(x==4 && y!=9); }}")
                w = self.ventana
                for arbol, valor, detalle in [(w.arbol_semantico, 2, 4),
                                             (w.arbol_comparacion_anotado, 2, 4),
                                             (w.arbol_sintactico, 1, 2),
                                             (w.arbol_comparacion_original, 1, 2)]:
                    items = w._items_arbol[arbol].values()
                    relevantes = [i for i in items if i.text(0) in {"RepeticionDoWhile", "Grupo"}
                                  or i.text(0).startswith("OperacionLogica | valor: &&")]
                    self.assertEqual(len(relevantes), 3)
                    for item in relevantes:
                        self.assertEqual(item.text(valor), esperado)
                        self.assertEqual(item.text(detalle), esperado)

    def test_maestro_ningun_valor_tiene_etiquetas_de_contexto(self):
        self.compilar((RAIZ / "pruebas/maestro_condiciones_original.txt").read_text(encoding="utf-8"))
        for arbol in (self.ventana.arbol_semantico, self.ventana.arbol_comparacion_anotado):
            for item in self.ventana._items_arbol[arbol].values():
                self.assertNotIn("(", item.text(2))
                self.assertNotIn(")", item.text(2))

    def test_do_while_desconocido_no_se_presenta_como_false(self):
        self.compilar("main { int x=4, y=8; do cin >> x; while(x==4 && y!=9); }")
        items = self.ventana._items_arbol[self.ventana.arbol_semantico].values()
        condicion = next(i for i in items if i.text(0).startswith("OperacionLogica | valor: &&"))
        self.assertEqual(condicion.text(2), "desconocido")
        self.assertIn("desconocido: x recibido por cin", condicion.text(4))

    def test_condicion_desconocida_visible_sin_inventar_false(self):
        self.compilar("main { float a = 55, b; if a > b then end }")
        w = self.ventana
        for arbol, columna in ((w.arbol_sintactico, 1), (w.arbol_semantico, 2)):
            self.assertEqual(w._items_arbol[arbol]["0.0.1.0"].text(columna), "desconocido")

    def test_booleano_false_y_valor_cero_visibles(self):
        self.compilar("main { int x = 0; if x > 2 then end }")
        w = self.ventana
        self.assertEqual(w._items_arbol[w.arbol_semantico]["0.0.1.0"].text(2), "false")
        self.assertEqual(w._items_arbol[w.arbol_semantico]["0.0.0.1.0.0"].text(2), "0")


if __name__ == "__main__":
    unittest.main()
