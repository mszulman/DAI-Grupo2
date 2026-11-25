"""
Contrato de datos v1: lo que el LLM debe devolver en el paso 4 del journey.

De dónde sale (Entrega 1):
    - Los valores de `intencion` son EXACTAMENTE los de la Matriz de Intenciones (B.4).
    - Los campos son los datos que necesitan los pasos 5 a 7 del user journey (B.2).

Pydantic verifica que el JSON esté BIEN FORMADO (campos, tipos, valores permitidos).
Si el dato es VÁLIDO PARA EL NEGOCIO (por ejemplo, si la unidad es del vecino)
lo deciden las reglas (reglas.py).
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Intencion = Literal[
    "EMERGENCIA",
    "SOLICITUD_REINTEGRO",
    "NUEVO_RECLAMO",
    "AMPLIAR_RECLAMO",
    "ESTADO_RECLAMO",
    "FUERA_DE_ALCANCE",
]

Rubro = Literal["ascensor", "agua", "gas", "electricidad", "cerrajeria", "estructura", "otro"]

Ubicacion = Literal["unidad", "espacio_comun"]


class ExtraccionReclamo(BaseModel):
    # extra="forbid": si el LLM agrega un campo que no existe en el contrato
    # (por ejemplo "reintegro_aprobado": true), la validación falla.
    model_config = ConfigDict(extra="forbid")

    intencion: Intencion
    edificio_mencionado: Optional[str] = None
    # Piso + letra normalizados: "4B", "PBA", "PB", "12C".
    unidad_mencionada: Optional[str] = Field(default=None, pattern=r"^(PB|\d{1,2})[A-Z]?$")
    rubro: Optional[Rubro] = None
    ubicacion: Optional[Ubicacion] = None
    # El prompt pide 15 palabras o menos; acá se pone un tope generoso en caracteres.
    descripcion_problema: Optional[str] = Field(default=None, max_length=200)
    # Solo dígitos: el código lo busca en la base sin limpiar "N°" ni "#".
    numero_reclamo_mencionado: Optional[str] = Field(default=None, pattern=r"^\d+$")
