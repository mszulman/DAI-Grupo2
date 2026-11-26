"""
El componente completo: pasos 2 a 5 del user journey de la Entrega 1.

    Mensaje ─┬─ [Regla] ¿mensaje vacío?               paso 1
             ├─ [Regla] ¿emergencia? → escala sin LLM paso 3
             ├─ [Regla] ¿teléfono en el padrón?       paso 2
             ├─ [LLM + prompt] → texto                paso 4
             ├─ json.loads()      ¿es JSON?           ┐
             ├─ Pydantic          ¿cumple contrato?   ├ paso 5
             └─ [Regla] ¿la unidad es del vecino?     ┘

Cada etapa puede fallar, y cada falla se informa por separado:
    COMUNICACION → el modelo no respondió (red, key, saturación)
    FORMATO      → respondió algo que no es JSON
    CONTRATO     → es JSON pero no cumple el contrato
    REGLA        → cumple el contrato pero un dato no es válido para el negocio
"""

import json
import urllib.error
from typing import Optional

from pydantic import ValidationError

from .config import RAIZ_PROYECTO, detectar_proveedor
from .contrato import ExtraccionReclamo
from .llm import describir_error_http, llamar_con_reintentos
from .reglas import RESPUESTA_EMERGENCIA, detectar_emergencia, identificar_remitente, resolver_unidad

PROMPT_VERSION = "v2"   # v2 suma CONSULTA_REGLAMENTO (Parte B); v1 queda para comparar

# Acción determinista y riesgo por intención (Matriz de la Entrega 1, B.4).
# El LLM nunca elige la acción: la elige esta tabla. Se ejecutan en la Entrega 3.
ACCIONES = {
    "EMERGENCIA":          {"accion": "protocolo_guardia",               "riesgo": "ALTO"},
    "SOLICITUD_REINTEGRO": {"accion": "registrar_pedido_y_derivar",      "riesgo": "ALTO"},
    "NUEVO_RECLAMO":       {"accion": "buscar_duplicado_y_registrar",    "riesgo": "MEDIO"},
    "AMPLIAR_RECLAMO":     {"accion": "agregar_info_a_reclamo",          "riesgo": "MEDIO"},
    "ESTADO_RECLAMO":      {"accion": "consultar_estado_reclamo",        "riesgo": "BAJO"},
    "CONSULTA_REGLAMENTO": {"accion": "responder_con_rag",               "riesgo": "BAJO"},
    "FUERA_DE_ALCANCE":    {"accion": "derivar_a_administrativo",        "riesgo": "BAJO"},
}


def cargar_prompt(version: str = PROMPT_VERSION) -> str:
    """El prompt vive en un archivo aparte: así se puede comparar v0 con v1 sin tocar el código."""
    return (RAIZ_PROYECTO / "prompts" / f"extraccion_{version}.txt").read_text(encoding="utf-8")


def armar_mensaje_usuario(mensaje: str) -> str:
    """Delimita el mensaje del vecino para que el modelo lo trate como dato, no como instrucción."""
    return f"Mensaje del vecino (entre <mensaje> y </mensaje>):\n<mensaje>\n{mensaje.strip()}\n</mensaje>"


def escalar_emergencia(motivo: str) -> dict:
    return {"ok": True, "etapa": "EMERGENCIA_ESCALADA", "motivo": motivo,
            "respuesta_fija": RESPUESTA_EMERGENCIA, **ACCIONES["EMERGENCIA"]}


def validar_respuesta(texto: str) -> dict:
    """
    Paso 5 (primera parte) — validación en dos niveles.
    No limpiamos bloques ```json: si el modelo los agrega, rompió la regla 4 del
    prompt y queremos verlo como error de FORMATO.
    """
    try:
        datos = json.loads(texto)                       # Nivel 1: ¿es JSON?
    except (json.JSONDecodeError, TypeError) as e:
        return {"ok": False, "error": "FORMATO", "detalle": f"No es JSON válido ({e})"}

    if not isinstance(datos, dict):
        return {"ok": False, "error": "CONTRATO", "detalle": "El JSON no es un objeto {...}"}

    try:
        extraccion = ExtraccionReclamo(**datos)         # Nivel 2: ¿cumple el contrato?
    except ValidationError as e:
        errores = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        return {"ok": False, "error": "CONTRATO", "detalle": errores}

    return {"ok": True, "extraccion": extraccion.model_dump()}


