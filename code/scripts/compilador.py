"""Fachada CLI: coordina las tres fases, produce JSON y guarda evidencias."""

import argparse
import hashlib
import json
import os
import sys

from compiler.analisis_lexico import analisis_lexico, guardar_tokens
from compiler.analisis_sintactico import analisis_sintactico as ejecutar_parser
from compiler.analisis_semantico import analisis_semantico as ejecutar_semantico


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SALIDAS_DIR = os.path.join(BASE_DIR, "salidas")


def _resultado_vacio(fase):
    return {
        "fase": fase, "tokens": [], "errores": [],
        "errores_lexicos": [], "errores_sintacticos": [],
        "errores_semanticos": [], "errores_ejecucion": [],
        "arbol": {}, "arbol_semantico": {},
        "tabla_simbolos": [], "tabla_simbolos_lexica": [],
        "conversiones": [], "traza_semantica": [],
        "estado": "completo", "estado_semantico": "no_ejecutado",
        "motivo_semantico": "La fase solicitada no incluye analisis semantico",
        "valido": False,
    }


def ast_parcial_seguro(arbol, errores):
    """Solo permite recuperacion de expresiones; nunca fallos de bloques/declaraciones."""
    if arbol is None or arbol.nodo != "Programa":
        return False
    if not errores:
        return True
    permitidos = ("Se esperaba componente de expresion y se encontro",
                  "Se esperaba ')' para cerrar la expresion")
    if any(e["tipo"] != "Error Sintactico" or
           not e["descripcion"].startswith(permitidos) for e in errores):
        return False
    # Un ErrorComponente retiene el hueco recuperado y propaga tipo error.
    pendientes = [arbol]
    while pendientes:
        nodo = pendientes.pop()
        if nodo.nodo == "ErrorComponente":
            return True
        pendientes.extend(nodo.hijos)
    return False


def _texto_arbol(arbol, anotado=False):
    if not arbol:
        return ""
    lineas = []
    pendientes = [(arbol, 0)]
    while pendientes:
        nodo, nivel = pendientes.pop()
        texto = "  " * nivel + nodo["nodo"]
        if nodo.get("valor"):
            texto += ": " + nodo["valor"]
        if nodo.get("tipo"):
            texto += " [" + nodo["tipo"] + "]"
        if anotado:
            texto += f" (linea {nodo.get('linea', 0)}, columna {nodo.get('columna', 0)}) "
            texto += json.dumps(nodo.get("atributos", {}), ensure_ascii=False, allow_nan=False)
        lineas.append(texto)
        pendientes.extend((h, nivel + 1) for h in reversed(nodo.get("hijos", [])))
    return "\n".join(lineas) + "\n"


def _texto_errores(errores, fase, nota=""):
    if nota:
        return nota + "\n"
    if not errores:
        return f"Sin errores {fase}.\n"
    return "\n".join(
        f"{e['tipo']} [{e.get('codigo', '')}] - Linea {e['linea']}, "
        f"Columna {e['columna']}: {e['descripcion']}" for e in errores
    ) + "\n"


def guardar_salidas(resultado, directorio=None):
    directorio = directorio or SALIDAS_DIR
    os.makedirs(directorio, exist_ok=True)
    guardar_tokens(resultado["tokens"], os.path.join(directorio, "tokens.txt"))
    nota_semantica = ""
    if resultado["estado_semantico"] in {"no_ejecutado", "bloqueado"}:
        nota_semantica = resultado["motivo_semantico"]
    nota_sintactica = ""
    if resultado["fase"] == "lexico" or resultado["errores_lexicos"] or resultado["errores_ejecucion"]:
        nota_sintactica = "Analisis sintactico no ejecutado"
    titulo_tabla = ("Tabla semantica" if resultado["fase"] == "semantico"
                    else "Inventario lexico de identificadores")
    encabezado = "ID\tNombre\tTipo\tLineas\tColumna\tAmbito\tDesplazamiento\tDeclarado\tInicializado"
    filas = [titulo_tabla, encabezado]
    for s in resultado["tabla_simbolos"]:
        valores = [s["id"], s["nombre"], s["tipo"],
                   ",".join(map(str, s.get("lineas", [s.get("linea", 0)]))),
                   s.get("columna", ""), s.get("ambito", s.get("scope", "")),
                   s.get("desplazamiento", ""), s.get("declarado", ""),
                   s.get("inicializado", "")]
        filas.append("\t".join(map(str, valores)))
    if nota_semantica and resultado["fase"] == "semantico":
        filas.append(nota_semantica)
    archivos = {
        "ast.txt": _texto_arbol(resultado["arbol"]),
        "ast_semantico.txt": _texto_arbol(resultado["arbol_semantico"], True) or (nota_semantica + "\n"),
        "tabla_simbolos.txt": "\n".join(filas) + "\n",
        "errores_lexicos.txt": _texto_errores(resultado["errores_lexicos"], "lexicos"),
        "errores_sintacticos.txt": _texto_errores(resultado["errores_sintacticos"], "sintacticos", nota_sintactica),
        "errores_semanticos.txt": _texto_errores(resultado["errores_semanticos"], "semanticos", nota_semantica),
        "errores_ejecucion.txt": _texto_errores(resultado["errores_ejecucion"], "de ejecucion"),
        "traza_semantica.txt": "\n".join(json.dumps(e, ensure_ascii=False, allow_nan=False)
                                             for e in resultado["traza_semantica"]) or nota_semantica,
        "conversiones.txt": json.dumps(resultado["conversiones"], indent=2, ensure_ascii=False, allow_nan=False),
        "resultado.json": json.dumps(resultado, indent=2, ensure_ascii=False, allow_nan=False),
    }
    for nombre, contenido in archivos.items():
        with open(os.path.join(directorio, nombre), "w", encoding="utf-8") as archivo:
            archivo.write(contenido)


