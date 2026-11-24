"""
Helpers para resumir resultados del lote (los usan app.py y exportar_resultados.py).
No deciden nada del negocio: solo traducen un resultado a las columnas de la tabla.
"""

from typing import Optional


def intencion_de(resultado: dict) -> str:
    extraccion = resultado.get("extraccion") or {}
    if extraccion:
        return extraccion["intencion"]
    if "respuesta_cruda" not in resultado and resultado.get("etapa") == "EMERGENCIA_ESCALADA":
        return "— (no se llamó al LLM)"
    return "—"


def json_valido(resultado: dict) -> str:
    error = resultado.get("error")
    if error == "FORMATO":
        return "No"
    if error == "COMUNICACION":
        return "— (no respondió)"
    if error == "CONTRATO":
        return "Sí (no cumple contrato)"
    if resultado.get("extraccion"):
        return "Sí"
    return "—"


def etapa_de(resultado: dict) -> str:
    return resultado.get("error") or resultado.get("etapa", "—")


def cumple_esperado(resultado: dict, esperado: Optional[dict]) -> Optional[bool]:
    """¿La intención y la etapa son las que define la Matriz para ese caso? None si no hay esperado."""
    if not esperado:
        return None
    if etapa_de(resultado) != esperado["etapa"]:
        return False
    extraccion = resultado.get("extraccion") or {}
    # Si lo frenó el filtro de emergencias antes del LLM, no hay intención que comparar.
    return not extraccion or extraccion["intencion"] == esperado["intencion"]
