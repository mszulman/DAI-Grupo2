"""
RAG sobre el reglamento y las políticas de reclamos de Ombú.

    pregunta + edificios del vecino (del padrón)
      │
      ├─ Recuperar: embedding + ChromaDB + filtro (vigente, edificio) ........ [Herramienta: sensor]
      ├─ ✋ ¿algún fragmento supera el umbral?
      │       └─ NO → "No tengo información oficial sobre esa consulta."   (el LLM ni se llama)
      ├─ Generar: prompt de grounding + fragmentos + pregunta ................. [LLM]
      └─ ✋ Validar la respuesta: cita al menos un código, solo códigos del contexto,
              no da nada por aprobado  ..................................... [Regla]
              └─ falla → no se envía: se deriva

Es la misma idea de la Clase 4 (plantilla → modelo → validación) con un paso nuevo adelante:
RECUPERAR el contexto. Sin API key, la generación es una SIMULACIÓN (devuelve el fragmento
recuperado tal cual); la recuperación (embeddings, filtro y umbral) corre de verdad igual.
"""

import re
import urllib.error
from typing import Optional

from .base_conocimiento import K, BaseConocimiento, base_por_defecto, filtro_para
from .config import RAIZ_PROYECTO, detectar_proveedor
from .llm import llamar_con_reintentos
from .reglas import normalizar_texto

SIN_INFORMACION = "No tengo información oficial sobre esa consulta."
LARGO_MAXIMO = 900

PATRON_CITA = re.compile(r"\b(?:POL|REG)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
# Lo que una respuesta del RAG nunca puede decir, aunque "suene" a lo que dice el reglamento.
PATRONES_PROHIBIDOS = [
    r"(?<!no )\b(esta|fue|queda|quedo) (aprobad|confirmad)",
    r"\bte (lo |la )?(reintegramos|devolvemos|descontamos)",
]


def _leer_prompt(nombre: str) -> str:
    return (RAIZ_PROYECTO / "prompts" / f"{nombre}.txt").read_text(encoding="utf-8")


def formatear_contexto(usados: list[dict]) -> str:
    """Cada fragmento con su código para poder citarlo: "[POL-PLAZOS] Plazos de atención: ..."."""
    return "\n".join(f"[{d['codigo']}] {d['titulo']}: {d['texto']}" for d in usados)


def armar_mensaje_usuario(pregunta: str, contexto: str) -> str:
    return (f"Fragmentos del reglamento y de las políticas de Ombú:\n{contexto}\n\n"
            f"Consulta del vecino (entre <consulta> y </consulta>):\n<consulta>\n{pregunta.strip()}\n</consulta>")


def validar_respuesta_rag(texto: str, fuentes: list[str]) -> tuple[bool, str]:
    """
    Segunda capa contra la alucinación (la primera es el umbral): la respuesta tiene que estar
    anclada en lo recuperado. Devuelve (ok, motivo).
    """
    if texto.strip().startswith(SIN_INFORMACION):
        return True, "el modelo dice que el contexto no responde la consulta"
    citas = set(PATRON_CITA.findall(texto))
    if not citas:
        return False, "no cita ninguna regla del contexto"
    ajenas = citas - set(fuentes)
    if ajenas:
        return False, f"cita reglas que no estaban en el contexto: {', '.join(sorted(ajenas))}"
    normalizado = normalizar_texto(texto)
    for patron in PATRONES_PROHIBIDOS:
        if re.search(patron, normalizado):
            return False, f"da algo por aprobado o confirmado (patrón '{patron}')"
    if len(texto) > LARGO_MAXIMO:
        return False, f"demasiado larga ({len(texto)} caracteres)"
    return True, "cita solo reglas recuperadas"


def _simular(usados: list[dict]) -> str:
    """Sin API key: el primer fragmento recuperado, textual y citado. No redacta nada."""
    d = usados[0]
    return f"Según {d['titulo'].lower()} ({d['codigo']}): {d['texto']}"


def responder_consulta(pregunta: str, edificios: Optional[list[str]],
                       base: Optional[BaseConocimiento] = None, k: int = K) -> dict:
    """
    Lo que usa el workflow. Devuelve:
        estado      → RESPONDIDA, SIN_INFORMACION o NO_VALIDADA
        texto       → la respuesta (None si no se puede enviar)
        origen      → quién la escribió, o por qué no se llamó al LLM
        fuentes     → códigos de las reglas que se pasaron como contexto
        candidatos  → los k recuperados con su similitud (para la traza)
    """
    base = base or base_por_defecto()
    candidatos = base.buscar(pregunta, k=k, filtro=filtro_para(edificios))
    usados = [c for c in candidatos if c["supera_umbral"]]
    salida = {"fuentes": list(dict.fromkeys(c["codigo"] for c in usados)),
              "candidatos": [(c["id"], c["similitud"], c["supera_umbral"]) for c in candidatos]}

    # ✋ Punto de control 1 · el umbral: si nada se parece lo suficiente, no hay de dónde responder.
    if not usados:
        return {**salida, "estado": "SIN_INFORMACION", "texto": SIN_INFORMACION,
                "origen": f"ningún fragmento supera el umbral ({base.umbral}): no se llama al LLM"}

    proveedor = detectar_proveedor()
    if proveedor is None:
        texto, origen = _simular(usados), "SIMULACIÓN (sin API key): fragmento recuperado, textual"
    else:
        nombre, key = proveedor
        try:
            texto = llamar_con_reintentos(_leer_prompt("rag_v1"),
                                          armar_mensaje_usuario(pregunta, formatear_contexto(usados)),
                                          nombre, key, json_mode=False, temperatura=0).strip()
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as e:
            return {**salida, "estado": "NO_VALIDADA", "texto": None, "origen": f"falló el LLM ({type(e).__name__})"}
        origen = f"LLM ({nombre})"

    # ✋ Punto de control 2 · la respuesta tiene que estar anclada en lo recuperado.
    ok, motivo = validar_respuesta_rag(texto, salida["fuentes"])
    if not ok:
        return {**salida, "estado": "NO_VALIDADA", "texto": None, "texto_rechazado": texto,
                "origen": f"{origen} · rechazada: {motivo}"}
    if texto.startswith(SIN_INFORMACION):
        return {**salida, "estado": "SIN_INFORMACION", "texto": SIN_INFORMACION,
                "origen": f"{origen} · el contexto recuperado no responde la consulta"}
    return {**salida, "estado": "RESPONDIDA", "texto": texto, "origen": origen}


def responder_sin_grounding(pregunta: str) -> Optional[dict]:
    """
    La misma pregunta SIN contexto, como en las Entregas 1 y 2: para la comparación de B.3.
    Sin API key devuelve None: no hay forma honesta de mostrar qué inventaría un modelo.
    """
    proveedor = detectar_proveedor()
    if proveedor is None:
        return None
    nombre, key = proveedor
    try:
        texto = llamar_con_reintentos(_leer_prompt("sin_grounding_v1"), pregunta.strip(), nombre, key,
                                      json_mode=False, temperatura=0)
        return {"texto": texto.strip(), "origen": f"LLM ({nombre}), sin contexto"}
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError) as e:
        return {"texto": None, "origen": f"falló el LLM ({type(e).__name__})"}
