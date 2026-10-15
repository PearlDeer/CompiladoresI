"""Contratos de fases, bloqueos, archivos y ejecucion real de la CLI."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "code" / "scripts"))
import compilador
from compiler.ast_node import ASTNode


class IntegracionTest(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory(prefix="fase3_cli_")
        self.addCleanup(self.temporal.cleanup)
        self.salidas = Path(self.temporal.name)

    def analizar(self, codigo, fase="semantico"):
        return compilador.analizar(codigo, fase, str(self.salidas))

    def ejecutar_cli(self, fase, fuente, archivo_salida=None):
        args = [sys.executable, "-B", "-X", "utf8", str(RAIZ / "code/scripts/compilador.py"),
                fase, str(fuente)]
        if archivo_salida:
            args.append(str(archivo_salida))
        args.extend(["--salidas", str(self.salidas / "artefactos")])
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=10)

    def test_bloqueo_lexico_no_invoca_fases_posteriores(self):
        with patch.object(compilador, "ejecutar_parser") as parser, \
                patch.object(compilador, "ejecutar_semantico") as semantico:
            r = self.analizar("main { int x; x = @; }")
        parser.assert_not_called()
        semantico.assert_not_called()
        self.assertEqual(r["estado_semantico"], "bloqueado")
        self.assertTrue(r["errores_lexicos"])
        self.assertEqual(r["errores_sintacticos"], [])
        self.assertEqual(r["errores_semanticos"], [])
        self.assertEqual(r["arbol"], {})
        self.assertEqual(r["arbol_semantico"], {})
        self.assertEqual(r["tabla_simbolos"], [])

    def test_sintaxis_estructural_bloquea_semantico(self):
        codigo = (RAIZ / "pruebas/con_errores.txt").read_text(encoding="utf-8")
        with patch.object(compilador, "ejecutar_semantico") as semantico:
            r = self.analizar(codigo)
        semantico.assert_not_called()
        self.assertEqual(len(r["errores_sintacticos"]), 13)
        self.assertEqual(r["estado"], "bloqueado")
        self.assertTrue(r["arbol"])
        self.assertEqual(r["arbol_semantico"], {})
        self.assertEqual(r["tabla_simbolos"], [])

    def test_sintaxis_fatal_bloquea_incluso_con_hueco_de_expresion(self):
        raiz = ASTNode("Programa").agregar(ASTNode("ErrorComponente"))
        error = {"tipo": "Error Sintactico Fatal", "descripcion": "Expresion demasiado profunda",
                 "linea": 1, "columna": 1}
        with patch.object(compilador, "ejecutar_parser", return_value=(raiz, [error])), \
                patch.object(compilador, "ejecutar_semantico") as semantico:
            r = self.analizar("main {}")
        semantico.assert_not_called()
        self.assertEqual(r["estado_semantico"], "bloqueado")

    def test_historico_parcial_se_mantiene_y_se_analiza(self):
        archivo = RAIZ / "testlexico.txt"
        anterior = archivo.read_bytes()
        r = self.analizar(anterior.decode("utf-8"))
        self.assertEqual(archivo.read_bytes(), anterior)
        self.assertEqual(r["estado_semantico"], "parcial")
        self.assertFalse(r["valido"])
        self.assertEqual(len(r["errores_sintacticos"]), 2)
        self.assertEqual(len(r["errores_semanticos"]), 8)
        self.assertEqual(len(r["tabla_simbolos"]), 6)
        self.assertTrue(r["arbol_semantico"])

    def test_listas_de_errores_no_se_mezclan(self):
        r = self.analizar((RAIZ / "testlexico.txt").read_text(encoding="utf-8"))
        self.assertTrue(all(e["tipo"] == "Error Sintactico" for e in r["errores_sintacticos"]))
        self.assertTrue(all(e["tipo"] == "Error Semantico" for e in r["errores_semanticos"]))
        self.assertEqual(r["errores_lexicos"], [])
        self.assertEqual(len(r["errores"]), 10)

    def test_archivos_y_json_coherentes(self):
        r = self.analizar("main { int x = 1; float y; y = x + 2.5; }")
        esperados = {"tokens.txt", "ast.txt", "ast_semantico.txt", "tabla_simbolos.txt",
                     "errores_lexicos.txt", "errores_sintacticos.txt", "errores_semanticos.txt",
                     "conversiones.txt", "traza_semantica.txt", "resultado.json"}
        self.assertTrue(esperados <= {p.name for p in self.salidas.iterdir()})
        self.assertEqual(json.loads((self.salidas / "resultado.json").read_text(encoding="utf-8")), r)
        self.assertIn("tipo_calculado", (self.salidas / "ast_semantico.txt").read_text(encoding="utf-8"))
        self.assertNotIn("tipo_calculado", (self.salidas / "ast.txt").read_text(encoding="utf-8"))
        self.assertIn("Desplazamiento", (self.salidas / "tabla_simbolos.txt").read_text(encoding="utf-8"))

    def test_limpieza_de_salidas_tras_bloqueo_y_fase_lexica(self):
        self.analizar("main { float x; x = 2; }")
        r = self.analizar("main { x = @; }")
        self.assertEqual(r["conversiones"], [])
        self.assertEqual((self.salidas / "ast.txt").read_text(encoding="utf-8"), "")
        self.assertIn("bloqueado", (self.salidas / "ast_semantico.txt").read_text(encoding="utf-8"))
        self.assertNotIn("referencia_tabla_simbolos", (self.salidas / "traza_semantica.txt").read_text(encoding="utf-8"))
        r = self.analizar("main { int x; }", "lexico")
        self.assertEqual(r["arbol"], {})
        self.assertEqual(r["arbol_semantico"], {})
        self.assertIn("no incluye", (self.salidas / "errores_semanticos.txt").read_text(encoding="utf-8"))

    def test_solo_fase_solicitada(self):
        with patch.object(compilador, "ejecutar_parser") as parser, \
                patch.object(compilador, "ejecutar_semantico") as semantico:
            self.analizar("main {}", "lexico")
        parser.assert_not_called()
        semantico.assert_not_called()
        with patch.object(compilador, "ejecutar_semantico") as semantico:
            r = self.analizar("main { int x; }", "sintactico")
        semantico.assert_not_called()
        self.assertTrue(r["arbol"])
        self.assertEqual(r["estado_semantico"], "no_ejecutado")

    def test_todos_los_errores_minimos_y_conversion_valida(self):
        r = self.analizar((RAIZ / "pruebas/semantico_errores.txt").read_text(encoding="utf-8"))
        self.assertEqual(r["errores_sintacticos"], [])
        self.assertEqual(len(r["errores_semanticos"]), 11)
        codigos = {e["codigo"] for e in r["errores_semanticos"]}
        self.assertTrue({"SEM_NO_DECLARADO", "SEM_DUPLICADO", "SEM_TIPOS_INCOMPATIBLES",
                         "SEM_CONVERSION_INVALIDA", "SEM_OPERADOR_INVALIDO",
                         "SEM_ASIGNACION_INCOMPATIBLE", "SEM_CONDICION_NO_BOOLEANA"} <= codigos)
        self.assertEqual(sum(e["codigo"] == "SEM_CONDICION_NO_BOOLEANA" for e in r["errores_semanticos"]), 3)
        self.assertEqual([(c["de"], c["a"]) for c in r["conversiones"]], [("int", "float")])

    def test_tabla_real_con_tipos_lineas_ambito_y_desplazamiento(self):
        r = self.analizar("main {\n int x;\n float y;\n cin >> x;\n y = x;\n cout << y;\n}")
        self.assertTrue(r["valido"])
        self.assertEqual([s["tipo"] for s in r["tabla_simbolos"]], ["int", "float"])
        self.assertEqual([s["lineas"] for s in r["tabla_simbolos"]], [[2, 4, 5], [3, 5, 6]])
        self.assertEqual([s["desplazamiento"] for s in r["tabla_simbolos"]], [0, 1])
        self.assertTrue(all(s["ambito"] == "global" and s["declarado"] for s in r["tabla_simbolos"]))

    def test_cli_tres_fases_cinco_archivos(self):
        archivos = ["pruebas/valido_1.txt", "pruebas/valido_2.txt", "pruebas/operadores_multilinea.txt",
                    "pruebas/con_errores.txt", "testlexico.txt"]
        claves = {"tokens", "errores_lexicos", "errores_sintacticos", "errores_semanticos",
                  "arbol", "arbol_semantico", "tabla_simbolos", "conversiones"}
        for fase in ("lexico", "sintactico", "semantico"):
            for nombre in archivos:
                with self.subTest(fase=fase, archivo=nombre):
                    proceso = self.ejecutar_cli(fase, RAIZ / nombre)
                    self.assertEqual(proceso.returncode, 0, proceso.stderr)
                    r = json.loads(proceso.stdout)
                    self.assertTrue(claves <= r.keys())
                    if nombre in archivos[:3]:
                        self.assertTrue(r["valido"])
                    if fase == "semantico" and nombre in archivos[:3]:
                        self.assertTrue(r["arbol_semantico"])

    def test_cli_json_a_archivo(self):
        destino = self.salidas / "respuesta.json"
        proceso = self.ejecutar_cli("semantico", RAIZ / "pruebas/semantico_valido.txt", destino)
        self.assertEqual(proceso.returncode, 0, proceso.stderr)
        self.assertEqual(proceso.stdout, "")
        r = json.loads(destino.read_text(encoding="utf-8"))
        self.assertTrue(r["valido"])

    def test_cli_archivo_ausente_error_de_ejecucion(self):
        proceso = self.ejecutar_cli("semantico", self.salidas / "ausente.txt")
        self.assertEqual(proceso.returncode, 1)
        r = json.loads(proceso.stdout)
        self.assertTrue(r["errores_ejecucion"])
        self.assertEqual(r["errores_semanticos"], [])
        guardado = json.loads((self.salidas / "artefactos/resultado.json").read_text(encoding="utf-8"))
        self.assertEqual(guardado, r)

    def test_cli_fase_desconocida(self):
        proceso = self.ejecutar_cli("otra", RAIZ / "testlexico.txt")
        self.assertNotEqual(proceso.returncode, 0)
        self.assertIn("semantico", proceso.stderr)


if __name__ == "__main__":
    unittest.main()
