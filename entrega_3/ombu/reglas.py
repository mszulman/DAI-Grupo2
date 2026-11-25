"""
Reglas de negocio deterministas: si entra X, siempre sale Y.
Por eso las ejecuta Python y NO el LLM.

Hoy (Entrega 2), del user journey de la Entrega 1 (B.2):
    - Paso 2: identificar al remitente por su teléfono en el padrón.
    - Paso 3: filtro de emergencias por palabras clave (corre ANTES del LLM).
    - Paso 5: verificar que la unidad mencionada pertenezca al remitente.
Entrega 3: búsqueda de duplicados (paso 6), prioridad y registro del reclamo (paso 7).
"""

import json
import re
import unicodedata
from typing import Optional

from .config import RAIZ_PROYECTO

# Respuesta fija ante una emergencia: NO la redacta el LLM (Matriz B.4).
RESPUESTA_EMERGENCIA = (
    "Recibimos tu aviso como EMERGENCIA y ya lo derivamos a la guardia de "
    "Administración Ombú. Si hay riesgo para las personas, llamá al 911 "
    "(Bomberos: 100). Ante olor a gas: no prendas luces ni artefactos eléctricos, "
    "abrí ventanas y salí del lugar."
)

# Frases (no palabras sueltas): "gas" solo aparece también en reclamos comunes
# ("no tengo gas en la cocina"), que no son emergencias.
PATRONES_EMERGENCIA = [
    r"olor a gas", r"perdida de gas", r"escape de gas",
    r"inundaci", r"se (esta )?inunda",
    r"incendio", r"\bhumo\b", r"\bfuego\b", r"chispa", r"cortocircuito",
    r"(atrapad|encerrad)[oa]s? en el ascensor", r"quedo (alguien )?(atrapad|encerrad)",
    r"derrumbe", r"se (cayo|esta cayendo) (el|un|una|la) (techo|cielorraso|balcon|pared)",
]


def normalizar_texto(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar de forma robusta."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sin_tildes.lower()


# ── Paso 3 — Filtro de emergencias ──────────────────────────────────────────

def detectar_emergencia(mensaje: str) -> Optional[str]:
    """Devuelve el patrón que coincidió, o None. Regla binaria: si coincide, siempre escala."""
    texto = normalizar_texto(mensaje)
    for patron in PATRONES_EMERGENCIA:
        if re.search(patron, texto):
            return patron
    return None


# ── Paso 2 — Identificación del remitente ───────────────────────────────────

def cargar_padron() -> dict:
    """Padrón ficticio: teléfono → unidades vinculadas. En producción sale del sistema de gestión."""
    return json.loads((RAIZ_PROYECTO / "datos" / "padron.json").read_text(encoding="utf-8"))


def identificar_remitente(telefono: str, padron: Optional[dict] = None) -> list[dict]:
    """Búsqueda exacta en el padrón por los dígitos del teléfono. Si no está, lista vacía."""
    padron = cargar_padron() if padron is None else padron
    return padron.get(re.sub(r"\D", "", telefono or ""), [])


# ── Paso 5 — La unidad mencionada tiene que ser del remitente ───────────────

def resolver_unidad(extraccion: dict, ufs_vinculadas: list[dict]) -> tuple[Optional[dict], str]:
    """
    Decide sobre qué UF se opera. Solo se registran reclamos de unidades vinculadas
    al teléfono del remitente. Devuelve (uf, motivo); uf es None si no se puede resolver.
    """
    candidatas = ufs_vinculadas

    edificio = extraccion.get("edificio_mencionado")
    if edificio:
        edif = normalizar_texto(edificio)
        coinciden = [u for u in candidatas if edif in normalizar_texto(u["consorcio"])
                     or normalizar_texto(u["consorcio"]) in edif]
        if not coinciden:
            return None, f"NO_VINCULADA: el edificio '{edificio}' no corresponde a este teléfono"
        candidatas = coinciden

    unidad = extraccion.get("unidad_mencionada")
    if unidad:
        candidatas = [u for u in candidatas if u["unidad"] == unidad]
        if not candidatas:
            return None, f"NO_VINCULADA: la unidad {unidad} no está vinculada a este teléfono"

    if len(candidatas) == 1:
        return candidatas[0], "Unidad identificada"
    opciones = ", ".join(f"{u['unidad']} de {u['consorcio']}" for u in candidatas)
    return None, f"AMBIGUA: el teléfono tiene varias unidades ({opciones}); hay que pedir aclaración"
