"""Genera evidencias reproducibles de CLI y, opcionalmente, capturas reales de Qt."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


RAIZ = Path(__file__).resolve().parents[1]
ARCHIVOS = ("pruebas/valido_1.txt", "pruebas/valido_2.txt", "pruebas/operadores_multilinea.txt",
            "pruebas/con_errores.txt", "testlexico.txt",
            "pruebas/semantico_valido.txt", "pruebas/semantico_errores.txt",
            "pruebas/maestro_condiciones_original.txt", "pruebas/maestro_condiciones_valido.txt")


def ejecutar(fase, nombre, salidas):
    args = [sys.executable, "-B", "-X", "utf8", str(RAIZ / "code/scripts/compilador.py"),
            fase, str(RAIZ / nombre), "--salidas", str(salidas)]
    proceso = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=30)
    if proceso.returncode != 0:
        raise RuntimeError(proceso.stderr or proceso.stdout)
    return json.loads(proceso.stdout)


def validar_cli(salidas):
    historico = (RAIZ / "testlexico.txt").read_bytes()
    filas = []
    for fase in ("lexico", "sintactico", "semantico"):
        for nombre in ARCHIVOS:
            r = ejecutar(fase, nombre, salidas / "pruebas" / Path(nombre).stem / fase)
            if nombre in ARCHIVOS[:3] or nombre in {"pruebas/semantico_valido.txt", "pruebas/maestro_condiciones_valido.txt"}:
                assert r["valido"], (fase, nombre, r["errores"])
            if nombre == "pruebas/maestro_condiciones_original.txt":
                assert not r["errores_lexicos"] and not r["errores_sintacticos"]
                if fase == "semantico":
                    assert len(r["errores_semanticos"]) == 8
            if fase == "semantico" and nombre == "testlexico.txt":
                assert r["estado_semantico"] == "parcial"
                assert len(r["errores_sintacticos"]) == 2
                assert len(r["errores_semanticos"]) == 8
            if fase == "semantico" and nombre == "pruebas/con_errores.txt":
                assert r["estado_semantico"] == "bloqueado"
                assert not r["arbol_semantico"]
            if fase == "semantico" and nombre == "pruebas/semantico_errores.txt":
                codigos = {e["codigo"] for e in r["errores_semanticos"]}
                assert {"SEM_NO_DECLARADO", "SEM_DUPLICADO", "SEM_TIPOS_INCOMPATIBLES",
                        "SEM_CONVERSION_INVALIDA", "SEM_OPERADOR_INVALIDO",
                        "SEM_ASIGNACION_INCOMPATIBLE", "SEM_CONDICION_NO_BOOLEANA"} <= codigos
            filas.append({
                "archivo": nombre, "fase": fase, "estado": r["estado"], "valido": r["valido"],
                "tokens": len(r["tokens"]), "lexicos": len(r["errores_lexicos"]),
                "sintacticos": len(r["errores_sintacticos"]), "semanticos": len(r["errores_semanticos"]),
                "simbolos": len(r["tabla_simbolos"]), "conversiones": len(r["conversiones"]),
            })
    assert (RAIZ / "testlexico.txt").read_bytes() == historico
    ejecutar("semantico", "testlexico.txt", salidas)
    resumen = {"ejecuciones_cli": len(filas), "fuente_principal": "testlexico.txt",
               "sha256_archivo_principal": hashlib.sha256(historico).hexdigest(),
               "archivo_principal_preservado": True, "resultados": filas}
    (salidas / "resumen_pruebas.json").write_text(json.dumps(resumen, indent=2), encoding="utf-8")
    texto = ["Fuente principal de las salidas raiz: testlexico.txt (analisis parcial)",
             "Archivo\tFase\tLexicos\tSintacticos\tSemanticos\tSimbolos\tConversiones\tEstado\tValido"]
    for fila in filas:
        texto.append("\t".join(str(fila[k]) for k in
                                 ("archivo", "fase", "lexicos", "sintacticos", "semanticos",
                                  "simbolos", "conversiones", "estado", "valido")))
    (salidas / "resumen_pruebas.txt").write_text("\n".join(texto) + "\n", encoding="utf-8")
    return resumen


def capturar_ide(salidas):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(RAIZ / "code/scripts"))
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont, QFontDatabase, QTextCursor
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QAbstractItemView
    from compilador_ide import VentanaPrincipal, STYLESHEET

    app = QApplication.instance() or QApplication([])
    fuentes = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for nombre in ("segoeui.ttf", "segoeuib.ttf", "consola.ttf", "consolab.ttf"):
        ruta = fuentes / nombre
        if ruta.is_file():
            QFontDatabase.addApplicationFont(str(ruta))
    if not QFontDatabase.families():
        raise RuntimeError("Qt no dispone de fuentes para generar capturas legibles")
    if "Segoe UI" in QFontDatabase.families():
        app.setFont(QFont("Segoe UI", 10))
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    ventana = VentanaPrincipal()
    evidencias = salidas / "evidencias"
    evidencias.mkdir(parents=True, exist_ok=True)
    ventana.showNormal()
    ventana.resize(1600, 1000)
    ventana.resizeDocks([ventana.dock_derecho], [1080], Qt.Orientation.Horizontal)
    ventana.resizeDocks([ventana.dock_inferior], [300], Qt.Orientation.Vertical)
    capturas = []

    def compilar(nombre):
        ventana.directorio_salidas = str(salidas / "pruebas" / Path(nombre).stem / "semantico")
        ventana.editor.setPlainText((RAIZ / nombre).read_text(encoding="utf-8"))
        ventana.ruta_archivo = str(RAIZ / nombre)
        ventana._actualizar_titulo()
        ventana.act_ejecutar.trigger()
        limite = time.monotonic() + 15
        while ventana.proceso_compilador is not None and time.monotonic() < limite:
            QTest.qWait(10)
        assert ventana.proceso_compilador is None and ventana.ultimo_resultado is not None

    def guardar(nombre, fuente):
        QTest.qWait(50)
        ruta = evidencias / nombre
        assert ventana.grab().save(str(ruta))
        capturas.append({"archivo": nombre, "fuente": fuente,
                         "ancho": ventana.width(), "alto": ventana.height(),
                         "modo": "Qt offscreen; widgets reales y compilador externo"})

    def enfocar(arbol, item):
        arbol.setCurrentItem(item)
        arbol.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
        ruta = item.data(0, Qt.ItemDataRole.UserRole)
        anotado = ventana._items_arbol[ventana.arbol_semantico][ruta]
        linea = int(anotado.text(3).split(":")[0])
        ventana.editor.setTextCursor(QTextCursor(ventana.editor.document().findBlockByNumber(linea - 1)))
        ventana.editor.centerCursor()

    try:
        fuente = "pruebas/semantico_valido.txt"
        compilar(fuente)
        ventana.tabs_derecho.setCurrentWidget(ventana.arbol_semantico)
        ventana.tabs_inferior.setCurrentWidget(ventana.texto_resultados)
        guardar("ide_ast_semantico_valido.png", fuente)
        ventana.tabs_derecho.setCurrentWidget(ventana.comparacion_ast)
        guardar("ide_comparacion_ast.png", fuente)
        fuente = "testlexico.txt"
        compilar(fuente)
        ventana.tabs_derecho.setCurrentWidget(ventana.arbol_semantico)
        ventana.tabs_inferior.setCurrentWidget(ventana.texto_resultados)
        quince = next(item for item in ventana._items_arbol[ventana.arbol_semantico].values()
                      if item.text(0) == "Asignacion" and item.text(2) == "15")
        enfocar(ventana.arbol_semantico, quince)
        guardar("ide_valores_propagados.png", fuente)
        ventana.tabs_derecho.setCurrentWidget(ventana.comparacion_ast)
        condicion = next(item for item in ventana._items_arbol[ventana.arbol_comparacion_original].values()
                         if item.text(0) == "Grupo" and item.text(1) == "desconocido")
        enfocar(ventana.arbol_comparacion_original, condicion)
        ruta = condicion.data(0, Qt.ItemDataRole.UserRole)
        ventana.arbol_comparacion_anotado.scrollToItem(
            ventana._items_arbol[ventana.arbol_comparacion_anotado][ruta],
            QAbstractItemView.ScrollHint.PositionAtCenter)
        guardar("ide_booleano_historico.png", fuente)
        ventana.tabs_derecho.setCurrentWidget(ventana.tabla_simbolos)
        ventana.tabs_inferior.setCurrentWidget(ventana.tabla_err_semantico)
        guardar("ide_tabla_historico.png", fuente)
        for fuente, sufijo in [("pruebas/maestro_condiciones_original.txt", "desconocido"),
                               ("pruebas/maestro_condiciones_valido.txt", "true_false")]:
            compilar(fuente)
            ventana.tabs_derecho.setCurrentWidget(ventana.arbol_semantico)
            ventana.tabs_inferior.setCurrentWidget(ventana.texto_resultados)
            condicion = next(i for i in ventana._items_arbol[ventana.arbol_semantico].values()
                             if i.text(0) == "Seleccion")
            enfocar(ventana.arbol_semantico, condicion)
            guardar("ide_maestro_" + sufijo + ".png", fuente)
            if sufijo == "true_false":
                bucle = next(i for i in ventana._items_arbol[ventana.arbol_semantico].values()
                             if i.text(0).startswith("OperacionLogica | valor: &&"))
                enfocar(ventana.arbol_semantico, bucle)
                guardar("ide_maestro_bucle_false.png", fuente)
        fuente = "pruebas/semantico_errores.txt"
        compilar(fuente)
        ventana.tabs_derecho.setCurrentWidget(ventana.arbol_semantico)
        ventana.tabs_inferior.setCurrentWidget(ventana.tabla_err_semantico)
        guardar("ide_errores_semanticos.png", fuente)
        ventana.resize(1280, 800)
        ventana.resizeDocks([ventana.dock_derecho], [780], Qt.Orientation.Horizontal)
        guardar("ide_compacto.png", fuente)
        (evidencias / "capturas.json").write_text(json.dumps(capturas, indent=2), encoding="utf-8")
    finally:
        ventana.archivo_modificado = False
        ventana.close()
        app.processEvents()
    return capturas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salidas", type=Path, default=RAIZ / "salidas")
    parser.add_argument("--capturas", action="store_true")
    args = parser.parse_args()
    args.salidas.mkdir(parents=True, exist_ok=True)
    resumen = validar_cli(args.salidas)
    capturas = capturar_ide(args.salidas) if args.capturas else []
    print(f"{resumen['ejecuciones_cli']} ejecuciones CLI verificadas; {len(capturas)} capturas generadas")


if __name__ == "__main__":
    main()
