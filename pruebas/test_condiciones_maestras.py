"""Regresiones sobre el programa completo compartido y variantes controladas."""

import hashlib
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "code/scripts"))
from compilador import analizar


def nodos(arbol):
    yield arbol
    for hijo in arbol["hijos"]:
        yield from nodos(hijo)


class CondicionesMaestrasTest(unittest.TestCase):
    def setUp(self):
        self.original = (RAIZ / "pruebas/maestro_condiciones_original.txt").read_text(encoding="utf-8")
        self.valido = (RAIZ / "pruebas/maestro_condiciones_valido.txt").read_text(encoding="utf-8")

    def compilar(self, fuente):
        r = analizar(fuente)
        self.assertEqual(r["errores_lexicos"], [])
        self.assertEqual(r["errores_sintacticos"], [])
        return r

    def controles(self, r):
        return [n for n in nodos(r["arbol_semantico"])
                if n["nodo"] in {"Seleccion", "IteracionWhile", "RepeticionDoWhile"}]

    def test_original_exacto_sin_false_inventado(self):
        r = self.compilar(self.original)
        self.assertEqual(len(r["errores_semanticos"]), 8)
        c = self.controles(r)[0]["atributos"]
        self.assertIsNone(c["resultado_booleano"])
        self.assertEqual(c["motivo_desconocido"], "b sin inicializar")
        relacion = next(n for n in nodos(r["arbol_semantico"]) if n["nodo"] == "OperacionRelacional")
        self.assertEqual(relacion["atributos"]["operandos_evaluados"][0]["valor"], 55.0)
        self.assertFalse(relacion["atributos"]["operandos_evaluados"][1]["conocido"])

    def test_maestro_valido_resultados_de_todos_los_controles(self):
        r = self.compilar(self.valido)
        self.assertTrue(r["valido"], r["errores_semanticos"])
        self.assertEqual([n["atributos"]["resultado_booleano"] for n in self.controles(r)],
                         [True, True, False, False, True, False, False, True])
        for n in nodos(r["arbol_semantico"]):
            a = n["atributos"]
            if a.get("tipo_calculado") == "bool" and n["nodo"] != "Tipo":
                self.assertIn("resultado_booleano", a)
                if a.get("es_constante"):
                    self.assertIs(a["resultado_booleano"], a["valor_constante"])
        self.assertTrue(r["conversiones"])

    def test_mismo_maestro_if_verdadero_y_falso(self):
        for b, esperado in [(10.0, True), (100.0, False), (55.0, False)]:
            with self.subTest(b=b):
                r = self.compilar(self.valido.replace("b = 10.0,", f"b = {b},"))
                self.assertTrue(r["valido"])
                self.assertIs(self.controles(r)[0]["atributos"]["resultado_booleano"], esperado)

    def test_mismo_maestro_if_anidado_verdadero_y_falso(self):
        for suma, esperado in [(99, True), (1, False)]:
            with self.subTest(suma=suma):
                fuente = self.valido.replace("b = 10.0,", "b = 100.0,").replace("suma = 99;", f"suma = {suma};")
                r = self.compilar(fuente)
                self.assertTrue(r["valido"])
                self.assertIs(self.controles(r)[1]["atributos"]["resultado_booleano"], esperado)

    def test_mismo_maestro_do_logico_true_false(self):
        for expresion, esperado in [("x==6 && y==9", True), ("x==4 && y!=9", False),
                                    ("x==4 || y==9", True), ("!(x==6)", False)]:
            with self.subTest(expresion=expresion):
                r = self.compilar(self.valido.replace("x==4 && y!=9", expresion))
                self.assertTrue(r["valido"])
                c = next(n for n in self.controles(r) if n["nodo"] == "RepeticionDoWhile")
                self.assertIs(c["atributos"]["resultado_booleano"], esperado)

    def test_mismo_maestro_entrada_no_fabrica_resultado(self):
        r = self.compilar(self.valido.replace("if (a > b)", "cin >> b;\n    if (a > b)"))
        self.assertTrue(r["valido"])
        a = self.controles(r)[0]["atributos"]
        self.assertIsNone(a["resultado_booleano"])
        self.assertIn("b recibido por cin", a["motivo_desconocido"])

    def test_mismo_maestro_tipos_incorrectos_no_se_convierten_a_bool(self):
        for expresion in ["x", "a", "x && y"]:
            with self.subTest(expresion=expresion):
                r = self.compilar(self.valido.replace("if (a > b)", f"if ({expresion})"))
                c = self.controles(r)[0]["atributos"]
                self.assertFalse(c["condicion_valida"])
                self.assertIsNone(c["resultado_booleano"])
                self.assertTrue(r["errores_semanticos"])

    def test_mismo_maestro_operador_incompleto_sigue_siendo_error(self):
        r = analizar(self.original.replace("x==4 && y!=9", "x==4 &&"))
        self.assertTrue(r["errores_sintacticos"])
        self.assertFalse(r["valido"])

    def test_cortocircuito_con_desconocido_tiene_resultado(self):
        for expresion, esperado in [("false && b", False), ("true || b", True)]:
            r = self.compilar(f"main {{ bool b; if ({expresion}) then cout << 1; end }}")
            self.assertTrue(r["valido"])
            c = self.controles(r)[0]["atributos"]
            self.assertIs(c["resultado_booleano"], esperado)
            self.assertNotIn("motivo_desconocido", c)

    def test_motivo_sobrevive_asignacion_y_union_de_ramas(self):
        r = self.compilar("main { int x, y; cin >> x; y = x + 1; if y > 0 then cout << y; end }")
        self.assertIn("x recibido por cin", self.controles(r)[0]["atributos"]["motivo_desconocido"])
        r = self.compilar("main { bool b; int x; if b then x=1; else x=2; end if x>0 then cout << x; end }")
        self.assertIn("ramas alternativas", self.controles(r)[1]["atributos"]["motivo_desconocido"])

    def test_ast_original_y_archivo_historico_no_mutados(self):
        historico = RAIZ / "testlexico.txt"
        antes = hashlib.sha256(historico.read_bytes()).hexdigest()
        r = self.compilar(self.valido)
        self.assertTrue(all("resultado_booleano" not in n["atributos"] for n in nodos(r["arbol"])))
        self.assertEqual(hashlib.sha256(historico.read_bytes()).hexdigest(), antes)


if __name__ == "__main__":
    unittest.main()
