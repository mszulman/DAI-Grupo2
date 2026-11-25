"""
Pasos 9 y 10 del journey: el LLM redacta la respuesta al vecino y el código la valida.

Es el camino inverso al paso 4:
    paso 4 : lenguaje natural      → datos estructurados   (el LLM extrae)
    paso 9 : resultado estructurado → lenguaje natural      (el LLM redacta)

El LLM COMUNICA el resultado, no lo decide: recibe un JSON con lo que ya resolvieron las
reglas y el registro, y solo le pone palabras. Después, el paso 10 (validar_salida, en
reglas.py) controla que no haya inventado números de reclamo, fechas, montos ni aprobaciones.

Si no hay API key, si la API falla o si la redacción no pasa la validación, se usa una
PLANTILLA FIJA: el resultado ya está resuelto y se puede comunicar igual.
"""

import json
import urllib.error

from .config import RAIZ_PROYECTO, detectar_proveedor
from .llm import llamar_con_reintentos
from .reglas import validar_salida

PROMPT_REDACCION = "redaccion_v1"

ESTADOS_LEGIBLES = {"ABIERTO": "abierto, todavía sin asignar", "EN_CURSO": "en curso",
                    "RESUELTO": "resuelto"}


def plantilla_fija(resultado: dict) -> str:
    """Respuesta determinista: la usa el sistema cuando no puede (o no debe) usar la del LLM."""
    tipo, numero = resultado["tipo"], resultado.get("numero_reclamo")
    if tipo == "RECLAMO_REGISTRADO":
        return (f"Registramos tu reclamo N° {numero}: {resultado.get('descripcion', 'sin descripción')}. "
                "Te vamos a avisar por este medio cuando haya novedades.")
    if tipo == "AVISO_SUMADO":
        return (f"Ya teníamos un reclamo abierto por ese problema (reclamo N° {numero}) y sumamos tu aviso. "
                "Te avisamos por este medio cuando haya novedades.")
    if tipo == "RECLAMO_AMPLIADO":
        return f"Agregamos lo que nos contaste a tu reclamo N° {numero}. Gracias por avisarnos."
    if tipo == "ESTADO_INFORMADO":
        estado = ESTADOS_LEGIBLES.get(resultado.get("estado_reclamo"), resultado.get("estado_reclamo"))
        return f"Tu reclamo N° {numero} está {estado}. Te avisamos por este medio cuando haya novedades."
    if tipo == "SIN_RECLAMO":
        return ("No encontramos un reclamo por ese problema. Si querés, contanos qué pasa y en qué lugar "
                "del edificio, y lo registramos.")
    if tipo == "REINTEGRO_EN_EVALUACION":
        return ("Registramos tu pedido de reintegro. La administración lo va a evaluar y te va a responder "
                "por este medio; hasta entonces no hay ningún reintegro confirmado.")
    if tipo == "PEDIR_ACLARACION":
        opciones = "\n".join(f"  - {o}" for o in resultado.get("opciones", []))
        return f"Tenés más de una unidad registrada. ¿A cuál te referís?\n{opciones}"
    raise ValueError(f"Tipo de resultado desconocido: {tipo}")


def redactar_respuesta(resultado: dict) -> dict:
    """Devuelve {"texto": ..., "origen": "LLM (...)" | "PLANTILLA (...)"}."""
    proveedor = detectar_proveedor()
    if proveedor is None:
        return {"texto": plantilla_fija(resultado), "origen": "PLANTILLA (sin API key)"}

    nombre, key = proveedor
    system = (RAIZ_PROYECTO / "prompts" / f"{PROMPT_REDACCION}.txt").read_text(encoding="utf-8")
    usuario = f"<resultado>\n{json.dumps(resultado, ensure_ascii=False, indent=2)}\n</resultado>"
    try:
        texto = llamar_con_reintentos(system, usuario, nombre, key, json_mode=False, temperatura=0.3).strip()
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as e:
        return {"texto": plantilla_fija(resultado), "origen": f"PLANTILLA (falló la API: {type(e).__name__})"}

    # Paso 10 — validar la salida antes de mandarla
    ok, motivo = validar_salida(texto, resultado)
    if not ok:
        return {"texto": plantilla_fija(resultado), "origen": f"PLANTILLA (la redacción del LLM no pasó la validación: {motivo})",
                "texto_rechazado": texto}
    return {"texto": texto, "origen": f"LLM ({nombre})"}
