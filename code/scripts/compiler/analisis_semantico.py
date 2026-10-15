"""Tipos, atributos y simbolos calculados sobre una copia del AST de Fase 2.

El lenguaje conserva un unico ambito global en main. Las declaraciones son
visibles desde su aparicion, incluso dentro de estructuras de control. Las
direcciones son celdas logicas consecutivas, no direcciones fisicas en bytes.
La division entera trunca hacia cero; el resto sigue esa misma division.
Solo se convierten int a float. Los valores conocidos se propagan por el flujo;
entradas, ramas divergentes y escrituras de bucles pueden volverlos desconocidos.
Las anotaciones de bucles describen su primera evaluacion, no todas sus vueltas.
La inicializacion indica
asignacion segura en los caminos analizados, sin diagnosticar lecturas previas.
"""

from copy import deepcopy
import json
import math

from .ast_node import ASTNode
from .errores import ErrorCompilador


NUMERICOS = {"int", "float"}
TIPOS = NUMERICOS | {"bool"}
DESCONOCIDO = object()


class TablaSimbolos:
    """Tabla funcional indexada por (ambito, nombre), con usos y estado de flujo."""

    def __init__(self):
        self._simbolos = {}

    def buscar(self, nombre, ambito="global"):
        return self._simbolos.get((ambito, nombre))

    def obtener_tipo(self, nombre, ambito="global"):
        simbolo = self.buscar(nombre, ambito)
        return simbolo["tipo"] if simbolo else None

    def detectar_duplicado(self, nombre, ambito="global"):
        return self.buscar(nombre, ambito) is not None

    def insertar(self, nombre, tipo, linea=0, columna=0, ambito="global"):
        if tipo not in TIPOS:
            raise ValueError(f"Tipo de declaracion no permitido: {tipo}")
        if self.detectar_duplicado(nombre, ambito):
            return None
        direccion = len(self._simbolos)
        simbolo = {
            "id": direccion + 1, "nombre": nombre, "lexema": nombre,
            "tipo": tipo, "ambito": ambito, "scope": ambito,
            "linea": linea, "linea_declaracion": linea, "columna": columna,
            "lineas": [], "lineas_unicas": [], "ocurrencias": [],
            "direccion": direccion, "desplazamiento": direccion,
            "declarado": True, "inicializado": False,
            "valor_inicial_constante": None,
            "valor_conocido": False, "valor_actual": None,
            "motivo_desconocido": f"{nombre} sin inicializar",
        }
        self._simbolos[(ambito, nombre)] = simbolo
        self.registrar_uso(nombre, linea, columna, "declaracion", ambito)
        return simbolo

    def registrar_uso(self, nombre, linea, columna, contexto="lectura", ambito="global"):
        simbolo = self.buscar(nombre, ambito)
        if simbolo is not None:
            simbolo["lineas"].append(linea)
            if linea not in simbolo["lineas_unicas"]:
                simbolo["lineas_unicas"].append(linea)
            simbolo["ocurrencias"].append({
                "linea": linea, "columna": columna, "contexto": contexto,
            })
        return simbolo

    def estado_inicializacion(self):
        return {s["id"]: s["inicializado"] for s in self._simbolos.values()}

    def restaurar_inicializacion(self, estado):
        for simbolo in self._simbolos.values():
            simbolo["inicializado"] = estado.get(simbolo["id"], False)

    def exportar(self):
        return deepcopy(list(self._simbolos.values()))

    def estado_flujo(self):
        return {s["id"]: {k: s[k] for k in ("inicializado", "valor_conocido", "valor_actual", "motivo_desconocido")}
                for s in self._simbolos.values()}

    def restaurar_flujo(self, estado):
        for simbolo in self._simbolos.values():
            simbolo.update(estado.get(simbolo["id"], {
                "inicializado": False, "valor_conocido": False, "valor_actual": None,
                "motivo_desconocido": f"{simbolo['nombre']} sin inicializar",
            }))


