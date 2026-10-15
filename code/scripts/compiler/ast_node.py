from dataclasses import dataclass, field
from copy import deepcopy
import json


@dataclass
class ASTNode:
    """Nodo simple para representar el Arbol Sintactico Abstracto."""

    nodo: str
    valor: str = ""
    tipo: str = ""
    hijos: list["ASTNode"] = field(default_factory=list)
    linea: int = 0
    columna: int = 0
    atributos: dict = field(default_factory=dict)

    def agregar(self, hijo: "ASTNode | None") -> "ASTNode":
        """Agrega un hijo si existe y regresa el nodo actual."""
        if hijo is not None:
            self.hijos.append(hijo)
        return self

    def to_dict(self) -> dict:
        """Convierte el AST a diccionario para que PyQt6 lo muestre facilmente."""
        return {
            "nodo": self.nodo,
            "valor": self.valor,
            "tipo": self.tipo,
            "hijos": [hijo.to_dict() for hijo in self.hijos],
            "linea": self.linea,
            "columna": self.columna,
            "atributos": deepcopy(self.atributos),
        }

    def to_text(self, nivel: int = 0, *, incluir_atributos: bool = False) -> str:
        """Convierte el AST a texto indentado para guardarlo en ast.txt."""
        sangria = "  " * nivel
        detalle = ""
        if self.valor:
            detalle += f": {self.valor}"
        if self.tipo:
            detalle += f" [{self.tipo}]"
        if incluir_atributos:
            detalle += f" (linea {self.linea}, columna {self.columna})"
            if self.atributos:
                detalle += " " + json.dumps(self.atributos, ensure_ascii=False)

        lineas = [f"{sangria}{self.nodo}{detalle}"]
        for hijo in self.hijos:
            lineas.append(hijo.to_text(nivel + 1, incluir_atributos=incluir_atributos))
        return "\n".join(lineas)