def aplicar_reglas(extraccion: dict, ufs_vinculadas: list[dict]) -> dict:
    """Paso 5 (segunda parte) — reglas de negocio sobre una extracción que ya cumple el contrato."""
    # Segunda red de seguridad: el LLM detectó una emergencia que el filtro no vio.
    if extraccion["intencion"] == "EMERGENCIA":
        return escalar_emergencia("Detectada por el LLM (el filtro de palabras clave no la vio)")

    # Lo que está fuera de alcance se deriva, y una consulta de reglamento solo lee:
    # ninguna de las dos necesita identificar la unidad (el edificio sale del padrón).
    if extraccion["intencion"] in ("FUERA_DE_ALCANCE", "CONSULTA_REGLAMENTO"):
        return {"ok": True, "etapa": "LISTO", **ACCIONES[extraccion["intencion"]]}

    uf, motivo = resolver_unidad(extraccion, ufs_vinculadas)
    if uf is None:
        return {"ok": False, "error": "REGLA", "detalle": motivo}
    return {"ok": True, "etapa": "LISTO", "uf": uf, **ACCIONES[extraccion["intencion"]]}


def procesar_mensaje(mensaje: str, telefono: str, simulacion: Optional[str] = None,
                     version: str = PROMPT_VERSION) -> dict:
    """
    Flujo completo del componente. Nunca rompe el programa: siempre devuelve un dict
    con "ok" y, si falló, en qué etapa ("error") y por qué ("detalle").
    Si no hay API key en el .env, usa `simulacion` como si fuera la respuesta del modelo.
    """
    # Paso 1 — Entrada basura: no gastamos una llamada al modelo.
    if not isinstance(mensaje, str) or not any(c.isalnum() for c in mensaje):
        return {"ok": False, "error": "REGLA", "detalle": "Mensaje vacío o sin texto"}

    # Paso 3 — Emergencias: se resuelven SIN llamar al LLM.
    patron = detectar_emergencia(mensaje)
    if patron:
        return {"origen": "FILTRO DETERMINISTA (no se llamó al LLM)",
                **escalar_emergencia(f"Coincidió el patrón '{patron}'")}

    # Paso 2 — Remitente: si el teléfono no está en el padrón, se deriva a una persona.
    ufs = identificar_remitente(telefono)
    if not ufs:
        return {"ok": False, "error": "REGLA", "detalle": "Teléfono no registrado en el padrón",
                **ACCIONES["FUERA_DE_ALCANCE"]}

    # Paso 4 — LLM.
    proveedor = detectar_proveedor()
    if proveedor is None:
        origen, texto = "SIMULACIÓN (sin API key en .env)", simulacion or ""
    else:
        nombre, key = proveedor
        origen = f"API REAL — {nombre}"
        try:
            texto = llamar_con_reintentos(cargar_prompt(version), armar_mensaje_usuario(mensaje), nombre, key)
        except urllib.error.HTTPError as e:
            # El proveedor respondió con un error: key inválida, límite de uso, modelo inexistente...
            return {"origen": origen, "ok": False, "error": "COMUNICACION",
                    "detalle": describir_error_http(e)}
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as e:
            # No llegó a responder (sin red, certificado, timeout) o la respuesta vino vacía.
            return {"origen": origen, "ok": False, "error": "COMUNICACION", "detalle": f"{type(e).__name__}: {e}"}

    # Paso 5 — Formato, contrato y reglas.
    resultado = {"origen": origen, "prompt": version, "respuesta_cruda": texto, **validar_respuesta(texto)}
    if not resultado["ok"]:
        return resultado
    return {**resultado, **aplicar_reglas(resultado["extraccion"], ufs)}
