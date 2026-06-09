"""
Compilador externo invocado por el IDE.

Este archivo actua como fachada: coordina las fases, guarda salidas y regresa
JSON para la interfaz grafica. La logica real vive en scripts/compiler/.
"""

import json
import os
import sys

from compiler.analisis_lexico import analisis_lexico, guardar_tokens
from compiler.analisis_sintactico import (
    analisis_sintactico as ejecutar_parser,
    guardar_ast,
    guardar_errores_sintacticos,
)


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SALIDAS_DIR = os.path.join(BASE_DIR, "salidas")


def asegurar_salidas():
    """Crea la carpeta de salidas si no existe."""
    os.makedirs(SALIDAS_DIR, exist_ok=True)


def analizar_lexico(codigo):
    """Ejecuta solo la fase lexica y guarda tokens.txt."""
    asegurar_salidas()
    resultado = analisis_lexico(codigo)
    guardar_tokens(resultado["tokens"], os.path.join(SALIDAS_DIR, "tokens.txt"))
    return resultado


def guardar_ast_vacio():
    """Deja el archivo ast.txt vacio cuando hay errores lexicos."""
    with open(os.path.join(SALIDAS_DIR, "ast.txt"), "w", encoding="utf-8") as archivo:
        archivo.write("")


def analisis_sintactico(codigo):
    """Ejecuta lexico + parser descendente recursivo + AST."""
    resultado = analizar_lexico(codigo)

    errores_lexicos = resultado.get("errores", [])

    # Si hay errores lexicos, NO se genera ni se muestra el arbol.
    if errores_lexicos:
        guardar_ast_vacio()
        guardar_errores_sintacticos(
            [],
            os.path.join(SALIDAS_DIR, "errores_sintacticos.txt"),
        )

        resultado["arbol"] = {}
        return resultado

    # Si NO hay errores lexicos, entonces sí se ejecuta el parser.
    ast, errores_sintacticos = ejecutar_parser(resultado["tokens"])

    guardar_errores_sintacticos(
        errores_sintacticos,
        os.path.join(SALIDAS_DIR, "errores_sintacticos.txt"),
    )

    # Los errores sintacticos se agregan, pero NO bloquean el arbol.
    resultado["errores"].extend(errores_sintacticos)

    # Aunque haya errores sintacticos, el arbol se sigue guardando y mostrando.
    guardar_ast(ast, os.path.join(SALIDAS_DIR, "ast.txt"))
    resultado["arbol"] = ast.to_dict()

    return resultado


def main():
    if len(sys.argv) < 3:
        print("Uso: python compilador.py <fase> <archivo_entrada> [archivo_salida]")
        sys.exit(1)

    fase = sys.argv[1].lower()
    archivo_entrada = sys.argv[2]
    archivo_salida = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.exists(archivo_entrada):
        print(f"Error: No se encontro el archivo '{archivo_entrada}'")
        sys.exit(1)

    with open(archivo_entrada, "r", encoding="utf-8") as archivo:
        codigo = archivo.read()

    fases = {
        "lexico": analizar_lexico,
        "sintactico": analisis_sintactico,
    }

    if fase not in fases:
        print(f"Error: Fase '{fase}' no reconocida.")
        sys.exit(1)

    resultado = fases[fase](codigo)
    salida_json = json.dumps(resultado, indent=2, ensure_ascii=False)

    if archivo_salida:
        with open(archivo_salida, "w", encoding="utf-8") as archivo:
            archivo.write(salida_json)
    else:
        print(salida_json)


if __name__ == "__main__":
    main()