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

Requerimientos del lenguaje (segun PDF - Fase Analisis Lexico):
===============================================================
Tokens reconocidos y su clasificacion por colores:

    Color 1 - Numeros enteros y reales
    Color 2 - Identificadores (letras y digitos, sin comenzar por digito)
    Color 3 - Comentarios de una linea (//) y multiples lineas (/* ... */)
    Color 4 - Palabras reservadas: if, else, end, do, while, switch, case, 
              int, float, main, cin, cout
    Color 5 - Operadores aritmeticos: +, -, *, /, %, ^ (potencia), 
              ++ (incremento), -- (decremento)
    Color 6 - Operadores relacionales: <, <=, >, >=, !=, ==
              Operadores logicos: && (and), || (or), ! (not)
              (Todos los operadores relacionales y logicos llevan el mismo color)
    
    Sin color especifico:
    - Simbolos: (, ), {, }, , (coma), ; (punto y coma)
    - Cadenas de caracteres: "..." (comillas dobles)
    - Caracteres: '...' (comilla sencilla)
    - Asignacion: =

Errores lexicos:
    - Deben indicar numero de linea y columna
    - Caracteres no reconocidos
    - Cadenas/caracteres sin cerrar
    - Identificadores que empiezan con digito
    - Comentarios de bloque sin cerrar
    - Numeros mal formados

Automata Finito Determinista (DFA):
===================================
Estados principales:
    q0  - Estado inicial
    q1  - Digito reconocido (posible NUMERO_ENTERO)
    q2  - Punto decimal encontrado despues de digitos
    q3  - Digitos despues del punto (NUMERO_REAL valido)
    q4  - Letra o guion bajo (inicio de identificador/palabra reservada)
    q5  - Letra, digito o guion bajo en identificador
    q6  - Operador simple reconocido
    q7  - Primer caracter de operador doble (+ - < > = ! & |)
    q8  - Operador doble completo (++ -- <= >= == != && ||)
    q9  - Comilla doble abierta (inicio de cadena)
    q10 - Caracteres dentro de cadena
    q11 - Cadena cerrada (CADENA valida)
    q12 - Comilla simple abierta (inicio de caracter)
    q13 - Caracteres dentro de caracter literal
    q14 - Caracter literal cerrado (CARACTER valido)
    q15 - Slash encontrado (posible comentario o division)
    q16 - Comentario de linea (//)
    q17 - Inicio de comentario de bloque (/*)
    q18 - Posible cierre de comentario de bloque (*)
    q19 - Comentario de bloque cerrado (*/)
    qE  - Estado de error

Transiciones principales:
    q0 -> q1  : digito
    q1 -> q1  : digito
    q1 -> q2  : punto
    q2 -> q3  : digito
    q3 -> q3  : digito
    q0 -> q4  : letra | _
    q4 -> q5  : letra | digito | _
    q5 -> q5  : letra | digito | _
    q0 -> q15 : /
    q15 -> q16 : /  (comentario de linea)
    q15 -> q17 : *  (comentario de bloque)
    q17 -> q17 : cualquier caracter excepto *
    q17 -> q18 : *
    q18 -> q19 : /  (fin de comentario)
    q18 -> q17 : cualquier caracter excepto / y *
"""

import sys
import json
import os
import re


# =============================================================================
# DEFINICION DE TOKENS DEL LENGUAJE (segun PDF)
# =============================================================================

# Palabras reservadas del lenguaje
PALABRAS_RESERVADAS = {
    "if", "else", "end", "do", "while", "switch", "case",
    "int", "float", "main", "cin", "cout"
}

# Operadores aritmeticos
OPERADORES_ARITMETICOS_DOBLES = {"++", "--"}
OPERADORES_ARITMETICOS_SIMPLES = {"+", "-", "*", "/", "%", "^"}

# Operadores relacionales
OPERADORES_RELACIONALES_DOBLES = {"<=", ">=", "!=", "=="}
OPERADORES_RELACIONALES_SIMPLES = {"<", ">"}

# Operadores logicos
OPERADORES_LOGICOS_DOBLES = {"&&", "||"}
OPERADORES_LOGICOS_SIMPLES = {"!"}

# Simbolos / Delimitadores
SIMBOLOS = {"(", ")", "{", "}", ",", ";"}

# Asignacion
ASIGNACION = {"="}

# Caracteres validos para el inicio de identificadores
INICIO_IDENTIFICADOR = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")

# Caracteres validos dentro de identificadores
DENTRO_IDENTIFICADOR = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


# =============================================================================
# ESTADOS DEL AUTOMATA FINITO DETERMINISTA (DFA)
# =============================================================================
class Estado:
    """Enumeracion de estados del automata."""
    INICIAL = 0
    NUMERO_ENTERO = 1
    NUMERO_PUNTO = 2
    NUMERO_REAL = 3
    IDENTIFICADOR = 4
    COMENTARIO_LINEA = 5
    COMENTARIO_BLOQUE = 6
    COMENTARIO_BLOQUE_ASTERISCO = 7
    CADENA = 8
    CADENA_ESCAPE = 9
    CARACTER = 10
    CARACTER_ESCAPE = 11
    SLASH = 12
    ERROR = 99


# =============================================================================
# FUNCION PRINCIPAL DE ANALISIS LEXICO
# =============================================================================
def analisis_lexico(codigo):
    """
    Realiza el analisis lexico del codigo fuente.
    
    Implementa un Automata Finito Determinista (DFA) para reconocer tokens.
    
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
    
    Args:
        codigo: String con el codigo fuente a analizar
        
    Returns:
        Diccionario con:
            - tokens: Lista de tokens reconocidos
            - errores: Lista de errores lexicos encontrados
            - tabla_simbolos: Tabla de simbolos (identificadores)
    """
    
    tokens = []
    errores = []
    simbolos_vistos = {}
    
    num_token = 1
    num_simbolo = 1
    
    lineas = codigo.split('\n')
    total_lineas = len(lineas)
    
    # Estado del automata para comentarios multilinea
    en_comentario_bloque = False
    comentario_bloque_inicio_linea = 0
    comentario_bloque_inicio_col = 0
    
    num_linea = 0
    
    while num_linea < total_lineas:
        linea = lineas[num_linea]
        num_linea += 1  # Las lineas empiezan en 1 para el usuario
        col = 0
        
        while col < len(linea):
            ch = linea[col]
            
            # =================================================================
            # ESTADO: Dentro de comentario de bloque /* ... */
            # =================================================================
            if en_comentario_bloque:
                cierre_idx = linea.find("*/", col)
                if cierre_idx != -1:
                    # El comentario se cierra en esta linea
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
                    # El comentario continua en la siguiente linea
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
            
            # =================================================================
            # ESTADO INICIAL: Espacios en blanco - ignorar
            # =================================================================
            if ch.isspace():
                col += 1
                continue
            
            # =================================================================
            # RECONOCIMIENTO DE COMENTARIOS
            # =================================================================
            
            # Comentario de una linea: //
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
                break  # El resto de la linea es comentario
            
            # Comentario de bloque: /* ... */
            if col + 1 < len(linea) and linea[col:col + 2] == '/*':
                comentario_bloque_inicio_linea = num_linea
                comentario_bloque_inicio_col = col + 1
                cierre_idx = linea.find("*/", col + 2)
                
                if cierre_idx != -1:
                    # El comentario se cierra en la misma linea
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
                    # El comentario continua en las siguientes lineas
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
            
            # =================================================================
            # RECONOCIMIENTO DE CADENAS (comillas dobles): "..."
            # =================================================================
            if ch == '"':
                inicio = col
                col += 1
                cerrada = False
                
                while col < len(linea):
                    if linea[col] == '\\' and col + 1 < len(linea):
                        # Caracter de escape: saltar el siguiente caracter
                        col += 2
                    elif linea[col] == '"':
                        col += 1
                        cerrada = True
                        break
                    else:
                        col += 1
                
                if cerrada:
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
            
            # =================================================================
            # RECONOCIMIENTO DE CARACTERES (comilla sencilla): '...'
            # =================================================================
            if ch == "'":
                inicio = col
                col += 1
                cerrada = False
                
                while col < len(linea):
                    if linea[col] == '\\' and col + 1 < len(linea):
                        # Caracter de escape
                        col += 2
                    elif linea[col] == "'":
                        col += 1
                        cerrada = True
                        break
                    else:
                        col += 1
                
                if cerrada:
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
            
            # =================================================================
            # RECONOCIMIENTO DE NUMEROS (enteros y reales)
            # Automata: q0 -digito-> q1 -digito-> q1
            #           q1 -punto-> q2 -digito-> q3 -digito-> q3
            # =================================================================
            if ch.isdigit():
                inicio = col
                tiene_punto = False
                es_valido = True
                
                # Consumir digitos de la parte entera
                while col < len(linea) and linea[col].isdigit():
                    col += 1
                
                # Verificar si hay punto decimal
                if col < len(linea) and linea[col] == '.':
                    # Verificar que despues del punto haya digitos
                    if col + 1 < len(linea) and linea[col + 1].isdigit():
                        tiene_punto = True
                        col += 1  # Consumir el punto
                        # Consumir digitos de la parte decimal
                        while col < len(linea) and linea[col].isdigit():
                            col += 1
                    # Si no hay digitos despues del punto, no lo consumimos
                    # El punto se procesara como caracter no reconocido o sera parte de otro token
                
                # Verificar que no siga una letra o guion bajo (error: 123abc)
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
            
            # =================================================================
            # RECONOCIMIENTO DE IDENTIFICADORES Y PALABRAS RESERVADAS
            # Automata: q0 -letra|_-> q4 -(letra|digito|_)*-> q5
            # =================================================================
            if ch in INICIO_IDENTIFICADOR:
                inicio = col
                while col < len(linea) and linea[col] in DENTRO_IDENTIFICADOR:
                    col += 1
                
                palabra = linea[inicio:col]
                
                if palabra in PALABRAS_RESERVADAS:
                    tipo_tok = "PALABRA_RESERVADA"
                else:
                    tipo_tok = "IDENTIFICADOR"
                    # Agregar a tabla de simbolos si es un identificador nuevo
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
            
            # =================================================================
            # RECONOCIMIENTO DE OPERADORES DOBLES (2 caracteres)
            # Se deben revisar ANTES que los operadores simples
            # =================================================================
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
            
            # =================================================================
            # RECONOCIMIENTO DE OPERADORES SIMPLES (1 caracter)
            # =================================================================
            
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
            
            # Operador logico simple: ! (not)
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
            
            # =================================================================
            # RECONOCIMIENTO DE ASIGNACION: =
            # =================================================================
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
            
            # =================================================================
            # RECONOCIMIENTO DE SIMBOLOS / DELIMITADORES: ( ) { } , ;
            # =================================================================
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
            
            # =================================================================
            # ERROR LEXICO: Caracter no reconocido
            # =================================================================
            errores.append({
                "linea": num_linea,
                "columna": col + 1,
                "tipo": "Error Lexico",
                "descripcion": f"Caracter no reconocido: '{ch}' (ASCII: {ord(ch)})"
            })
            col += 1
    
    # =========================================================================
    # VERIFICACION FINAL: Comentario de bloque sin cerrar
    # =========================================================================
    if en_comentario_bloque:
        errores.append({
            "linea": comentario_bloque_inicio_linea,
            "columna": comentario_bloque_inicio_col,
            "tipo": "Error Lexico",
            "descripcion": f"Comentario de bloque sin cerrar (iniciado en linea {comentario_bloque_inicio_linea}, columna {comentario_bloque_inicio_col}) - falta */"
        })
    
    # =========================================================================
    # RESULTADO FINAL
    # =========================================================================
    return {
        "tokens": tokens,
        "errores": errores,
        "tabla_simbolos": list(simbolos_vistos.values())
    }


# =============================================================================
# ANALISIS SINTACTICO (placeholder para futuras fases)
# =============================================================================
def analisis_sintactico(codigo):
    """
    Realiza analisis lexico + sintactico.
    
    El analisis sintactico construye un arbol de derivacion basico
    agrupando tokens en sentencias.
    """
    resultado = analisis_lexico(codigo)
    tokens = resultado["tokens"]
    
    # Filtrar comentarios para el arbol sintactico
    tokens_sin_comentarios = [t for t in tokens if t["tipo"] != "COMENTARIO"]
    
    # Generar arbol sintactico basico agrupando por sentencias
    hijos = []
    sentencia = []
    num = 1
    
    for tok in tokens_sin_comentarios:
        sentencia.append(tok)
        if tok["token"] in (";", "{", "}"):
            hijos.append({
                "nodo": f"Sentencia_{num}",
                "valor": "",
                "tipo": "sentencia",
                "hijos": [
                    {
                        "nodo": t["tipo"],
                        "valor": t["token"],
                        "tipo": t["tipo"],
                        "hijos": []
                    }
                    for t in sentencia
                ]
            })
            sentencia = []
            num += 1
    
    # Tokens restantes sin terminador
    if sentencia:
        hijos.append({
            "nodo": f"Sentencia_{num}",
            "valor": "",
            "tipo": "sentencia",
            "hijos": [
                {
                    "nodo": t["tipo"],
                    "valor": t["token"],
                    "tipo": t["tipo"],
                    "hijos": []
                }
                for t in sentencia
            ]
        })
    
    resultado["arbol"] = {
        "nodo": "Programa",
        "valor": "",
        "tipo": "",
        "hijos": hijos
    }
    
    return resultado


# =============================================================================
# ANALISIS SEMANTICO (placeholder para futuras fases)
# =============================================================================
def analisis_semantico(codigo):
    """
    Realiza analisis lexico + sintactico + semantico.
    
    El analisis semantico verifica tipos y validaciones de expresiones.
    """
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


# =============================================================================
# GENERACION DE CODIGO INTERMEDIO (placeholder para futuras fases)
# =============================================================================
def generar_intermedio(codigo):
    """
    Genera codigo intermedio (tres direcciones).
    """
    resultado = analisis_semantico(codigo)
    tokens = resultado["tokens"]
    
    # Filtrar comentarios
    tokens_util = [t for t in tokens if t["tipo"] != "COMENTARIO"]
    
    lineas_ci = []
    temp = 0
    i = 0
    
    while i < len(tokens_util):
        # Patron de asignacion: id = expr ;
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
        
        # Patron de entrada/salida: cout/cin
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


# =============================================================================
# EJECUCION (placeholder para futuras fases)
# =============================================================================
def ejecutar(codigo):
    """
    Ejecuta todas las fases incluyendo ejecucion.
    """
    resultado = generar_intermedio(codigo)
    resultado["salida_ejecucion"] = (
        "-- Resultado de ejecucion --\n"
    )
    return resultado


# =============================================================================
# PUNTO DE ENTRADA PARA EJECUCION DESDE CONSOLA
# =============================================================================
def main():
    """
    Punto de entrada principal.
    
    Uso desde linea de comandos:
        python compilador.py <fase> <archivo_entrada> [archivo_salida]
    
    Fases disponibles:
        - lexico      : Solo analisis lexico
        - sintactico  : Lexico + sintactico
        - semantico   : Lexico + sintactico + semantico
        - intermedio  : Todas las fases + codigo intermedio
        - ejecutar    : Todas las fases + ejecucion
    """
    if len(sys.argv) < 3:
        print("=" * 60)
        print("COMPILADOR - Analizador Lexico")
        print("=" * 60)
        print()
        print("Uso: python compilador.py <fase> <archivo_entrada> [archivo_salida]")
        print()
        print("Fases disponibles:")
        print("  lexico      - Analisis lexico (tokenizacion)")
        print("  sintactico  - Analisis sintactico (arbol)")
        print("  semantico   - Analisis semantico (tipos)")
        print("  intermedio  - Generacion de codigo intermedio")
        print("  ejecutar    - Ejecucion del programa")
        print()
        print("Ejemplo:")
        print("  python compilador.py lexico programa.txt resultado.json")
        print()
        sys.exit(1)
    
    fase = sys.argv[1].lower()
    archivo_entrada = sys.argv[2]
    archivo_salida = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Validar que el archivo de entrada existe
    if not os.path.exists(archivo_entrada):
        print(f"Error: No se encontro el archivo '{archivo_entrada}'")
        sys.exit(1)
    
    # Leer el codigo fuente
    with open(archivo_entrada, "r", encoding="utf-8") as f:
        codigo = f.read()
    
    # Diccionario de fases disponibles
    fases = {
        "lexico": analisis_lexico,
        "sintactico": analisis_sintactico,
        "semantico": analisis_semantico,
        "intermedio": generar_intermedio,
        "ejecutar": ejecutar,
    }
    
    # Validar la fase solicitada
    if fase not in fases:
        print(f"Error: Fase '{fase}' no reconocida.")
        print(f"Fases disponibles: {', '.join(fases.keys())}")
        sys.exit(1)
    
    # Ejecutar la fase correspondiente
    resultado = fases[fase](codigo)
    
    # Generar salida JSON
    salida_json = json.dumps(resultado, indent=2, ensure_ascii=False)
    
    # Escribir a archivo o imprimir a stdout
    if archivo_salida:
        with open(archivo_salida, "w", encoding="utf-8") as f:
            f.write(salida_json)
        print(f"Resultado guardado en: {archivo_salida}")
    else:
        print(salida_json)


if __name__ == "__main__":
    main()
