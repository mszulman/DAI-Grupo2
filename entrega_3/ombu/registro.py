"""
Registro de reclamos: la "base de datos" que consultan y modifican los pasos 6 y 7 del journey.

En producción sería el sistema de gestión de la administradora. Para la práctica lo simulamos:
se carga de datos/reclamos.json y trabaja EN MEMORIA, así que cada corrida arranca igual y
el archivo nunca se modifica.

Inyección de dependencias (teoría, Unidad 2, 4.3): el workflow RECIBE un RegistroReclamos en
lugar de construirlo adentro. Así se puede probar con un registro de prueba y cambiar la
implementación (un archivo, una base real) sin tocar el workflow.

Cada método está marcado como:
    SENSOR   → solo lee, no modifica nada (riesgo bajo)
    ACTUADOR → modifica el registro (escribe)
"""

import copy
import json
from pathlib import Path
from typing import Optional

from .config import RAIZ_PROYECTO

ARCHIVO_RECLAMOS = RAIZ_PROYECTO / "datos" / "reclamos.json"
CERRADOS = {"RESUELTO"}


class RegistroReclamos:

    def __init__(self, reclamos: list[dict]):
        self._reclamos = copy.deepcopy(reclamos)
        self._ultimo_numero = max((int(r["numero"]) for r in self._reclamos), default=3000)

    @classmethod
    def desde_archivo(cls, ruta: Path = ARCHIVO_RECLAMOS) -> "RegistroReclamos":
        return cls(json.loads(Path(ruta).read_text(encoding="utf-8")))

    # ── SENSORES (solo leen) ────────────────────────────────────────────────

    def buscar_por_numero(self, numero: str) -> Optional[dict]:
        """SENSOR. El reclamo con ese número, o None si no existe."""
        for r in self._reclamos:
            if r["numero"] == numero:
                return copy.deepcopy(r)
        return None

    def buscar_duplicado(self, uf: dict, rubro: str, ubicacion: Optional[str]) -> Optional[dict]:
        """
        SENSOR. Un reclamo ABIERTO que ya cubre el mismo problema, o None.
        - Espacio común: mismo edificio y mismo rubro, aunque lo haya hecho otro vecino
          (el ascensor parado es uno solo, lo avisen 15 vecinos o uno).
        - Dentro de una unidad: misma unidad y mismo rubro.
        """
        for r in self._reclamos:
            if r["estado"] in CERRADOS or r["rubro"] != rubro:
                continue
            if ubicacion == "espacio_comun" and r["ubicacion"] == "espacio_comun" \
                    and r["consorcio"] == uf["consorcio"]:
                return copy.deepcopy(r)
            if ubicacion != "espacio_comun" and r["uf_id"] == uf["uf_id"]:
                return copy.deepcopy(r)
        return None

    def reclamos_visibles(self, uf: dict, rubro: Optional[str] = None) -> list[dict]:
        """
        SENSOR. Los reclamos que un vecino puede consultar: los de su unidad y los de espacios
        comunes de su edificio. Nunca los de otra unidad (privacidad). Más nuevos primero.
        """
        visibles = [r for r in self._reclamos
                    if (r["uf_id"] == uf["uf_id"]
                        or (r["ubicacion"] == "espacio_comun" and r["consorcio"] == uf["consorcio"]))
                    and (rubro is None or r["rubro"] == rubro)]
        return copy.deepcopy(sorted(visibles, key=lambda r: r["fecha_alta"], reverse=True))

    def puede_ver(self, reclamo: dict, uf: dict) -> bool:
        """Regla de privacidad: ¿este vecino puede ver o modificar este reclamo?"""
        return reclamo["uf_id"] == uf["uf_id"] or (
            reclamo["ubicacion"] == "espacio_comun" and reclamo["consorcio"] == uf["consorcio"])

    # ── ACTUADORES (escriben) ───────────────────────────────────────────────

    def registrar(self, uf: dict, rubro: str, ubicacion: Optional[str], descripcion: Optional[str],
                  prioridad: str, fecha: str) -> dict:
        """ACTUADOR. Registra un reclamo nuevo y devuelve el reclamo con su número REAL."""
        self._ultimo_numero += 1
        reclamo = {
            "numero": str(self._ultimo_numero),
            "uf_id": uf["uf_id"],
            "consorcio": uf["consorcio"],
            "rubro": rubro,
            "ubicacion": ubicacion or "unidad",
            "descripcion": descripcion or "Sin descripción",
            "prioridad": prioridad,
            "estado": "ABIERTO",
            "fecha_alta": fecha,
            "avisos": [],
            "notas": [],
        }
        self._reclamos.append(reclamo)
        return copy.deepcopy(reclamo)

    def sumar_aviso(self, numero: str, uf: dict) -> dict:
        """ACTUADOR. Suma el aviso de otro vecino a un reclamo existente (no crea uno nuevo)."""
        r = self._buscar_interno(numero)
        if uf["uf_id"] not in r["avisos"] and uf["uf_id"] != r["uf_id"]:
            r["avisos"].append(uf["uf_id"])
        return copy.deepcopy(r)

    def agregar_nota(self, numero: str, uf: dict, nota: str) -> dict:
        """ACTUADOR. Agrega información nueva del vecino a un reclamo existente."""
        r = self._buscar_interno(numero)
        r["notas"].append(f"[{uf['uf_id']}] {nota}")
        return copy.deepcopy(r)

    def _buscar_interno(self, numero: str) -> dict:
        for r in self._reclamos:
            if r["numero"] == numero:
                return r
        raise KeyError(f"No existe el reclamo {numero}")
