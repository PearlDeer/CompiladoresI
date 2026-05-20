from dataclasses import dataclass


@dataclass
class ErrorCompilador:
    """Error de compilacion con ubicacion en el codigo fuente."""

    tipo: str
    descripcion: str
    linea: int
    columna: int

    def to_dict(self) -> dict:
        return {
            "linea": self.linea,
            "columna": self.columna,
            "tipo": self.tipo,
            "descripcion": self.descripcion,
        }

