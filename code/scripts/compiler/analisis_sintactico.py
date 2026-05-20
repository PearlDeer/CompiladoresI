from .ast_node import ASTNode
from .errores import ErrorCompilador


class Parser:
    """Parser descendente recursivo para la gramatica del proyecto."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errores = []

    def actual(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        if self.tokens:
            ultimo = self.tokens[-1]
            return {"token": "EOF", "lexema": "EOF", "tipo": "EOF", "linea": ultimo["linea"], "columna": ultimo["columna"] + len(ultimo["token"])}
        return {"token": "EOF", "lexema": "EOF", "tipo": "EOF", "linea": 1, "columna": 1}

    def avanzar(self):
        token = self.actual()
        if self.pos < len(self.tokens):
            self.pos += 1
        return token

    def mirar(self, distancia=1):
        indice = self.pos + distancia
        if indice < len(self.tokens):
            return self.tokens[indice]
        return {"token": "EOF", "lexema": "EOF", "tipo": "EOF", "linea": self.actual()["linea"], "columna": self.actual()["columna"]}

    def es(self, lexema=None, tipo=None):
        token = self.actual()
        if lexema is not None and token["token"] != lexema:
            return False
        if tipo is not None and token["tipo"] != tipo:
            return False
        return True

    def coincidir(self, lexema=None, tipo=None, mensaje=None):
        """Consume un token esperado o registra error recuperable."""
        if self.es(lexema, tipo):
            return self.avanzar()

        token = self.actual()
        esperado = lexema or tipo
        self.error(mensaje or f"Se esperaba '{esperado}' y se encontro '{token['token']}'")
        return None

    def error(self, mensaje, tipo="Error Sintactico"):
        token = self.actual()
        self.errores.append(ErrorCompilador(tipo, mensaje, token["linea"], token["columna"]).to_dict())

    def sincronizar(self, paradas=None):
        """Avanza hasta un punto seguro para continuar despues de un error."""
        paradas = paradas or {";", "end", "else", "while", "EOF"}
        while not self.es("EOF") and self.actual()["token"] not in paradas:
            self.avanzar()
        if self.es(";"):
            self.avanzar()

    def parse(self):
        """programa -> main { lista_declaracion }"""
        raiz = ASTNode("Programa")
        self.coincidir("main", mensaje="El programa debe iniciar con 'main'")
        self.coincidir("{", mensaje="Se esperaba '{' despues de main")
        raiz.agregar(self.lista_declaracion({"}", "EOF"}))
        self.coincidir("}", mensaje="Se esperaba '}' para cerrar main")
        if not self.es("EOF"):
            self.error("Hay tokens despues del cierre del programa")
        return raiz

    def lista_declaracion(self, finales):
        """lista_declaracion -> declaracion*"""
        nodo = ASTNode("ListaDeclaracion")
        while not self.es("EOF") and self.actual()["token"] not in finales:
            declaracion = self.declaracion()
            if declaracion is None:
                self.sincronizar(finales | {";"})
            else:
                nodo.agregar(declaracion)
        return nodo

    def declaracion(self):
        """declaracion -> declaracion_variable | sentencia"""
        if self.actual()["token"] in {"int", "float", "bool"}:
            return self.declaracion_variable()
        return self.sentencia()

    def declaracion_variable(self):
        """declaracion_variable -> tipo identificador ;"""
        nodo = ASTNode("DeclaracionVariable")
        tipo = self.tipo()
        nodo.agregar(tipo)
        nodo.agregar(self.identificador())
        self.coincidir(";", mensaje="Falta ';' al final de la declaracion de variable")
        return nodo

    def tipo(self):
        """tipo -> int | float | bool"""
        token = self.actual()
        if token["token"] in {"int", "float", "bool"}:
            self.avanzar()
            return ASTNode("Tipo", token["token"], "tipo")
        self.error("Se esperaba un tipo: int, float o bool")
        return ASTNode("TipoError", token["token"], "error")

    def identificador(self):
        """identificador -> id (, id)*"""
        nodo = ASTNode("Identificadores")
        tok = self.coincidir(tipo="IDENTIFICADOR", mensaje="Se esperaba un identificador")
        if tok:
            nodo.agregar(ASTNode("Identificador", tok["token"], "id"))
        while self.es(","):
            self.avanzar()
            tok = self.coincidir(tipo="IDENTIFICADOR", mensaje="Se esperaba identificador despues de ','")
            if tok:
                nodo.agregar(ASTNode("Identificador", tok["token"], "id"))
        return nodo

    def sentencia(self):
        """sentencia -> seleccion | iteracion | repeticion | sent_in | sent_out | asignacion"""
        token = self.actual()
        try:
            if token["token"] == "if":
                return self.seleccion()
            if token["token"] == "while":
                return self.iteracion()
            if token["token"] == "do":
                return self.repeticion()
            if token["token"] == "cin":
                return self.sent_in()
            if token["token"] == "cout":
                return self.sent_out()
            if token["tipo"] == "IDENTIFICADOR":
                if self.mirar()["token"] != "=":
                    return ASTNode("Expresion").agregar(self.sent_expresion())
                return self.asignacion()
            self.error(f"Sentencia no valida cerca de '{token['token']}'")
            return None
        except RecursionError:
            self.error("Expresion demasiado profunda", "Error Sintactico Fatal")
            return None

    def asignacion(self):
        """asignacion -> id = sent_expresion"""
        nodo = ASTNode("Asignacion")
        tok = self.coincidir(tipo="IDENTIFICADOR", mensaje="Se esperaba identificador al inicio de asignacion")
        if tok:
            nodo.agregar(ASTNode("Identificador", tok["token"], "id"))
        self.coincidir("=", mensaje="Se esperaba '=' en la asignacion")
        nodo.agregar(self.sent_expresion())
        return nodo

    def sent_expresion(self):
        """sent_expresion -> expresion ; | ;"""
        nodo = ASTNode("SentExpresion")
        if self.es(";"):
            self.avanzar()
            return nodo
        nodo.agregar(self.expresion())
        self.coincidir(";", mensaje="Falta ';' al final de la expresion")
        return nodo

    def seleccion(self):
        """seleccion -> if expresion then lista_sentencias [else lista_sentencias] end"""
        nodo = ASTNode("Seleccion")
        self.coincidir("if")
        nodo.agregar(self.expresion())
        self.coincidir("then", mensaje="Se esperaba 'then' en la sentencia if")
        nodo.agregar(ASTNode("Then").agregar(self.lista_declaracion({"else", "end", "EOF"})))
        if self.es("else"):
            self.avanzar()
            nodo.agregar(ASTNode("Else").agregar(self.lista_declaracion({"end", "EOF"})))
        self.coincidir("end", mensaje="Se esperaba 'end' para cerrar el if")
        return nodo

    def iteracion(self):
        """iteracion -> while expresion lista_sentencias end"""
        nodo = ASTNode("IteracionWhile")
        self.coincidir("while")
        nodo.agregar(self.expresion())
        nodo.agregar(self.lista_declaracion({"end", "EOF"}))
        self.coincidir("end", mensaje="Se esperaba 'end' para cerrar el while")
        return nodo

    def repeticion(self):
        """repeticion -> do lista_sentencias while expresion"""
        nodo = ASTNode("RepeticionDoWhile")
        self.coincidir("do")
        nodo.agregar(self.lista_declaracion({"while", "EOF"}))
        self.coincidir("while", mensaje="Se esperaba 'while' para cerrar el do")
        nodo.agregar(self.expresion())
        if self.es(";"):
            self.avanzar()
        return nodo

    def sent_in(self):
        """sent_in -> cin >> id ;"""
        nodo = ASTNode("Entrada")
        self.coincidir("cin")
        self.coincidir(">>", mensaje="Se esperaba operador de entrada '>>'")
        tok = self.coincidir(tipo="IDENTIFICADOR", mensaje="Se esperaba identificador despues de '>>'")
        if tok:
            nodo.agregar(ASTNode("Identificador", tok["token"], "id"))
        self.coincidir(";", mensaje="Falta ';' al final de cin")
        return nodo

    def sent_out(self):
        """sent_out -> cout << salida ;"""
        nodo = ASTNode("Salida")
        self.coincidir("cout")
        self.coincidir("<<", mensaje="Se esperaba operador de salida '<<'")
        nodo.agregar(self.salida())
        self.coincidir(";", mensaje="Falta ';' al final de cout")
        return nodo

    def salida(self):
        """salida -> cadena | expresion | cadena << expresion | expresion << cadena"""
        nodo = ASTNode("ContenidoSalida")
        if self.es(tipo="CADENA"):
            tok = self.avanzar()
            nodo.agregar(ASTNode("Cadena", tok["token"], "cadena"))
            if self.es("<<"):
                self.avanzar()
                nodo.agregar(self.expresion())
            return nodo

        nodo.agregar(self.expresion())
        if self.es("<<"):
            self.avanzar()
            tok = self.coincidir(tipo="CADENA", mensaje="Despues de '<<' se esperaba una cadena")
            if tok:
                nodo.agregar(ASTNode("Cadena", tok["token"], "cadena"))
        return nodo

    def expresion(self):
        """expresion -> expresion_simple [rel_op expresion_simple]"""
        nodo = self.expresion_simple()
        if self.actual()["token"] in {"<", "<=", ">", ">=", "==", "!="}:
            op = self.avanzar()
            nuevo = ASTNode("OperacionRelacional", op["token"], "rel_op")
            nuevo.agregar(nodo)
            nuevo.agregar(self.expresion_simple())
            nodo = nuevo
        return nodo

    def expresion_simple(self):
        """expresion_simple -> termino (suma_op termino)*"""
        nodo = self.termino()
        while self.actual()["token"] in {"+", "-", "++", "--"}:
            op = self.avanzar()
            if op["token"] in {"++", "--"} and self.es_fin_expresion_simple():
                nuevo = ASTNode("OperacionIncremento", op["token"], "suma_op")
                nuevo.agregar(nodo)
                nodo = nuevo
                continue
            nuevo = ASTNode("OperacionSuma", op["token"], "suma_op")
            nuevo.agregar(nodo)
            nuevo.agregar(self.termino())
            nodo = nuevo
        return nodo

    def es_fin_expresion_simple(self):
        """Indica si ++ o -- deben interpretarse como operador postfix."""
        return self.actual()["token"] in {
            ";", ")", "then", "else", "end", "while", "}", "<<",
            "<", "<=", ">", ">=", "==", "!=", "EOF",
        }

    def termino(self):
        """termino -> factor (mult_op factor)*"""
        nodo = self.factor()
        while self.actual()["token"] in {"*", "/", "%"}:
            op = self.avanzar()
            nuevo = ASTNode("OperacionMultiplicacion", op["token"], "mult_op")
            nuevo.agregar(nodo)
            nuevo.agregar(self.factor())
            nodo = nuevo
        return nodo

    def factor(self):
        """factor -> componente (^ componente)*"""
        nodo = self.componente()
        while self.es("^"):
            op = self.avanzar()
            nuevo = ASTNode("OperacionPotencia", op["token"], "pot_op")
            nuevo.agregar(nodo)
            nuevo.agregar(self.componente())
            nodo = nuevo
        return nodo

    def componente(self):
        """componente -> (expresion) | numero | id | bool | op_logico componente"""
        token = self.actual()

        if token["token"] in {"&&", "||", "!"}:
            op = self.avanzar()
            return ASTNode("OperacionLogica", op["token"], "op_logico").agregar(self.componente())

        if self.es("("):
            self.avanzar()
            nodo = ASTNode("Grupo").agregar(self.expresion())
            self.coincidir(")", mensaje="Se esperaba ')' para cerrar la expresion")
            return nodo

        if token["tipo"] in {"NUMERO_ENTERO", "NUMERO_REAL"}:
            self.avanzar()
            return ASTNode("Numero", token["token"], token["tipo"])

        if token["tipo"] == "IDENTIFICADOR":
            self.avanzar()
            return ASTNode("Identificador", token["token"], "id")

        if token["token"] in {"true", "false"}:
            self.avanzar()
            return ASTNode("Booleano", token["token"], "bool")

        self.error(f"Se esperaba componente de expresion y se encontro '{token['token']}'")
        self.avanzar()
        return ASTNode("ErrorComponente", token["token"], "error")


def analisis_sintactico(tokens):
    parser = Parser(tokens)
    ast = parser.parse()
    return ast, parser.errores


def guardar_ast(ast, ruta):
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write(ast.to_text())


def guardar_errores_sintacticos(errores, ruta):
    with open(ruta, "w", encoding="utf-8") as archivo:
        if not errores:
            archivo.write("Sin errores sintacticos.\n")
            return
        for error in errores:
            archivo.write(
                f"{error['tipo']} - Linea {error['linea']}, Columna {error['columna']}: "
                f"{error['descripcion']}\n"
            )
