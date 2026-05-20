from dataclasses import dataclass, field


@dataclass
class ASTNode:
    """Nodo simple para representar el Arbol Sintactico Abstracto."""

    nodo: str
    valor: str = ""
    tipo: str = ""
    hijos: list["ASTNode"] = field(default_factory=list)

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
        }

    def to_text(self, nivel: int = 0) -> str:
        """Convierte el AST a texto indentado para guardarlo en ast.txt."""
        sangria = "  " * nivel
        detalle = ""
        if self.valor:
            detalle += f": {self.valor}"
        if self.tipo:
            detalle += f" [{self.tipo}]"

        lineas = [f"{sangria}{self.nodo}{detalle}"]
        for hijo in self.hijos:
            lineas.append(hijo.to_text(nivel + 1))
        return "\n".join(lineas)

