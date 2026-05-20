from .errores import ErrorCompilador


PALABRAS_RESERVADAS = {
    "main", "int", "float", "bool", "true", "false",
    "if", "then", "else", "end", "while", "do", "cin", "cout",
}

TIPOS = {"int", "float", "bool"}
SIMBOLOS = {"(", ")", "{", "}", ",", ";"}
OPERADORES_DOBLES = {
    "++": "OPERADOR_ARITMETICO",
    "--": "OPERADOR_ARITMETICO",
    "<=": "OPERADOR_RELACIONAL",
    ">=": "OPERADOR_RELACIONAL",
    "==": "OPERADOR_RELACIONAL",
    "!=": "OPERADOR_RELACIONAL",
    "&&": "OPERADOR_LOGICO",
    "||": "OPERADOR_LOGICO",
    "<<": "OPERADOR_SALIDA",
    ">>": "OPERADOR_ENTRADA",
}
OPERADORES_SIMPLES = {
    "+": "OPERADOR_ARITMETICO",
    "-": "OPERADOR_ARITMETICO",
    "*": "OPERADOR_ARITMETICO",
    "/": "OPERADOR_ARITMETICO",
    "%": "OPERADOR_ARITMETICO",
    "^": "OPERADOR_ARITMETICO",
    "<": "OPERADOR_RELACIONAL",
    ">": "OPERADOR_RELACIONAL",
    "!": "OPERADOR_LOGICO",
    "=": "ASIGNACION",
}


def crear_token(numero, lexema, tipo, linea, columna):
    """Crea el formato de token que consume el parser y muestra la interfaz."""
    return {
        "no": numero,
        "token": lexema,
        "lexema": lexema,
        "tipo": tipo,
        "linea": linea,
        "columna": columna,
    }


