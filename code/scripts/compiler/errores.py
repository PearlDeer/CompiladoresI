from dataclasses import dataclass


@dataclass
class ErrorCompilador:
    """Error de compilacion con ubicacion en el codigo fuente."""

    tipo: str
    descripcion: str
    linea: int
    columna: int
    codigo: str = ""

    def to_dict(self) -> dict:
        resultado = {
            "linea": self.linea,
            "columna": self.columna,
            "tipo": self.tipo,
            "descripcion": self.descripcion,
        }
        if self.codigo:
            resultado["codigo"] = self.codigo
        return resultado

