"""Validacion de Fase 3: python -B -m unittest discover -s pruebas -v."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "code" / "scripts"))

from compiler.analisis_lexico import analisis_lexico
from compiler.analisis_sintactico import analisis_sintactico
from compiler.analisis_semantico import AnalizadorSemantico, TablaSimbolos, analisis_semantico
from compiler.ast_node import ASTNode
from compiler.errores import ErrorCompilador


def nodos(arbol):
    yield arbol
    for hijo in arbol["hijos"]:
        yield from nodos(hijo)


class SemanticaTest(unittest.TestCase):
    def analizar(self, fuente):
        lexico = analisis_lexico(fuente)
        self.assertEqual(lexico["errores"], [])
        arbol, errores = analisis_sintactico(lexico["tokens"])
        self.assertEqual(errores, [], fuente)
        return analisis_semantico(arbol)

    def codigos(self, resultado):
        return [e["codigo"] for e in resultado["errores_semanticos"]]

    def simbolos(self, resultado):
        return {s["nombre"]: s for s in resultado["tabla_simbolos"]}

    def encontrar(self, resultado, nombre, valor=None):
        return [n for n in nodos(resultado["arbol_semantico"])
                if n["nodo"] == nombre and (valor is None or n["valor"] == valor)]

    def test_programa_valido_existente(self):
        resultado = self.analizar((RAIZ / "pruebas" / "valido_1.txt").read_text(encoding="utf-8"))
        self.assertTrue(resultado["valido"])
        self.assertEqual(resultado["estado"], "completo")
        simbolos = self.simbolos(resultado)
        self.assertEqual({k: s["tipo"] for k, s in simbolos.items()},
                         {"x": "int", "y": "int", "promedio": "float", "activo": "bool"})
        self.assertTrue(all(s["inicializado"] for s in simbolos.values()))
        self.assertGreater(len(resultado["conversiones"]), 0)
        json.dumps(resultado, allow_nan=False)

    def test_no_declarado_no_inventa_simbolo_y_conserva_ubicacion(self):
        resultado = self.analizar("main {\n  int x;\n  x = ausente + 1;\n}")
        self.assertEqual(self.codigos(resultado), ["SEM_NO_DECLARADO"])
        error = resultado["errores_semanticos"][0]
        self.assertEqual((error["linea"], error["columna"]), (3, 7))
        self.assertEqual(set(self.simbolos(resultado)), {"x"})
        self.assertFalse(self.simbolos(resultado)["x"]["inicializado"])

    def test_duplicado_conserva_tipo_y_direccion_original(self):
        resultado = self.analizar("main { int x; float x = 1.5; int y; }")
        self.assertEqual(self.codigos(resultado), ["SEM_DUPLICADO"])
        self.assertEqual(self.simbolos(resultado)["x"]["tipo"], "int")
        self.assertFalse(self.simbolos(resultado)["x"]["inicializado"])
        self.assertEqual([s["direccion"] for s in resultado["tabla_simbolos"]], [0, 1])

    def test_float_a_int_invalido(self):
        resultado = self.analizar("main { int x; x = 1.5; }")
        self.assertEqual(self.codigos(resultado), ["SEM_CONVERSION_INVALIDA"])
        self.assertFalse(self.simbolos(resultado)["x"]["inicializado"])

    def test_int_a_float_con_conversion_en_ast(self):
        resultado = self.analizar("main { float x; x = 3; }")
        self.assertTrue(resultado["valido"])
        self.assertEqual(len(resultado["conversiones"]), 1)
        expresion = self.encontrar(resultado, "SentExpresion")[0]
        atributos = expresion["atributos"]
        self.assertEqual(atributos["tipo_calculado"], "int")
        self.assertEqual(atributos["tipo_contextual"], "float")
        self.assertEqual(atributos["conversion_aplicada"], resultado["conversiones"])
        self.assertTrue(self.simbolos(resultado)["x"]["inicializado"])

    def test_bool_en_aritmetica(self):
        for op in ("+", "-", "*", "/", "%", "^"):
            with self.subTest(op=op):
                resultado = self.analizar(f"main {{ int x; x = true {op} 2; }}")
                self.assertEqual(self.codigos(resultado), ["SEM_OPERADOR_INVALIDO"])

    def test_condiciones_no_booleanas(self):
        for valor in ("1", "1.5"):
            for sentencia in (f"if {valor} then end", f"while {valor} end",
                              f"do while {valor};"):
                with self.subTest(sentencia=sentencia):
                    resultado = self.analizar("main { " + sentencia + " }")
                    self.assertEqual(self.codigos(resultado), ["SEM_CONDICION_NO_BOOLEANA"])

    def test_relacionales_logicos_y_condiciones_validas(self):
        resultado = self.analizar("""main {
          int x; float y; bool b;
          x = 2; y = 3.5;
          b = (x < y) && !false || (true == false);
          if b then cout << x; else cout << y; end
          while x < 3 x++; end
          do x--; while x > 0;
        }""")
        self.assertTrue(resultado["valido"])
        for nombre in ("OperacionLogica", "OperacionRelacional"):
            self.assertTrue(all(n["atributos"]["tipo_calculado"] == "bool"
                                for n in self.encontrar(resultado, nombre)))

    def test_operadores_logicos_requieren_booleanos(self):
        for expresion in ("1 && true", "false || 2.0", "!1"):
            with self.subTest(expresion=expresion):
                resultado = self.analizar(f"main {{ bool b; b = {expresion}; }}")
                self.assertEqual(self.codigos(resultado), ["SEM_OPERADOR_INVALIDO"])

    def test_relacionales_incompatibles(self):
        for expresion in ("true < false", "true == 1", "2.0 != false"):
            with self.subTest(expresion=expresion):
                resultado = self.analizar(f"main {{ bool b; b = {expresion}; }}")
                self.assertEqual(self.codigos(resultado), ["SEM_TIPOS_INCOMPATIBLES"])

    def test_asignaciones_bool_numero(self):
        for declaracion, valor in (("int", "true"), ("float", "false"), ("bool", "1")):
            with self.subTest(tipo=declaracion):
                resultado = self.analizar(f"main {{ {declaracion} x; x = {valor}; }}")
                self.assertEqual(self.codigos(resultado), ["SEM_ASIGNACION_INCOMPATIBLE"])

    def test_cin_cout_declarados(self):
        resultado = self.analizar('main { int x; cin >> x; cout << "x" << x; }')
        self.assertTrue(resultado["valido"])
        self.assertTrue(self.simbolos(resultado)["x"]["inicializado"])
        self.assertEqual([o["contexto"] for o in self.simbolos(resultado)["x"]["ocurrencias"]],
                         ["declaracion", "entrada", "lectura"])

    def test_cin_cout_no_declarados_continua(self):
        resultado = self.analizar('main { cin >> x; cout << y; int z; z = 2; }')
        self.assertEqual(self.codigos(resultado), ["SEM_NO_DECLARADO", "SEM_NO_DECLARADO"])
        self.assertTrue(self.simbolos(resultado)["z"]["inicializado"])

    def test_ast_original_independiente(self):
        lexico = analisis_lexico("main { float x; x = 1 + 2.0; }")
        arbol, errores = analisis_sintactico(lexico["tokens"])
        self.assertFalse(errores)
        anterior = deepcopy(arbol.to_dict())
        resultado = analisis_semantico(arbol)
        self.assertEqual(arbol.to_dict(), anterior)
        self.assertEqual(resultado["arbol_original"], anterior)
        self.assertEqual(arbol.atributos, {})
        resultado["arbol_semantico"]["hijos"][0]["atributos"]["ambito"] = "alterado"
        self.assertEqual(arbol.to_dict(), anterior)
        self.assertEqual(resultado["arbol_original"], anterior)

    def test_atributos_heredados_referencias_y_direcciones(self):
        resultado = self.analizar("main { int a, b; float c; bool d; a = 1; }")
        simbolos = self.simbolos(resultado)
        for nombre, tipo in (("a", "int"), ("b", "int"), ("c", "float"), ("d", "bool")):
            for nodo in self.encontrar(resultado, "Identificador", nombre):
                atributos = nodo["atributos"]
                self.assertEqual(atributos["tipo_declarado"], tipo)
                self.assertEqual(atributos["tipo_calculado"], tipo)
                self.assertEqual(atributos["referencia_tabla_simbolos"], simbolos[nombre]["id"])
                self.assertEqual(atributos["direccion"], simbolos[nombre]["direccion"])
                self.assertEqual(atributos["ambito"], "global")
        self.assertEqual([s["desplazamiento"] for s in resultado["tabla_simbolos"]], [0, 1, 2, 3])
        self.assertTrue(all(s["declarado"] for s in simbolos.values()))

    def test_lineas_y_columnas_de_cada_ocurrencia(self):
        resultado = self.analizar("main {\n  int x;\n  x = 1;\n  cout << x + x;\n}")
        simbolo = self.simbolos(resultado)["x"]
        self.assertEqual(simbolo["lineas"], [2, 3, 4, 4])
        self.assertEqual(simbolo["lineas_unicas"], [2, 3, 4])
        self.assertEqual(simbolo["columna"], 7)
        self.assertEqual([(o["linea"], o["columna"]) for o in simbolo["ocurrencias"]],
                         [(2, 7), (3, 3), (4, 11), (4, 15)])

    def test_aritmetica_tipos_y_constantes(self):
        resultado = self.analizar("main { int a = 2 + 3 * 4; float b = 1 + 2.5; float c = 1.5 + 2.5; }")
        self.assertTrue(resultado["valido"])
        simbolos = self.simbolos(resultado)
        self.assertEqual(simbolos["a"]["valor_inicial_constante"], 14)
        self.assertEqual(simbolos["b"]["valor_inicial_constante"], 3.5)
        self.assertEqual(simbolos["c"]["valor_inicial_constante"], 4.0)
        self.assertEqual(len(resultado["conversiones"]), 1)

    def test_division_resto_y_potencia_enteros(self):
        resultado = self.analizar("main { int a = (0 - 7) / 3, b = (0 - 7) % 3, c = 2 ^ 3 ^ 2; }")
        self.assertTrue(resultado["valido"])
        self.assertEqual([self.simbolos(resultado)[n]["valor_inicial_constante"] for n in ("a", "b", "c")],
                         [-2, -1, 64])

    def test_modulo_float_invalido(self):
        resultado = self.analizar("main { float x; x = 2.5 % 2; }")
        self.assertEqual(self.codigos(resultado), ["SEM_OPERADOR_INVALIDO"])

    def test_divisor_cero_y_dominio_constante(self):
        for expresion, codigo in (("1 / 0", "SEM_DIVISION_CERO"),
                                  ("1 % 0", "SEM_DIVISION_CERO"),
                                  ("2 ^ (0 - 1)", "SEM_DOMINIO_CONSTANTE")):
            with self.subTest(expresion=expresion):
                resultado = self.analizar(f"main {{ int x; x = {expresion}; }}")
                self.assertEqual(self.codigos(resultado), [codigo])

    def test_propaga_valores_conocidos_de_identificadores(self):
        resultado = self.analizar("main { int x = 1, y = x + 2; }")
        suma = self.encontrar(resultado, "OperacionSuma")[0]
        self.assertTrue(suma["atributos"]["es_constante"])
        self.assertEqual(suma["atributos"]["valor_constante"], 3)
        self.assertEqual(self.simbolos(resultado)["y"]["valor_inicial_constante"], 3)

    def test_inicializacion_declaraciones_y_conversiones(self):
        resultado = self.analizar("main { int a, b = 2; float c = 3; int d = 2.5; }")
        self.assertEqual(self.codigos(resultado), ["SEM_CONVERSION_INVALIDA"])
        self.assertEqual({n: s["inicializado"] for n, s in self.simbolos(resultado).items()},
                         {"a": False, "b": True, "c": True, "d": False})
        self.assertEqual(self.simbolos(resultado)["c"]["valor_inicial_constante"], 3.0)

    def test_if_inicializacion_segura_en_ambas_ramas(self):
        resultado = self.analizar("main { bool b; int x; cin >> b; if b then x = 1; else x = 2; end }")
        self.assertTrue(resultado["valido"])
        self.assertTrue(self.simbolos(resultado)["x"]["inicializado"])

    def test_if_una_rama_no_asegura_inicializacion(self):
        resultado = self.analizar("main { bool b; int x; cin >> b; if b then x = 1; end }")
        self.assertTrue(resultado["valido"])
        self.assertFalse(self.simbolos(resultado)["x"]["inicializado"])

    def test_if_constante_selecciona_estado_sin_omitir_errores(self):
        resultado = self.analizar("main { int x; if true then x = 1; else cout << ausente; end }")
        self.assertEqual(self.codigos(resultado), ["SEM_NO_DECLARADO"])
        self.assertTrue(self.simbolos(resultado)["x"]["inicializado"])

    def test_while_no_asegura_inicializacion(self):
        resultado = self.analizar("main { bool b; int x; cin >> b; while b x = 1; end }")
        self.assertTrue(resultado["valido"])
        self.assertFalse(self.simbolos(resultado)["x"]["inicializado"])

    def test_do_while_inicializa_al_menos_una_vez(self):
        resultado = self.analizar("main { int x; do x = 1; while false; }")
        self.assertTrue(resultado["valido"])
        self.assertTrue(self.simbolos(resultado)["x"]["inicializado"])

    def test_incremento_numerico_y_errores(self):
        self.assertTrue(self.analizar("main { int x; float y; x++; y--; }")["valido"])
        for fuente in ("main { bool b; b++; }", "main { int x; x = (1 + 2)++; }",
                       "main { int x, y; x = x ++ y; }"):
            with self.subTest(fuente=fuente):
                self.assertEqual(self.codigos(self.analizar(fuente)), ["SEM_OPERADOR_INVALIDO"])

    def test_asignacion_vacia(self):
        resultado = self.analizar("main { int x; x = ; }")
        self.assertEqual(self.codigos(resultado), ["SEM_EXPRESION_VACIA"])

    def test_traza_muestra_herencia_sintesis_tabla_conversion(self):
        resultado = self.analizar("main { int x; float y; x = 1; y = x + 2.5; }")
        traza = resultado["traza_semantica"]
        self.assertEqual([e["paso"] for e in traza], list(range(1, len(traza) + 1)))
        self.assertTrue({"heredar", "propagar", "insertar", "buscar", "convertir", "comprobar"}
                        <= {e["accion"] for e in traza})
        ids = {n["atributos"]["id_nodo"] for n in nodos(resultado["arbol_semantico"])}
        self.assertTrue(all(e["nodo"] in ids for e in traza))

    def test_ambito_global_duplicado_en_bloque(self):
        resultado = self.analizar("main { int x; if true then float x; end }")
        self.assertEqual(self.codigos(resultado), ["SEM_DUPLICADO"])

    def test_uso_anterior_a_declaracion(self):
        resultado = self.analizar("main { x = 1; int x; }")
        self.assertEqual(self.codigos(resultado), ["SEM_NO_DECLARADO"])
        self.assertFalse(self.simbolos(resultado)["x"]["inicializado"])

    def test_parser_recuperado_no_se_declara_valido(self):
        lexico = analisis_lexico("main { int x; x = 1 + ; int y; y = 2; }")
        arbol, errores = analisis_sintactico(lexico["tokens"])
        self.assertTrue(errores)
        resultado = analisis_semantico(arbol)
        self.assertEqual(resultado["estado"], "parcial")
        self.assertFalse(resultado["valido"])
        self.assertTrue(self.simbolos(resultado)["y"]["inicializado"])

    def test_limite_constantes_no_limita_tipos(self):
        resultado = self.analizar("main { int x; x = 2 ^ 1000000; }")
        self.assertTrue(resultado["valido"])
        potencia = self.encontrar(resultado, "OperacionPotencia")[0]
        self.assertEqual(potencia["atributos"]["tipo_calculado"], "int")
        self.assertNotIn("valor_constante", potencia["atributos"])

    def test_reutilizar_analizador_no_acumula_estado(self):
        analizador = AnalizadorSemantico()
        primero = analizador.analizar(ASTNode("Programa").agregar(ASTNode("ErrorComponente")))
        segundo = analizador.analizar(ASTNode("Programa"))
        self.assertEqual(primero["estado"], "parcial")
        self.assertTrue(segundo["valido"])
        self.assertEqual(segundo["tabla_simbolos"], [])


class ContratosTest(unittest.TestCase):
    def test_tabla_operaciones_y_ambitos(self):
        tabla = TablaSimbolos()
        primero = tabla.insertar("x", "int", 2, 7)
        self.assertIs(tabla.buscar("x"), primero)
        self.assertEqual(tabla.obtener_tipo("x"), "int")
        self.assertTrue(tabla.detectar_duplicado("x"))
        self.assertIsNone(tabla.insertar("x", "float", 3, 2))
        self.assertIsNone(tabla.buscar("ausente"))
        self.assertIsNone(tabla.obtener_tipo("ausente"))
        self.assertIsNone(tabla.registrar_uso("ausente", 4, 3))
        otro = tabla.insertar("x", "bool", 5, 2, "otro")
        self.assertEqual(tabla.obtener_tipo("x", "otro"), "bool")
        self.assertNotEqual(primero["direccion"], otro["direccion"])
        tabla.registrar_uso("x", 6, 3)
        self.assertEqual(primero["lineas"], [2, 6])
        exportado = tabla.exportar()
        exportado[0]["lineas"].append(99)
        self.assertEqual(primero["lineas"], [2, 6])

    def test_ast_constructor_texto_y_serializacion_compatibles(self):
        hijo = ASTNode("Hijo", "1", "NUMERO_ENTERO")
        arbol = ASTNode("Programa", "", "", [hijo])
        self.assertEqual(arbol.to_text(), "Programa\n  Hijo: 1 [NUMERO_ENTERO]")
        hijo.atributos["conversion_aplicada"] = [{"a": "float"}]
        datos = arbol.to_dict()
        datos["hijos"][0]["atributos"]["conversion_aplicada"][0]["a"] = "bool"
        self.assertEqual(hijo.atributos["conversion_aplicada"][0]["a"], "float")
        self.assertIn("conversion_aplicada", arbol.to_text(incluir_atributos=True))

    def test_error_conserva_contrato_anterior(self):
        error = ErrorCompilador("Error Lexico", "mensaje", 2, 3)
        self.assertEqual(error.to_dict(), {"tipo": "Error Lexico", "descripcion": "mensaje",
                                          "linea": 2, "columna": 3})

    def test_ubicacion_operadores_identificadores_y_grupos(self):
        fuente = "main {\n  int x;\n  x = (1 + 2);\n}"
        lexico = analisis_lexico(fuente)
        self.assertTrue(all(set(t) == {"no", "token", "lexema", "tipo", "linea", "columna"}
                            for t in lexico["tokens"]))
        arbol, errores = analisis_sintactico(lexico["tokens"])
        self.assertFalse(errores)
        por_nombre = {}
        for nodo in nodos(arbol.to_dict()):
            self.assertGreater(nodo["linea"], 0)
            self.assertGreater(nodo["columna"], 0)
            por_nombre.setdefault(nodo["nodo"], []).append(nodo)
        self.assertEqual((por_nombre["OperacionSuma"][0]["linea"],
                          por_nombre["OperacionSuma"][0]["columna"]), (3, 10))
        self.assertEqual(por_nombre["Grupo"][0]["columna"], 7)
        self.assertEqual(por_nombre["Identificador"][0]["columna"], 7)

    def test_regresion_operadores_multilinea(self):
        fuente = (RAIZ / "pruebas" / "operadores_multilinea.txt").read_text(encoding="utf-8")
        lexico = analisis_lexico(fuente)
        arbol, errores = analisis_sintactico(lexico["tokens"])
        self.assertFalse(errores)
        self.assertTrue(analisis_semantico(arbol)["valido"])
        tokens_operadores = {(t["linea"], t["columna"]) for t in lexico["tokens"]
                            if t["token"] in {"++", "--", "==", "<<", ">>"}}
        for nodo in nodos(arbol.to_dict()):
            if nodo["nodo"] in {"OperacionIncremento", "OperacionRelacional"}:
                self.assertIn((nodo["linea"], nodo["columna"]), tokens_operadores)


if __name__ == "__main__":
    unittest.main()
