"""
Compilador Externo (Modulo independiente)
==========================================
Este archivo es el compilador que el IDE invoca como proceso externo.
Puede ejecutarse desde linea de comandos de forma autonoma:

    python compilador.py <fase> <archivo_entrada> <archivo_salida>

Fases disponibles:
    - lexico       : Analisis lexico (tokenizacion)
    - sintactico   : Analisis sintactico (arbol)
    - semantico    : Analisis semantico (tipos)
    - intermedio   : Generacion de codigo intermedio
    - ejecutar     : Ejecucion del programa

La comunicacion con el IDE es mediante archivos:
    - Lee el codigo fuente desde <archivo_entrada>
    - Escribe los resultados en formato JSON a <archivo_salida>

Requerimientos del lenguaje (PDF):
    - Palabras reservadas: if, else, end, do, while, switch, case, int, float, main, cin, cout
    - Operadores aritmeticos: +, -, *, /, %, ^, ++, --
    - Operadores relacionales: <, <=, >, >=, !=, ==
    - Operadores logicos: && (and), || (or), ! (not)
    - Simbolos: ( ) { } , ; "" ''
    - Asignacion: =
    - Numeros enteros y reales
    - Identificadores (letras y digitos, no empiezan con digito)
    - Comentarios de una linea (//) y multiples lineas (/* ... */)
    - Errores lexicos con numero de linea y columna
"""

import sys
import json
import os


# =============================================================================
# Palabras reservadas del lenguaje (segun PDF)
# =============================================================================
PALABRAS_RESERVADAS = {
    "if", "else", "end", "do", "while", "switch", "case",
    "int", "float", "main", "cin", "cout"
}

# =============================================================================
# Operadores aritmeticos (dobles primero para prioridad)
# =============================================================================
OPERADORES_ARITMETICOS_DOBLES = {"++", "--"}
OPERADORES_ARITMETICOS_SIMPLES = {"+", "-", "*", "/", "%", "^"}

# =============================================================================
# Operadores relacionales
# =============================================================================
OPERADORES_RELACIONALES_DOBLES = {"<=", ">=", "!=", "=="}
OPERADORES_RELACIONALES_SIMPLES = {"<", ">"}

# =============================================================================
# Operadores logicos
# =============================================================================
OPERADORES_LOGICOS_DOBLES = {"&&", "||"}
OPERADORES_LOGICOS_SIMPLES = {"!"}

# =============================================================================
# Simbolos / Delimitadores
# =============================================================================
SIMBOLOS = {"(", ")", "{", "}", ",", ";"}

# =============================================================================
# Asignacion
# =============================================================================
ASIGNACION = {"="}