def analizar(codigo, fase="semantico", directorio_salidas=None):
    if fase not in {"lexico", "sintactico", "semantico"}:
        raise ValueError(f"Fase no reconocida: {fase}")
    resultado = _resultado_vacio(fase)
    resultado["sha256_fuente"] = hashlib.sha256(codigo.encode("utf-8")).hexdigest()
    lexico = analisis_lexico(codigo)
    resultado["tokens"] = lexico["tokens"]
    resultado["errores_lexicos"] = list(lexico["errores"])
    resultado["tabla_simbolos_lexica"] = lexico["tabla_simbolos"]
    if fase != "semantico":
        resultado["tabla_simbolos"] = lexico["tabla_simbolos"]
    arbol = None
    if resultado["errores_lexicos"]:
        resultado["estado"] = "bloqueado"
        resultado["estado_semantico"] = "bloqueado" if fase == "semantico" else "no_ejecutado"
        resultado["motivo_semantico"] = "Analisis semantico bloqueado por errores lexicos"
    elif fase != "lexico":
        arbol, errores = ejecutar_parser(resultado["tokens"])
        resultado["errores_sintacticos"] = errores
        resultado["arbol"] = arbol.to_dict() if arbol else {}
        if errores:
            resultado["estado"] = "parcial"
        if fase == "semantico":
            if ast_parcial_seguro(arbol, errores):
                semantico = ejecutar_semantico(arbol)
                for clave in ("arbol_semantico", "tabla_simbolos", "errores_semanticos",
                              "conversiones", "traza_semantica"):
                    resultado[clave] = semantico[clave]
                resultado["estado_semantico"] = semantico["estado"]
                resultado["estado"] = semantico["estado"]
                resultado["motivo_semantico"] = (
                    "Recorrido parcial: errores limitados a expresiones; resultados provisionales"
                    if errores else "Analisis semantico completado")
            else:
                resultado["estado_semantico"] = "bloqueado"
                resultado["estado"] = "bloqueado"
                resultado["motivo_semantico"] = "Analisis semantico bloqueado: estructura sintactica insegura"
    resultado["errores"] = (resultado["errores_lexicos"] + resultado["errores_sintacticos"] +
                            resultado["errores_semanticos"])
    resultado["valido"] = not resultado["errores"] and resultado["estado"] == "completo"
    guardar_salidas(resultado, directorio_salidas)
    return resultado


def analizar_lexico(codigo):
    return analizar(codigo, "lexico")


def analisis_sintactico(codigo):
    return analizar(codigo, "sintactico")


def analisis_semantico(codigo):
    return analizar(codigo, "semantico")


def main():
    argumentos = argparse.ArgumentParser(description="Compilador: fases lexica, sintactica y semantica")
    argumentos.add_argument("fase", choices=("lexico", "sintactico", "semantico"))
    argumentos.add_argument("archivo_entrada")
    argumentos.add_argument("archivo_salida", nargs="?")
    argumentos.add_argument("--salidas", default=SALIDAS_DIR, help="Directorio de evidencias")
    args = argumentos.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        with open(args.archivo_entrada, "r", encoding="utf-8-sig") as archivo:
            resultado = analizar(archivo.read(), args.fase, args.salidas)
        salida = json.dumps(resultado, indent=2, ensure_ascii=False, allow_nan=False)
        if args.archivo_salida:
            with open(args.archivo_salida, "w", encoding="utf-8") as archivo:
                archivo.write(salida)
        else:
            print(salida)
        return 0
    except (OSError, UnicodeError, RecursionError) as error:
        resultado = _resultado_vacio(args.fase)
        resultado["estado"] = "bloqueado"
        resultado["estado_semantico"] = "bloqueado"
        resultado["motivo_semantico"] = "Analisis semantico bloqueado por error de ejecucion"
        resultado["errores_ejecucion"] = [{"tipo": "Error de ejecucion", "linea": 0,
                                             "columna": 0, "descripcion": str(error)}]
        resultado["errores"] = resultado["errores_ejecucion"]
        try:
            guardar_salidas(resultado, args.salidas)
        except OSError:
            pass
        print(json.dumps(resultado, ensure_ascii=False), file=sys.stdout)
        return 1


if __name__ == "__main__":
    sys.exit(main())