class AnalizadorSemantico:
    """Recorrido dirigido por los nodos producidos por el parser existente."""

    def analizar(self, arbol):
        if not isinstance(arbol, ASTNode):
            raise TypeError("El analizador semantico requiere un ASTNode")
        self.tabla = TablaSimbolos()
        self.errores = []
        self.conversiones = []
        self.traza = []
        self.parcial = bool(arbol.atributos.get("sintaxis_recuperada"))
        original = deepcopy(arbol.to_dict())
        anotado = deepcopy(arbol)
        self._preparar(anotado, "0")
        self._recorrer(anotado)
        return {
            "arbol_original": original,
            "arbol_semantico": anotado.to_dict(),
            "tabla_simbolos": self.tabla.exportar(),
            "errores_semanticos": deepcopy(self.errores),
            "conversiones": deepcopy(self.conversiones),
            "traza_semantica": deepcopy(self.traza),
            "estado": "parcial" if self.parcial else "completo",
            "valido": not self.errores and not self.parcial,
        }

    def _preparar(self, nodo, ruta):
        recuperado = nodo.atributos.get("sintaxis_recuperada", False)
        nodo.atributos = {"id_nodo": ruta, "ambito": "global"}
        if recuperado:
            nodo.atributos["sintaxis_recuperada"] = True
        for i, hijo in enumerate(nodo.hijos):
            self._preparar(hijo, f"{ruta}.{i}")

    def _trazar(self, nodo, regla, accion, **datos):
        self.traza.append({
            "paso": len(self.traza) + 1,
            "nodo": nodo.atributos["id_nodo"], "regla": regla,
            "accion": accion, "linea": nodo.linea, "columna": nodo.columna,
            **datos,
        })

    def _tipo(self, nodo, tipo, constante=DESCONOCIDO):
        nodo.atributos["tipo_calculado"] = tipo
        nodo.atributos["es_constante"] = constante is not DESCONOCIDO
        nodo.atributos.pop("valor_constante", None)
        if constante is not DESCONOCIDO:
            nodo.atributos["valor_constante"] = constante
            nodo.atributos.pop("motivo_desconocido", None)
        elif tipo != "void":
            motivos = [h.atributos.get("motivo_desconocido") for h in nodo.hijos
                       if not h.atributos.get("es_constante")]
            motivo = "; ".join(dict.fromkeys(m for m in motivos if m))
            nodo.atributos.setdefault("motivo_desconocido", motivo or "valor no conocido en compilacion")
        if tipo == "bool" and nodo.nodo != "Tipo":
            nodo.atributos["resultado_booleano"] = None if constante is DESCONOCIDO else constante
            self._trazar(nodo, "evaluacion_booleana", "evaluar",
                         resultado=nodo.atributos["resultado_booleano"],
                         motivo=nodo.atributos.get("motivo_desconocido", ""))
        if nodo.nodo in {"OperacionRelacional", "OperacionLogica"}:
            nodo.atributos["operandos_evaluados"] = [
                {"tipo": h.atributos.get("tipo_calculado"),
                 "conocido": h.atributos.get("es_constante", False),
                 "valor": h.atributos.get("valor_constante"),
                 "motivo": h.atributos.get("motivo_desconocido", "")}
                for h in nodo.hijos]
        self._trazar(nodo, "sintesis", "propagar", atributo="tipo_calculado", valor=tipo)
        return tipo

    def _error(self, nodo, codigo, descripcion):
        nodo.atributos["motivo_desconocido"] = descripcion
        self.errores.append(ErrorCompilador(
            "Error Semantico", descripcion, nodo.linea, nodo.columna, codigo,
        ).to_dict())
        self._trazar(nodo, codigo, "error", descripcion=descripcion)
        return self._tipo(nodo, "error")

    def _incompleto(self, nodo):
        # Los huecos de recuperacion del parser no son errores semanticos nuevos.
        self.parcial = True
        self._trazar(nodo, "recuperacion_sintactica", "omitir")
        return self._tipo(nodo, "error")

    def _vincular(self, nodo, simbolo):
        nodo.atributos.update({
            "tipo_declarado": simbolo["tipo"], "ambito": simbolo["ambito"],
            "direccion": simbolo["direccion"],
            "desplazamiento": simbolo["desplazamiento"],
            "referencia_tabla_simbolos": simbolo["id"],
            "inicializado_al_usar": simbolo["inicializado"],
        })

    def _identificador(self, nodo, contexto="lectura"):
        simbolo = self.tabla.registrar_uso(
            nodo.valor, nodo.linea, nodo.columna, contexto,
        )
        self._trazar(nodo, "identificador", "buscar", nombre=nodo.valor,
                     encontrado=simbolo is not None,
                     simbolo_id=simbolo["id"] if simbolo else None)
        if simbolo is None:
            return self._error(nodo, "SEM_NO_DECLARADO",
                               f"El identificador '{nodo.valor}' no ha sido declarado")
        self._vincular(nodo, simbolo)
        valor = (simbolo["valor_actual"] if contexto == "lectura" and simbolo["valor_conocido"]
                 else DESCONOCIDO)
        if contexto == "lectura" and valor is DESCONOCIDO:
            nodo.atributos["motivo_desconocido"] = simbolo["motivo_desconocido"]
        return self._tipo(nodo, simbolo["tipo"], valor)

    def _valor_asignado(self, expresion, tipo):
        valor = expresion.atributos.get("valor_constante", DESCONOCIDO)
        if valor is not DESCONOCIDO and tipo == "float":
            try:
                valor = float(valor)
                if not math.isfinite(valor):
                    return DESCONOCIDO
            except OverflowError:
                return DESCONOCIDO
        return valor

    def _guardar_valor(self, simbolo, valor, nodo):
        simbolo["inicializado"] = True
        simbolo["valor_conocido"] = valor is not DESCONOCIDO
        simbolo["valor_actual"] = None if valor is DESCONOCIDO else valor
        origen = nodo.hijos[1] if nodo.nodo in {"Asignacion", "Inicializacion"} else nodo
        simbolo["motivo_desconocido"] = (origen.atributos.get("motivo_desconocido") or
            f"{simbolo['nombre']} sin valor conocido") if valor is DESCONOCIDO else ""
        self._trazar(nodo, "flujo_valores", "actualizar_valor", simbolo_id=simbolo["id"],
                     conocido=simbolo["valor_conocido"], valor=simbolo["valor_actual"])

    def _combinar_flujo(self, izquierda, derecha):
        combinado = {}
        desconocido = {"inicializado": False, "valor_conocido": False, "valor_actual": None}
        for i in self.tabla.estado_flujo():
            a, b = izquierda.get(i, desconocido), derecha.get(i, desconocido)
            conocido = (a["valor_conocido"] and b["valor_conocido"] and
                        type(a["valor_actual"]) is type(b["valor_actual"]) and
                        a["valor_actual"] == b["valor_actual"])
            combinado[i] = {"inicializado": a["inicializado"] and b["inicializado"],
                            "valor_conocido": conocido,
                            "valor_actual": a["valor_actual"] if conocido else None}
            combinado[i]["motivo_desconocido"] = "" if conocido else (
                a.get("motivo_desconocido") if a == b else "valor depende de ramas alternativas")
        return combinado

    def _modificados(self, nodo):
        nombres = set()
        pendientes = [nodo]
        while pendientes:
            actual = pendientes.pop()
            if actual.nodo in {"Asignacion", "Inicializacion", "Entrada", "OperacionIncremento"} and actual.hijos:
                destino = actual.hijos[0]
                while destino.nodo == "Grupo" and len(destino.hijos) == 1:
                    destino = destino.hijos[0]
                if destino.nodo == "Identificador":
                    nombres.add(destino.valor)
            pendientes.extend(actual.hijos)
        return nombres

    def _invalidar_valores(self, nombres):
        for nombre in nombres:
            simbolo = self.tabla.buscar(nombre)
            if simbolo:
                simbolo["valor_conocido"] = False
                simbolo["valor_actual"] = None
                simbolo["motivo_desconocido"] = f"{nombre} modificado en un bucle; valor final no determinado"

    def _contexto_bucle(self, nodo, contexto):
        nodo.atributos["contexto_valor"] = contexto
        for hijo in nodo.hijos:
            self._contexto_bucle(hijo, contexto)

    def _convertir(self, operando, contexto, motivo):
        conversion = {
            "id": len(self.conversiones) + 1, "de": "int", "a": "float",
            "nodo_origen": operando.atributos["id_nodo"],
            "nodo_contexto": contexto.atributos["id_nodo"], "motivo": motivo,
            "linea": operando.linea, "columna": operando.columna,
        }
        self.conversiones.append(conversion)
        operando.atributos.setdefault("conversion_aplicada", []).append(deepcopy(conversion))
        operando.atributos["tipo_contextual"] = "float"
        self._trazar(operando, "int_a_float", "convertir", **conversion)

    def _compatible(self, destino, expresion, contexto):
        origen = expresion.atributos["tipo_calculado"]
        if "error" in {destino, origen}:
            return False
        if origen == "void":
            self._error(contexto, "SEM_EXPRESION_VACIA", "La asignacion requiere una expresion")
            return False
        if destino == origen:
            self._trazar(contexto, "asignacion", "comprobar", destino=destino, origen=origen)
            return True
        if destino == "float" and origen == "int":
            self._convertir(expresion, contexto, "asignacion")
            return True
        if destino == "int" and origen == "float":
            self._error(contexto, "SEM_CONVERSION_INVALIDA",
                        "Asignacion incompatible: no se permite convertir float a int")
        else:
            self._error(contexto, "SEM_ASIGNACION_INCOMPATIBLE",
                        f"Asignacion incompatible: destino {destino}, expresion {origen}")
        return False

    def _declaracion(self, nodo):
        if len(nodo.hijos) != 2 or nodo.hijos[0].valor not in TIPOS:
            return self._incompleto(nodo)
        tipo, identificadores = nodo.hijos
        if identificadores.nodo != "Identificadores":
            return self._incompleto(nodo)
        dtype = tipo.valor
        self._tipo(tipo, dtype)
        for receptor in (tipo, nodo, identificadores):
            receptor.atributos["tipo_declarado"] = dtype
        self._trazar(identificadores, "declaracion", "heredar",
                     atributo="tipo_declarado", valor=dtype,
                     nodo_origen=tipo.atributos["id_nodo"])
        for declarador in identificadores.hijos:
            inicializacion = declarador.nodo == "Inicializacion"
            if inicializacion and len(declarador.hijos) != 2:
                self._incompleto(declarador)
                continue
            identificador = declarador.hijos[0] if inicializacion else declarador
            if identificador.nodo != "Identificador":
                self._incompleto(declarador)
                continue
            declarador.atributos["tipo_declarado"] = dtype
            identificador.atributos["tipo_declarado"] = dtype
            self._trazar(identificador, "declaracion", "heredar",
                         atributo="tipo_declarado", valor=dtype,
                         nodo_origen=identificadores.atributos["id_nodo"])
            simbolo = self.tabla.insertar(
                identificador.valor, dtype, identificador.linea, identificador.columna,
            )
            if simbolo is None:
                self.tabla.registrar_uso(identificador.valor, identificador.linea,
                                        identificador.columna, "declaracion_duplicada")
                self._error(identificador, "SEM_DUPLICADO",
                            f"Declaracion duplicada de '{identificador.valor}' en global")
            else:
                self._vincular(identificador, simbolo)
                self._tipo(identificador, dtype)
                self._trazar(identificador, "declaracion", "insertar",
                             nombre=identificador.valor, simbolo_id=simbolo["id"])
            if inicializacion:
                expresion = declarador.hijos[1]
                self._expresion(expresion)
                compatible = simbolo is not None and self._compatible(dtype, expresion, declarador)
                valor = DESCONOCIDO
                if compatible:
                    valor = self._valor_asignado(expresion, dtype)
                    self._guardar_valor(simbolo, valor, declarador)
                    simbolo["valor_inicial_constante"] = None if valor is DESCONOCIDO else valor
                    self._tipo(identificador, dtype, valor)
                self._tipo(declarador, dtype if compatible else "error", valor)
        self._tipo(identificadores, "void")
        return self._tipo(nodo, "void")

    def _asignacion(self, nodo):
        if len(nodo.hijos) != 2 or nodo.hijos[0].nodo != "Identificador":
            return self._incompleto(nodo)
        identificador, expresion = nodo.hijos
        destino = self._identificador(identificador, "asignacion")
        self._expresion(expresion)
        if self._compatible(destino, expresion, nodo):
            valor = self._valor_asignado(expresion, destino)
            self._guardar_valor(self.tabla.buscar(identificador.valor), valor, nodo)
            self._tipo(identificador, destino, valor)
            return self._tipo(nodo, destino, valor)
        return self._tipo(nodo, "error")

    def _condicion(self, expresion):
        tipo = self._expresion(expresion)
        if tipo not in {"bool", "error"}:
            self._error(expresion, "SEM_CONDICION_NO_BOOLEANA",
                        f"La condicion requiere bool; se obtuvo {tipo}")
        self._trazar(expresion, "condicion", "comprobar", esperado="bool", obtenido=tipo)
        expresion.atributos["resultado_condicion"] = (
            expresion.atributos.get("valor_constante") if tipo == "bool" else None)
        expresion.atributos["condicion_valida"] = tipo == "bool"
        return expresion.atributos["resultado_condicion"]

    def _anotar_control(self, nodo, condicion):
        for atributo in ("resultado_condicion", "condicion_valida", "motivo_desconocido"):
            if atributo in condicion.atributos:
                nodo.atributos[atributo] = deepcopy(condicion.atributos[atributo])
        nodo.atributos["resultado_booleano"] = condicion.atributos["resultado_condicion"]

    def _seleccion(self, nodo):
        if len(nodo.hijos) not in {2, 3}:
            return self._incompleto(nodo)
        condicion = nodo.hijos[0]
        resultado_condicion = self._condicion(condicion)
        nodo.atributos["resultado_condicion"] = resultado_condicion
        nodo.atributos["condicion_valida"] = condicion.atributos["condicion_valida"]
        self._anotar_control(nodo, condicion)
        antes = self.tabla.estado_flujo()
        self._recorrer(nodo.hijos[1])
        rama_then = self.tabla.estado_flujo()
        self.tabla.restaurar_flujo(antes)
        if len(nodo.hijos) == 3:
            self._recorrer(nodo.hijos[2])
        rama_else = self.tabla.estado_flujo()
        if resultado_condicion is not None:
            combinado = rama_then if resultado_condicion else rama_else
        else:
            combinado = self._combinar_flujo(rama_then, rama_else)
        self.tabla.restaurar_flujo(combinado)
        self._trazar(nodo, "seleccion", "combinar_flujo", estado=combinado)
        return self._tipo(nodo, "void")

    def _recorrer(self, nodo):
        nombre = nodo.nodo
        if nombre == "DeclaracionVariable":
            return self._declaracion(nodo)
        if nombre == "Asignacion":
            return self._asignacion(nodo)
        if nombre == "Seleccion":
            return self._seleccion(nodo)
        if nombre in {"IteracionWhile", "RepeticionDoWhile"}:
            if len(nodo.hijos) != 2:
                return self._incompleto(nodo)
            if nombre == "IteracionWhile":
                condicion, cuerpo = nodo.hijos
                self._contexto_bucle(condicion, "entrada del while")
                resultado_condicion = self._condicion(condicion)
                antes = self.tabla.estado_flujo()
                self._contexto_bucle(cuerpo, "cuerpo no ejecutado" if resultado_condicion is False
                                     else "primera iteracion del while")
                if resultado_condicion is False:
                    self._invalidar_valores(self._modificados(cuerpo))
                self._recorrer(cuerpo)
                despues = self.tabla.estado_flujo()
                self.tabla.restaurar_flujo(despues if resultado_condicion is True else antes)
                if resultado_condicion is not False:
                    self._invalidar_valores(self._modificados(nodo))
            else:
                cuerpo, condicion = nodo.hijos
                self._contexto_bucle(cuerpo, "primera iteracion del do-while")
                self._recorrer(cuerpo)
                self._contexto_bucle(condicion, "primera condicion del do-while")
                resultado_condicion = self._condicion(condicion)
                if resultado_condicion is not False:
                    self._invalidar_valores(self._modificados(nodo))
            nodo.atributos["resultado_condicion"] = resultado_condicion
            nodo.atributos["condicion_valida"] = condicion.atributos["condicion_valida"]
            self._anotar_control(nodo, condicion)
            nodo.atributos["contexto_valor"] = ("entrada del while" if nombre == "IteracionWhile"
                                               else "primera condicion del do-while")
            return self._tipo(nodo, "void")
        if nombre == "Entrada":
            if len(nodo.hijos) != 1 or nodo.hijos[0].nodo != "Identificador":
                return self._incompleto(nodo)
            identificador = nodo.hijos[0]
            tipo = self._identificador(identificador, "entrada")
            if tipo != "error":
                nodo.atributos["motivo_desconocido"] = f"{identificador.valor} recibido por cin; valor de ejecucion"
                self._guardar_valor(self.tabla.buscar(identificador.valor), DESCONOCIDO, nodo)
            return self._tipo(nodo, tipo)
        if nombre in {"Programa", "ListaDeclaracion", "Then", "Else", "Cuerpo",
                      "Salida", "ContenidoSalida"}:
            for hijo in nodo.hijos:
                self._recorrer(hijo)
            return self._tipo(nodo, "void")
        return self._expresion(nodo, como_sentencia=nombre == "Expresion")

    def _expresion(self, nodo, *, como_sentencia=False):
        nombre = nodo.nodo
        if nombre == "Identificador":
            return self._identificador(nodo)
        if nombre == "Numero":
            tipo = "int" if nodo.tipo == "NUMERO_ENTERO" else "float"
            try:
                valor = int(nodo.valor) if tipo == "int" else float(nodo.valor)
                if isinstance(valor, float) and not math.isfinite(valor):
                    valor = DESCONOCIDO
            except (ValueError, OverflowError):
                valor = DESCONOCIDO
            return self._tipo(nodo, tipo, valor)
        if nombre == "Booleano":
            return self._tipo(nodo, "bool", nodo.valor == "true")
        if nombre == "Cadena":
            try:
                valor = json.loads(nodo.valor)
            except json.JSONDecodeError:
                valor = DESCONOCIDO
            return self._tipo(nodo, "cadena", valor)
        if nombre in {"Grupo", "SentExpresion", "Expresion"}:
            if not nodo.hijos and nombre == "SentExpresion":
                return self._tipo(nodo, "void")
            if len(nodo.hijos) != 1:
                return self._incompleto(nodo)
            hijo = nodo.hijos[0]
            tipo = self._expresion(hijo, como_sentencia=como_sentencia)
            return self._tipo(nodo, tipo, hijo.atributos.get("valor_constante", DESCONOCIDO))
        if nombre == "OperacionIncremento":
            if len(nodo.hijos) != 1:
                return self._incompleto(nodo)
            operando = nodo.hijos[0]
            tipo = self._expresion(operando)
            destino = operando
            while destino.nodo == "Grupo" and len(destino.hijos) == 1:
                destino = destino.hijos[0]
            if tipo == "error":
                return self._tipo(nodo, "error")
            if tipo not in NUMERICOS or destino.nodo != "Identificador":
                return self._error(nodo, "SEM_OPERADOR_INVALIDO",
                                   f"'{nodo.valor}' requiere un identificador numerico modificable")
            simbolo = self.tabla.buscar(destino.valor)
            valor = operando.atributos.get("valor_constante", DESCONOCIDO)
            if valor is not DESCONOCIDO:
                actualizado = valor + (1 if nodo.valor == "++" else -1)
                self._guardar_valor(simbolo, actualizado, nodo)
                if como_sentencia:
                    # Una sentencia independiente muestra el estado resultante.
                    # Dentro de otra expresion, postfix conserva el valor anterior.
                    valor = actualizado
                    actual = operando
                    while actual is not destino:
                        self._tipo(actual, tipo, valor)
                        actual = actual.hijos[0]
                    self._tipo(destino, tipo, valor)
            return self._tipo(nodo, tipo, valor)
        if nombre == "OperacionLogica" and nodo.valor == "!":
            if len(nodo.hijos) != 1:
                return self._incompleto(nodo)
            hijo = nodo.hijos[0]
            tipo = self._expresion(hijo)
            if tipo == "error":
                return self._tipo(nodo, "error")
            if tipo != "bool":
                return self._error(nodo, "SEM_OPERADOR_INVALIDO", "'!' requiere un operando bool")
            valor = not hijo.atributos["valor_constante"] if hijo.atributos.get("es_constante") else DESCONOCIDO
            return self._tipo(nodo, "bool", valor)
        if nombre in {"OperacionSuma", "OperacionMultiplicacion", "OperacionPotencia",
                      "OperacionRelacional", "OperacionLogica"}:
            return self._binaria(nodo)
        return self._incompleto(nodo)

    def _binaria(self, nodo):
        if len(nodo.hijos) != 2:
            for hijo in nodo.hijos:
                self._expresion(hijo)
            return self._incompleto(nodo)
        izquierda, derecha = nodo.hijos
        tipo_izquierda = self._expresion(izquierda)
        antes_derecha = self.tabla.estado_flujo() if nodo.valor in {"&&", "||"} else None
        tipo_derecha = self._expresion(derecha)
        if nodo.valor in {"&&", "||"}:
            valor_izquierda = izquierda.atributos.get("valor_constante", DESCONOCIDO)
            omitir = ((nodo.valor == "&&" and valor_izquierda is False) or
                      (nodo.valor == "||" and valor_izquierda is True))
            if omitir:
                self.tabla.restaurar_flujo(antes_derecha)
            elif valor_izquierda is DESCONOCIDO:
                self.tabla.restaurar_flujo(self._combinar_flujo(antes_derecha, self.tabla.estado_flujo()))
        tipos = [tipo_izquierda, tipo_derecha]
        if "error" in tipos:
            return self._tipo(nodo, "error")
        op = nodo.valor
        numericos = all(t in NUMERICOS for t in tipos)
        if op in {"&&", "||"}:
            if tipos != ["bool", "bool"]:
                return self._error(nodo, "SEM_OPERADOR_INVALIDO", f"'{op}' requiere dos operandos bool")
            resultado = "bool"
        elif op in {"<", "<=", ">", ">=", "==", "!="}:
            if not numericos and not (op in {"==", "!="} and tipos == ["bool", "bool"]):
                return self._error(nodo, "SEM_TIPOS_INCOMPATIBLES",
                                   f"Operandos incompatibles para '{op}': {tipos[0]} y {tipos[1]}")
            resultado = "bool"
        elif op in {"+", "-", "*", "/", "%", "^"}:
            if not numericos or (op == "%" and tipos != ["int", "int"]):
                return self._error(nodo, "SEM_OPERADOR_INVALIDO",
                                   f"Tipos incorrectos para '{op}': {tipos[0]} y {tipos[1]}")
            resultado = "float" if "float" in tipos else "int"
        else:
            return self._error(nodo, "SEM_OPERADOR_INVALIDO", f"Uso binario no permitido de '{op}'")
        if numericos and "float" in tipos:
            for hijo, tipo in zip(nodo.hijos, tipos):
                if tipo == "int":
                    self._convertir(hijo, nodo, "operandos mixtos")
        derecha = nodo.hijos[1].atributos
        if op in {"/", "%"} and derecha.get("es_constante") and derecha["valor_constante"] == 0:
            return self._error(nodo, "SEM_DIVISION_CERO", "Division o resto con divisor constante cero")
        valor = self._constante_binaria(nodo, resultado)
        if nodo.atributos.get("tipo_calculado") == "error":
            return "error"
        return self._tipo(nodo, resultado, valor)

    def _constante_binaria(self, nodo, tipo):
        if nodo.valor in {"&&", "||"}:
            valores = [h.atributos.get("valor_constante", DESCONOCIDO) for h in nodo.hijos]
            if nodo.valor == "&&" and any(v is False for v in valores):
                return False
            if nodo.valor == "||" and any(v is True for v in valores):
                return True
        if not all(h.atributos.get("es_constante") for h in nodo.hijos):
            return DESCONOCIDO
        a, b = (h.atributos["valor_constante"] for h in nodo.hijos)
        op = nodo.valor
        try:
            if any(h.atributos.get("tipo_contextual") == "float" for h in nodo.hijos):
                a, b = float(a), float(b)
            if op == "^":
                if tipo == "int" and b < 0:
                    raise ValueError("exponente negativo en potencia entera")
                # Limita trabajo de compilacion sin limitar la expresion del lenguaje.
                if abs(b) > 4096 or (tipo == "int" and a.bit_length() * b > 4096):
                    return DESCONOCIDO
                valor = pow(a, b)
                if isinstance(valor, complex):
                    raise ValueError("potencia fuera del dominio real")
            elif op in {"/", "%"} and tipo == "int":
                cociente = (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
                valor = cociente if op == "/" else a - cociente * b
            else:
                operaciones = {
                    "+": lambda: a + b, "-": lambda: a - b, "*": lambda: a * b,
                    "/": lambda: a / b, "<": lambda: a < b, "<=": lambda: a <= b,
                    ">": lambda: a > b, ">=": lambda: a >= b,
                    "==": lambda: a == b, "!=": lambda: a != b,
                    "&&": lambda: a and b, "||": lambda: a or b,
                }
                valor = operaciones[op]()
            if isinstance(valor, float) and not math.isfinite(valor):
                return DESCONOCIDO
            return valor
        except (ValueError, ZeroDivisionError) as error:
            self._error(nodo, "SEM_DOMINIO_CONSTANTE", f"Operacion constante no valida: {error}")
            return DESCONOCIDO
        except OverflowError:
            return DESCONOCIDO


def analisis_semantico(arbol):
    """Devuelve AST original/anotado y resultados serializables, sin escribir archivos."""
    return AnalizadorSemantico().analizar(arbol)