def analisis_lexico(codigo):
    """Realiza el analisis lexico del codigo fuente.

    Clasificacion de tokens segun el PDF:
        - NUMERO_ENTERO / NUMERO_REAL          (Color 1)
        - IDENTIFICADOR                         (Color 2)
        - COMENTARIO                            (Color 3)
        - PALABRA_RESERVADA                     (Color 4)
        - OPERADOR_ARITMETICO                   (Color 5)
        - OPERADOR_RELACIONAL / OPERADOR_LOGICO (Color 6)
        - SIMBOLO                               (sin color especifico)
        - ASIGNACION                            (sin color especifico)
        - CADENA / CARACTER                     (cadenas y caracteres)

    Retorna un diccionario con tokens, errores y tabla de simbolos.
    """

    tokens = []
    errores = []
    tabla_simbolos = []

    num_token = 1
    num_simbolo = 1
    simbolos_vistos = {}

    lineas = codigo.split('\n')
    total_lineas = len(lineas)

    en_comentario_bloque = False  # Estado para comentarios multilinea
    num_linea = 0

    while num_linea < total_lineas:
        linea = lineas[num_linea]
        num_linea += 1  # Lineas empiezan en 1
        col = 0

        while col < len(linea):
            ch = linea[col]

            # =============================================================
            # Dentro de un comentario de bloque /* ... */
            # =============================================================
            if en_comentario_bloque:
                cierre_idx = linea.find("*/", col)
                if cierre_idx != -1:
                    texto_com = linea[col:cierre_idx + 2]
                    tokens.append({
                        "no": num_token,
                        "token": texto_com,
                        "tipo": "COMENTARIO",
                        "linea": num_linea,
                        "columna": col + 1
                    })
                    num_token += 1
                    col = cierre_idx + 2
                    en_comentario_bloque = False
                else:
                    # Toda la linea restante es comentario
                    if col < len(linea):
                        texto_com = linea[col:]
                        tokens.append({
                            "no": num_token,
                            "token": texto_com,
                            "tipo": "COMENTARIO",
                            "linea": num_linea,
                            "columna": col + 1
                        })
                        num_token += 1
                    break  # Pasar a la siguiente linea
                continue

            # =============================================================
            # Espacios en blanco - ignorar
            # =============================================================
            if ch.isspace():
                col += 1
                continue

            # =============================================================
            # Comentarios de una linea: //
            # =============================================================
            if col + 1 < len(linea) and linea[col:col + 2] == '//':
                texto_com = linea[col:]
                tokens.append({
                    "no": num_token,
                    "token": texto_com,
                    "tipo": "COMENTARIO",
                    "linea": num_linea,
                    "columna": col + 1
                })
                num_token += 1
                break  # Fin de la linea

            # =============================================================
            # Comentarios de multiples lineas: /* ... */
            # =============================================================
            if col + 1 < len(linea) and linea[col:col + 2] == '/*':
                inicio_col = col
                cierre_idx = linea.find("*/", col + 2)
                if cierre_idx != -1:
                    # Comentario se cierra en la misma linea
                    texto_com = linea[col:cierre_idx + 2]
                    tokens.append({
                        "no": num_token,
                        "token": texto_com,
                        "tipo": "COMENTARIO",
                        "linea": num_linea,
                        "columna": col + 1
                    })
                    num_token += 1
                    col = cierre_idx + 2
                else:
                    # Comentario continua en siguientes lineas
                    texto_com = linea[col:]
                    tokens.append({
                        "no": num_token,
                        "token": texto_com,
                        "tipo": "COMENTARIO",
                        "linea": num_linea,
                        "columna": col + 1
                    })
                    num_token += 1
                    en_comentario_bloque = True
                    break  # Pasar a la siguiente linea
                continue

            # =============================================================
            # Cadenas con comillas dobles: "..."
            # =============================================================
            if ch == '"':
                inicio = col
                col += 1
                while col < len(linea) and linea[col] != '"':
                    if linea[col] == '\\' and col + 1 < len(linea):
                        col += 1  # Saltar caracter escapado
                    col += 1
                if col < len(linea):
                    col += 1  # Cerrar comilla
                    tokens.append({
                        "no": num_token,
                        "token": linea[inicio:col],
                        "tipo": "CADENA",
                        "linea": num_linea,
                        "columna": inicio + 1
                    })
                    num_token += 1
                else:
                    errores.append({
                        "linea": num_linea,
                        "columna": inicio + 1,
                        "tipo": "Error Lexico",
                        "descripcion": f"Cadena sin cerrar: {linea[inicio:]}"
                    })
                continue

            # =============================================================
            # Caracteres con comilla sencilla: '...'
            # =============================================================
            if ch == "'":
                inicio = col
                col += 1
                while col < len(linea) and linea[col] != "'":
                    if linea[col] == '\\' and col + 1 < len(linea):
                        col += 1  # Saltar caracter escapado
                    col += 1
                if col < len(linea):
                    col += 1  # Cerrar comilla
                    tokens.append({
                        "no": num_token,
                        "token": linea[inicio:col],
                        "tipo": "CARACTER",
                        "linea": num_linea,
                        "columna": inicio + 1
                    })
                    num_token += 1
                else:
                    errores.append({
                        "linea": num_linea,
                        "columna": inicio + 1,
                        "tipo": "Error Lexico",
                        "descripcion": f"Caracter sin cerrar: {linea[inicio:]}"
                    })
                continue

            # =============================================================
            # Numeros enteros y reales
            # =============================================================
            if ch.isdigit():
                inicio = col
                tiene_punto = False
                while col < len(linea) and (linea[col].isdigit() or linea[col] == '.'):
                    if linea[col] == '.':
                        if tiene_punto:
                            break  # Segundo punto: cortar
                        tiene_punto = True
                    col += 1
                # Verificar que no siga una letra (ej: 123abc -> error)
                if col < len(linea) and (linea[col].isalpha() or linea[col] == '_'):
                    inicio_err = col
                    while col < len(linea) and (linea[col].isalnum() or linea[col] == '_'):
                        col += 1
                    errores.append({
                        "linea": num_linea,
                        "columna": inicio + 1,
                        "tipo": "Error Lexico",
                        "descripcion": f"Identificador no valido (empieza con digito): {linea[inicio:col]}"
                    })
                else:
                    tipo_num = "NUMERO_REAL" if tiene_punto else "NUMERO_ENTERO"
                    tokens.append({
                        "no": num_token,
                        "token": linea[inicio:col],
                        "tipo": tipo_num,
                        "linea": num_linea,
                        "columna": inicio + 1
                    })
                    num_token += 1
                continue

            # =============================================================
            # Identificadores y palabras reservadas
            # (letras y digitos, no comienzan con digito)
            # =============================================================
            if ch.isalpha() or ch == '_':
                inicio = col
                while col < len(linea) and (linea[col].isalnum() or linea[col] == '_'):
                    col += 1
                palabra = linea[inicio:col]
                if palabra in PALABRAS_RESERVADAS:
                    tipo_tok = "PALABRA_RESERVADA"
                else:
                    tipo_tok = "IDENTIFICADOR"
                    # Agregar a tabla de simbolos si es nuevo
                    if palabra not in simbolos_vistos:
                        simbolos_vistos[palabra] = {
                            "id": num_simbolo,
                            "nombre": palabra,
                            "tipo": "desconocido",
                            "valor": "",
                            "scope": "global",
                            "linea": num_linea
                        }
                        num_simbolo += 1
                tokens.append({
                    "no": num_token,
                    "token": palabra,
                    "tipo": tipo_tok,
                    "linea": num_linea,
                    "columna": inicio + 1
                })
                num_token += 1
                continue

            # =============================================================
            # Operadores dobles (2 caracteres) - revisar primero
            # =============================================================
            if col + 1 < len(linea):
                doble = linea[col:col + 2]

                # Operadores aritmeticos dobles: ++ --
                if doble in OPERADORES_ARITMETICOS_DOBLES:
                    tokens.append({
                        "no": num_token,
                        "token": doble,
                        "tipo": "OPERADOR_ARITMETICO",
                        "linea": num_linea,
                        "columna": col + 1
                    })
                    num_token += 1
                    col += 2
                    continue

                # Operadores relacionales dobles: <= >= != ==
                if doble in OPERADORES_RELACIONALES_DOBLES:
                    tokens.append({
                        "no": num_token,
                        "token": doble,
                        "tipo": "OPERADOR_RELACIONAL",
                        "linea": num_linea,
                        "columna": col + 1
                    })
                    num_token += 1
                    col += 2
                    continue

                # Operadores logicos dobles: && ||
                if doble in OPERADORES_LOGICOS_DOBLES:
                    tokens.append({
                        "no": num_token,
                        "token": doble,
                        "tipo": "OPERADOR_LOGICO",
                        "linea": num_linea,
                        "columna": col + 1
                    })
                    num_token += 1
                    col += 2
                    continue

            # =============================================================
            # Operadores simples de un caracter
            # =============================================================

            # Operadores aritmeticos simples: + - * / % ^
            if ch in OPERADORES_ARITMETICOS_SIMPLES:
                tokens.append({
                    "no": num_token,
                    "token": ch,
                    "tipo": "OPERADOR_ARITMETICO",
                    "linea": num_linea,
                    "columna": col + 1
                })
                num_token += 1
                col += 1
                continue

            # Operadores relacionales simples: < >
            if ch in OPERADORES_RELACIONALES_SIMPLES:
                tokens.append({
                    "no": num_token,
                    "token": ch,
                    "tipo": "OPERADOR_RELACIONAL",
                    "linea": num_linea,
                    "columna": col + 1
                })
                num_token += 1
                col += 1
                continue

            # Operador logico simple: !
            if ch in OPERADORES_LOGICOS_SIMPLES:
                tokens.append({
                    "no": num_token,
                    "token": ch,
                    "tipo": "OPERADOR_LOGICO",
                    "linea": num_linea,
                    "columna": col + 1
                })
                num_token += 1
                col += 1
                continue

            # Asignacion: =
            if ch == '=':
                tokens.append({
                    "no": num_token,
                    "token": ch,
                    "tipo": "ASIGNACION",
                    "linea": num_linea,
                    "columna": col + 1
                })
                num_token += 1
                col += 1
                continue

            # Simbolos / Delimitadores: ( ) { } , ;
            if ch in SIMBOLOS:
                tokens.append({
                    "no": num_token,
                    "token": ch,
                    "tipo": "SIMBOLO",
                    "linea": num_linea,
                    "columna": col + 1
                })
                num_token += 1
                col += 1
                continue

            # =============================================================
            # Caracter no reconocido -> Error lexico
            # =============================================================
            errores.append({
                "linea": num_linea,
                "columna": col + 1,
                "tipo": "Error Lexico",
                "descripcion": f"Caracter no reconocido: '{ch}'"
            })
            col += 1

    # Si el archivo termina dentro de un comentario de bloque sin cerrar
    if en_comentario_bloque:
        errores.append({
            "linea": total_lineas,
            "columna": 1,
            "tipo": "Error Lexico",
            "descripcion": "Comentario de bloque sin cerrar (falta */)"
        })

    return {
        "tokens": tokens,
        "errores": errores,
        "tabla_simbolos": list(simbolos_vistos.values())
    }