def analisis_lexico(codigo):
    """Analiza el codigo fuente y regresa tokens, errores y tabla de simbolos."""
    tokens = []
    errores = []
    simbolos = {}
    num_token = 1
    num_simbolo = 1
    i = 0
    linea = 1
    columna = 1
    total = len(codigo)

    def avanzar():
        """Avanza un caracter actualizando linea y columna."""
        nonlocal i, linea, columna
        ch_actual = codigo[i]
        i += 1
        if ch_actual == "\n":
            linea += 1
            columna = 1
        else:
            columna += 1
        return ch_actual

    def avanzar_hasta(indice_objetivo):
        """Consume caracteres hasta llegar al indice indicado."""
        while i < indice_objetivo:
            avanzar()

    def buscar_siguiente_significativo(inicio):
        """Busca el siguiente caracter que no sea espacio ni comentario.

        Esta funcion permite aceptar operadores dobles escritos con saltos de
        linea entre sus dos caracteres, por ejemplo: = \n = se reconoce como ==.
        """
        j = inicio
        while j < total:
            if codigo[j].isspace():
                j += 1
                continue
            if codigo.startswith("//", j):
                salto = codigo.find("\n", j + 2)
                if salto == -1:
                    return total
                j = salto + 1
                continue
            if codigo.startswith("/*", j):
                cierre = codigo.find("*/", j + 2)
                if cierre == -1:
                    return j
                j = cierre + 2
                continue
            break
        return j

    while i < total:
        ch = codigo[i]

        if ch.isspace():
            avanzar()
            continue

        if codigo.startswith("//", i):
            while i < total and codigo[i] != "\n":
                avanzar()
            continue

        if codigo.startswith("/*", i):
            inicio_linea = linea
            inicio_columna = columna
            avanzar()
            avanzar()
            cerrado = False
            while i < total:
                if codigo.startswith("*/", i):
                    avanzar()
                    avanzar()
                    cerrado = True
                    break
                avanzar()
            if not cerrado:
                errores.append(ErrorCompilador("Error Lexico", "Comentario de bloque sin cerrar", inicio_linea, inicio_columna).to_dict())
            continue

        if ch == '"':
            inicio_i = i
            inicio_linea = linea
            inicio_columna = columna
            avanzar()
            cerrada = False
            while i < total and codigo[i] != "\n":
                if codigo[i] == "\\" and i + 1 < total:
                    avanzar()
                    avanzar()
                elif codigo[i] == '"':
                    avanzar()
                    cerrada = True
                    break
                else:
                    avanzar()
            if cerrada:
                tokens.append(crear_token(num_token, codigo[inicio_i:i], "CADENA", inicio_linea, inicio_columna))
                num_token += 1
            else:
                errores.append(ErrorCompilador("Error Lexico", "Cadena sin cerrar", inicio_linea, inicio_columna).to_dict())
            continue

        if ch.isdigit():
            inicio_i = i
            inicio_linea = linea
            inicio_columna = columna
            while i < total and codigo[i].isdigit():
                avanzar()

            tipo = "NUMERO_ENTERO"
            if i < total and codigo[i] == ".":
                if i + 1 < total and codigo[i + 1].isdigit():
                    tipo = "NUMERO_REAL"
                    avanzar()
                    while i < total and codigo[i].isdigit():
                        avanzar()
                else:
                    avanzar()
                    errores.append(ErrorCompilador("Error Lexico", f"Numero mal formado: {codigo[inicio_i:i]}", inicio_linea, inicio_columna).to_dict())
                    continue

            if i < total and (codigo[i].isalpha() or codigo[i] == "_"):
                while i < total and (codigo[i].isalnum() or codigo[i] == "_"):
                    avanzar()
                errores.append(ErrorCompilador("Error Lexico", f"Identificador no valido: {codigo[inicio_i:i]}", inicio_linea, inicio_columna).to_dict())
                continue

            tokens.append(crear_token(num_token, codigo[inicio_i:i], tipo, inicio_linea, inicio_columna))
            num_token += 1
            continue

        if ch.isalpha() or ch == "_":
            inicio_i = i
            inicio_linea = linea
            inicio_columna = columna
            while i < total and (codigo[i].isalnum() or codigo[i] == "_"):
                avanzar()
            lexema = codigo[inicio_i:i]
            tipo = "PALABRA_RESERVADA" if lexema in PALABRAS_RESERVADAS else "IDENTIFICADOR"
            tokens.append(crear_token(num_token, lexema, tipo, inicio_linea, inicio_columna))
            num_token += 1
            if tipo == "IDENTIFICADOR" and lexema not in simbolos:
                simbolos[lexema] = {
                    "id": num_simbolo,
                    "nombre": lexema,
                    "tipo": "desconocido",
                    "valor": "",
                    "scope": "global",
                    "linea": inicio_linea,
                }
                num_simbolo += 1
            continue

        if ch in OPERADORES_SIMPLES or ch in {"&", "|"}:
            inicio_linea = linea
            inicio_columna = columna
            siguiente = buscar_siguiente_significativo(i + 1)
            if siguiente < total:
                doble = ch + codigo[siguiente]
                if doble in OPERADORES_DOBLES:
                    avanzar_hasta(siguiente + 1)
                    tokens.append(crear_token(num_token, doble, OPERADORES_DOBLES[doble], inicio_linea, inicio_columna))
                    num_token += 1
                    continue

            avanzar()
            if ch in {"&", "|"}:
                errores.append(ErrorCompilador("Error Lexico", f"Operador incompleto: '{ch}'", inicio_linea, inicio_columna).to_dict())
                continue
            tokens.append(crear_token(num_token, ch, OPERADORES_SIMPLES[ch], inicio_linea, inicio_columna))
            num_token += 1
            continue

        if ch in SIMBOLOS:
            tokens.append(crear_token(num_token, ch, "SIMBOLO", linea, columna))
            num_token += 1
            avanzar()
            continue

        errores.append(ErrorCompilador("Error Lexico", f"Caracter no reconocido: '{ch}'", linea, columna).to_dict())
        avanzar()

    return {
        "tokens": tokens,
        "errores": errores,
        "tabla_simbolos": list(simbolos.values()),
    }


def guardar_tokens(tokens, ruta):
    with open(ruta, "w", encoding="utf-8") as archivo:
        for token in tokens:
            archivo.write(
                f"{token['no']}\t{token['tipo']}\t{token['token']}\t"
                f"Linea {token['linea']}, Columna {token['columna']}\n"
            )
