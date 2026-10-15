"""Valores propagados, apariciones repetidas y expresiones completas de control."""

from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "code/scripts"))
from compiler.analisis_lexico import analisis_lexico
from compiler.analisis_sintactico import analisis_sintactico
from compiler.analisis_semantico import analisis_semantico


def nodos(arbol):
    yield arbol
    for hijo in arbol["hijos"]:
        yield from nodos(hijo)


class ValoresTest(unittest.TestCase):
    def analizar(self, fuente, recuperado=False):
        lexico = analisis_lexico(fuente)
        self.assertEqual(lexico["errores"], [])
        arbol, errores = analisis_sintactico(lexico["tokens"])
        if not recuperado:
            self.assertEqual(errores, [], fuente)
        return analisis_semantico(arbol)

    def simbolo(self, resultado, nombre):
        return next(s for s in resultado["tabla_simbolos"] if s["nombre"] == nombre)

    def asignaciones(self, resultado, nombre):
        return [n for n in nodos(resultado["arbol_semantico"])
                if n["nodo"] == "Asignacion" and n["hijos"][0]["valor"] == nombre]

    def test_cadena_y_seis_z_once_y_quince(self):
        r = self.analizar("main { int y, z; y = 5 + 2 - 1; z = y + 5; y = y + 9; }")
        self.assertTrue(r["valido"])
        self.assertEqual([n["atributos"]["valor_constante"] for n in self.asignaciones(r, "y")], [6, 15])
        ultima = self.asignaciones(r, "y")[-1]
        suma = ultima["hijos"][1]["hijos"][0]
        self.assertEqual(suma["hijos"][0]["atributos"]["valor_constante"], 6)
        self.assertEqual(suma["atributos"]["valor_constante"], 15)
        self.assertEqual(ultima["hijos"][0]["atributos"]["valor_constante"], 15)
        self.assertEqual(self.simbolo(r, "z")["valor_actual"], 11)

    def test_linea_registra_cinco_apariciones(self):
        r = self.analizar("main {\n int y;\n y = 1;\n y = y + y + y + y;\n}")
        s = self.simbolo(r, "y")
        self.assertEqual(s["lineas"], [2, 3, 4, 4, 4, 4, 4])
        self.assertEqual(len([o for o in s["ocurrencias"] if o["linea"] == 4]), 5)
        self.assertEqual(s["valor_actual"], 4)

    def test_asignacion_invalida_no_reemplaza_valor(self):
        r = self.analizar("main { int x = 2, y; x = 1.5; y = x + 1; }")
        self.assertEqual(self.simbolo(r, "x")["valor_actual"], 2)
        self.assertEqual(self.simbolo(r, "y")["valor_actual"], 3)
        self.assertEqual([e["codigo"] for e in r["errores_semanticos"]], ["SEM_CONVERSION_INVALIDA"])

    def test_cin_invalida_valor_anterior(self):
        r = self.analizar("main { int x = 1, y; cin >> x; y = x + 2; }")
        self.assertTrue(r["valido"])
        self.assertFalse(self.simbolo(r, "x")["valor_conocido"])
        self.assertFalse(self.simbolo(r, "y")["valor_conocido"])

    def test_if_conocido_no_filtra_valor_de_otra_rama(self):
        r = self.analizar("main { int x = 1, y; if true then x = 2; else x = 7; end y = x + 1; }")
        self.assertEqual(self.simbolo(r, "y")["valor_actual"], 3)

    def test_if_desconocido_ramas_distintas_invalida(self):
        r = self.analizar("main { bool b; int x = 1, y; cin >> b; if b then x = 2; else x = 7; end y = x + 1; }")
        self.assertFalse(self.simbolo(r, "y")["valor_conocido"])

    def test_if_desconocido_ramas_iguales_conserva(self):
        r = self.analizar("main { bool b; int x, y; cin >> b; if b then x = 2; else x = 2; end y = x + 1; }")
        self.assertEqual(self.simbolo(r, "y")["valor_actual"], 3)

    def test_if_sin_else_mezcla_valor_anterior(self):
        r = self.analizar("main { bool b; int x = 1; if b then x = 2; end }")
        self.assertFalse(self.simbolo(r, "x")["valor_conocido"])

    def test_while_falso_conserva_valores_anteriores(self):
        r = self.analizar("main { int x = 3; while x < 0 cin >> x; end }")
        self.assertEqual(self.simbolo(r, "x")["valor_actual"], 3)
        ciclo = next(n for n in nodos(r["arbol_semantico"]) if n["nodo"] == "IteracionWhile")
        self.assertIs(ciclo["atributos"]["resultado_condicion"], False)

    def test_while_no_supone_una_sola_iteracion(self):
        r = self.analizar("main { int x = 0, k = 7, y; while x < 3 x++; end y = k + 1; }")
        self.assertFalse(self.simbolo(r, "x")["valor_conocido"])
        self.assertEqual(self.simbolo(r, "y")["valor_actual"], 8)
        ciclo = next(n for n in nodos(r["arbol_semantico"]) if n["nodo"] == "IteracionWhile")
        self.assertIs(ciclo["atributos"]["resultado_condicion"], True)
        self.assertEqual(ciclo["hijos"][0]["atributos"]["contexto_valor"], "entrada del while")

    def test_do_while_falso_propaga_una_iteracion(self):
        r = self.analizar("main { int y = 6, z; do y = y + 9; while false; z = y + 1; }")
        self.assertEqual(self.simbolo(r, "z")["valor_actual"], 16)

    def test_do_while_verdadero_valor_inicial_y_salida_desconocida(self):
        r = self.analizar("main { int y = 6; do y = y + 9; while y < 100; }")
        self.assertEqual(self.asignaciones(r, "y")[0]["atributos"]["valor_constante"], 15)
        self.assertFalse(self.simbolo(r, "y")["valor_conocido"])
        ciclo = next(n for n in nodos(r["arbol_semantico"]) if n["nodo"] == "RepeticionDoWhile")
        self.assertIs(ciclo["atributos"]["resultado_condicion"], True)

    def test_incremento_postfix_propaga_y_devuelve_valor_anterior(self):
        r = self.analizar("main { int x = 1, y; y = x++; x--; }")
        self.assertEqual(self.simbolo(r, "y")["valor_actual"], 1)
        self.assertEqual(self.simbolo(r, "x")["valor_actual"], 1)

    def test_cortocircuito_no_aplica_incremento_omitido(self):
        for expresion in ("false && (x++ > 0)", "true || (x++ > 0)"):
            with self.subTest(expresion=expresion):
                r = self.analizar(f"main {{ int x = 1; bool b; b = {expresion}; }}")
                self.assertTrue(r["valido"])
                self.assertEqual(self.simbolo(r, "x")["valor_actual"], 1)

    def test_cortocircuito_desconocido_mezcla_efectos(self):
        r = self.analizar("main { bool b; int x = 1; b = b && (x++ < 0); }")
        self.assertFalse(self.simbolo(r, "x")["valor_conocido"])
        self.assertIs(self.simbolo(r, "b")["valor_actual"], False)

    def test_booleano_desconocido_no_se_inventa(self):
        r = self.analizar("main { float a = 55, b; if a > b then end }")
        condicion = next(n for n in nodos(r["arbol_semantico"]) if n["nodo"] == "OperacionRelacional")
        self.assertEqual(condicion["atributos"]["tipo_calculado"], "bool")
        self.assertIsNone(condicion["atributos"]["resultado_condicion"])
        self.assertFalse(condicion["atributos"]["es_constante"])

    def test_operadores_en_if_while_y_do_while(self):
        expresiones = {
            "x + y == 6": True, "x - y == 2": True, "x * y == 8": True,
            "x / y == 2": True, "x % y == 0": True, "x ^ y == 16": True,
            "x < y": False, "x <= y": False, "x > y": True, "x >= y": True,
            "x == y": False, "x != y": True, "!b": False,
            "(x > y) && (y != 0)": True, "(x < y) || (y == 2)": True,
            "x++ > y": True, "x-- > y": True,
        }
        for expresion, esperado in expresiones.items():
            for plantilla, clase in (("if ({}) then end", "Seleccion"),
                                     ("while ({}) end", "IteracionWhile"),
                                     ("do while ({});", "RepeticionDoWhile")):
                with self.subTest(expresion=expresion, clase=clase):
                    r = self.analizar("main { int x = 4, y = 2; bool b = true; " + plantilla.format(expresion) + " }")
                    self.assertTrue(r["valido"], r["errores_semanticos"])
                    control = next(n for n in nodos(r["arbol_semantico"]) if n["nodo"] == clase)
                    self.assertIs(control["atributos"]["resultado_condicion"], esperado)

    def test_logico_incompleto_sigue_siendo_error_sintactico(self):
        r = self.analizar("main { int x = 4; do x++; while (x == 4 &&); }", recuperado=True)
        self.assertFalse(r["valido"])
        self.assertEqual(r["estado"], "parcial")
        logico = next(n for n in nodos(r["arbol_semantico"]) if n["nodo"] == "OperacionLogica")
        self.assertEqual(logico["atributos"]["tipo_calculado"], "error")

    def test_ejemplo_historico_conserva_y_quince_y_comparacion_desconocida(self):
        r = self.analizar((RAIZ / "testlexico.txt").read_text(encoding="utf-8"), recuperado=True)
        y = self.asignaciones(r, "y")
        self.assertEqual([n["atributos"].get("valor_constante") for n in y[:3]], [6, 15, -2])
        primero = next(n for n in nodos(r["arbol_semantico"]) if n["nodo"] == "Seleccion")
        self.assertIsNone(primero["atributos"]["resultado_condicion"])


if __name__ == "__main__":
    unittest.main()