def analisis_sintactico(codigo):
    """Realiza analisis lexico + sintactico."""
    resultado = analisis_lexico(codigo)
    tokens = resultado["tokens"]

    # Filtrar comentarios para el arbol sintactico
    tokens_sin_comentarios = [t for t in tokens if t["tipo"] != "COMENTARIO"]

    # Generar arbol sintactico basico
    hijos = []
    sentencia = []
    num = 1

    for tok in tokens_sin_comentarios:
        sentencia.append(tok)
        if tok["token"] in (";", "{", "}"):
            hijos.append({
                "nodo": f"Sentencia_{num}",
                "valor": "", "tipo": "sentencia",
                "hijos": [
                    {"nodo": t["tipo"], "valor": t["token"],
                     "tipo": t["tipo"], "hijos": []}
                    for t in sentencia
                ]
            })
            sentencia = []
            num += 1

    if sentencia:
        hijos.append({
            "nodo": f"Sentencia_{num}",
            "valor": "", "tipo": "sentencia",
            "hijos": [
                {"nodo": t["tipo"], "valor": t["token"],
                 "tipo": t["tipo"], "hijos": []}
                for t in sentencia
            ]
        })

    resultado["arbol"] = {
        "nodo": "Programa", "valor": "", "tipo": "", "hijos": hijos
    }
    return resultado


