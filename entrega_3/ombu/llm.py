"""
Llamada a la API real del modelo (request → response).

Soporta Gemini (por defecto) y el formato compatible con OpenAI (OpenAI y Groq).
El proveedor y el modelo se eligen por variables de entorno: el resto del
sistema no depende de cuál se use.
"""

import json
import os
import time
import urllib.error
import urllib.request

from .config import SSL_CONTEXT

REINTENTOS = 3
CODIGOS_REINTENTABLES = (429, 503)  # 429: límite de uso · 503: servidor saturado


MODELOS_POR_DEFECTO = {
    "gemini": ("GEMINI_MODEL", "gemini-3.5-flash"),
    "openai": ("OPENAI_MODEL", "gpt-4o-mini"),
    "groq": ("GROQ_MODEL", "llama-3.3-70b-versatile"),
}


def modelo_configurado(proveedor: str) -> str:
    """Nombre del modelo que se va a usar con ese proveedor (variable de entorno o default)."""
    variable, default = MODELOS_POR_DEFECTO[proveedor]
    return os.getenv(variable, default)


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    """Request HTTP POST: manda un JSON y devuelve el JSON de la respuesta."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
    )
    with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _llamar_gemini(system: str, usuario: str, api_key: str, json_mode: bool, temperatura: float) -> str:
    modelo = modelo_configurado("gemini")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": usuario}]}],
        "generationConfig": {"temperature": temperatura,
                             **({"responseMimeType": "application/json"} if json_mode else {})},
    }
    data = _post_json(url, payload, {"x-goog-api-key": api_key})
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _llamar_chat_completions(system: str, usuario: str, api_key: str, url: str, modelo: str,
                             json_mode: bool, temperatura: float) -> str:
    """Formato compatible con OpenAI (sirve para OpenAI y para Groq)."""
    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": usuario},
        ],
        "temperature": temperatura,
        **({"response_format": {"type": "json_object"}} if json_mode else {}),
    }
    data = _post_json(url, payload, {"Authorization": f"Bearer {api_key}"})
    return data["choices"][0]["message"]["content"]


def llamar_modelo(system: str, usuario: str, proveedor: str, api_key: str,
                  json_mode: bool = True, temperatura: float = 0) -> str:
    """
    Una sola llamada. Devuelve el TEXTO crudo del modelo (todavía no es un dict).
    json_mode=True para extraer (paso 4); False para redactar texto libre (paso 9).
    """
    if proveedor == "gemini":
        return _llamar_gemini(system, usuario, api_key, json_mode, temperatura)
    if proveedor == "openai":
        return _llamar_chat_completions(
            system, usuario, api_key,
            "https://api.openai.com/v1/chat/completions",
            modelo_configurado("openai"), json_mode, temperatura,
        )
    if proveedor == "groq":
        return _llamar_chat_completions(
            system, usuario, api_key,
            "https://api.groq.com/openai/v1/chat/completions",
            modelo_configurado("groq"), json_mode, temperatura,
        )
    raise ValueError(f"Proveedor desconocido: {proveedor}")


def llamar_con_reintentos(system: str, usuario: str, proveedor: str, api_key: str,
                          json_mode: bool = True, temperatura: float = 0) -> str:
    """
    Un error de comunicación transitorio (503, 429) se reintenta con espera creciente (2s, 4s).
    Una key inválida (401/403) o un pedido mal armado (400) NO se reintenta: fallaría igual.
    """
    for intento in range(1, REINTENTOS + 1):
        try:
            return llamar_modelo(system, usuario, proveedor, api_key, json_mode, temperatura)
        except urllib.error.HTTPError as e:
            if e.code in CODIGOS_REINTENTABLES and intento < REINTENTOS:
                espera = 2 ** intento
                print(f"  ⏳ HTTP {e.code} (intento {intento}/{REINTENTOS}). Reintento en {espera}s...")
                time.sleep(espera)
                continue
            raise
    raise RuntimeError("No debería llegar acá")