def analisis_semantico(codigo):
    """Realiza analisis lexico + sintactico + semantico."""
    resultado = analisis_sintactico(codigo)

    validaciones = []
    for tok in resultado["tokens"]:
        if tok["tipo"] == "IDENTIFICADOR":
            validaciones.append({
                "no": len(validaciones) + 1,
                "expresion": tok["token"],
                "tipo_esperado": "variable",
                "tipo_encontrado": "identificador",
                "estado": "OK"
            })

    resultado["semantico"] = validaciones
    return resultado


def generar_intermedio(codigo):
    """Genera codigo intermedio (tres direcciones)."""
    resultado = analisis_semantico(codigo)
    tokens = resultado["tokens"]

    # Filtrar comentarios
    tokens_util = [t for t in tokens if t["tipo"] != "COMENTARIO"]

    lineas_ci = []
    temp = 0
    i = 0

    while i < len(tokens_util):
        if (i + 2 < len(tokens_util)
                and tokens_util[i]["tipo"] == "IDENTIFICADOR"
                and tokens_util[i + 1]["token"] == "="):
            var = tokens_util[i]["token"]
            j = i + 2
            expr = []
            while j < len(tokens_util) and tokens_util[j]["token"] != ";":
                expr.append(tokens_util[j]["token"])
                j += 1
            if len(expr) >= 3:
                t = f"t{temp}"
                temp += 1
                lineas_ci.append(f"  {t} = {' '.join(expr)}")
                lineas_ci.append(f"  {var} = {t}")
            elif expr:
                lineas_ci.append(f"  {var} = {' '.join(expr)}")
            i = j + 1
            continue

        if (tokens_util[i]["token"] in ("cout", "cin")
                and i + 1 < len(tokens_util)):
            j = i + 1
            args = []
            while j < len(tokens_util) and tokens_util[j]["token"] != ";":
                if tokens_util[j]["token"] not in ("<<", ">>", ","):
                    args.append(tokens_util[j]["token"])
                j += 1
            for a in args:
                lineas_ci.append(f"  param {a}")
            lineas_ci.append(f"  call {tokens_util[i]['token']}, {len(args)}")
            i = j + 1
            continue

        i += 1

    if not lineas_ci:
        lineas_ci.append("  ; (Sin codigo intermedio generado)")

    resultado["codigo_intermedio"] = "\n".join(lineas_ci)
    return resultado


def ejecutar(codigo):
    """Ejecuta todas las fases incluyendo ejecucion."""
    resultado = generar_intermedio(codigo)
    resultado["salida_ejecucion"] = (
        "-- Resultado de ejecucion --\n"
        "(Implemente su logica de ejecucion aqui)"
    )
    return resultado


# =============================================================================
# Punto de entrada para ejecucion desde consola
# =============================================================================
def main():
    if len(sys.argv) < 3:
        print("Uso: python compilador.py <fase> <archivo_entrada> [archivo_salida]")
        print("Fases: lexico, sintactico, semantico, intermedio, ejecutar")
        sys.exit(1)

    fase = sys.argv[1]
    archivo_entrada = sys.argv[2]
    archivo_salida = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.exists(archivo_entrada):
        print(f"Error: No se encontro el archivo '{archivo_entrada}'")
        sys.exit(1)

    with open(archivo_entrada, "r", encoding="utf-8") as f:
        codigo = f.read()

    fases = {
        "lexico": analisis_lexico,
        "sintactico": analisis_sintactico,
        "semantico": analisis_semantico,
        "intermedio": generar_intermedio,
        "ejecutar": ejecutar,
    }

    if fase not in fases:
        print(f"Error: Fase '{fase}' no reconocida.")
        print(f"Fases disponibles: {', '.join(fases.keys())}")
        sys.exit(1)

    resultado = fases[fase](codigo)

    salida_json = json.dumps(resultado, indent=2, ensure_ascii=False)

    if archivo_salida:
        with open(archivo_salida, "w", encoding="utf-8") as f:
            f.write(salida_json)
    else:
        print(salida_json)


if __name__ == "__main__":
    main()
