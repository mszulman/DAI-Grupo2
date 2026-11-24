"""
Entrega 2 — Primer prototipo operativo de Administración Ombú (reclamos de mantenimiento)
=========================================================================================
Corre el lote de prueba (datos/lote_prueba.json) contra el modelo y muestra:
  1. El resultado de cada caso.
  2. La tabla del lote, con el formato de la Entrega 2 (Parte C).
  3. Una demostración de errores: qué etapa frena cada respuesta rota.

Uso (desde la carpeta entrega_2/):
    python app.py             → prompt v1 (few-shot)
    python app.py v0          → prompt v0 (zero-shot), para comparar
"""

import json
import sys

from ombu.config import RAIZ_PROYECTO, detectar_proveedor
from ombu.extractor import PROMPT_VERSION, aplicar_reglas, procesar_mensaje, validar_respuesta
from ombu.reglas import identificar_remitente

# Respuestas rotas típicas de un LLM, para ver qué etapa frena cada una (no requiere API).
TELEFONO_DEMO = "+54 9 11 5555-0101"   # vecino del 4B de Tipas 1450
RESPUESTAS_ROTAS = [
    ("Texto antes del JSON", '¡Listo! Acá va: {"intencion": "NUEVO_RECLAMO"}'),
    ("Bloque de código Markdown", '```json\n{"intencion": "NUEVO_RECLAMO"}\n```'),
    ("Intención inventada", '{"intencion": "APROBAR_REINTEGRO", "unidad_mencionada": "4B"}'),
    ("Campo que no existe en el contrato",
     '{"intencion": "SOLICITUD_REINTEGRO", "reintegro_aprobado": true}'),
    ("Unidad sin normalizar y rubro fuera de la lista",
     '{"intencion": "NUEVO_RECLAMO", "unidad_mencionada": "4°B", "rubro": "plomeria"}'),
    ("Formato perfecto, unidad de otro vecino",
     '{"intencion": "ESTADO_RECLAMO", "edificio_mencionado": "Tipas 1450", "unidad_mencionada": "7A"}'),
]


def titulo(texto: str) -> None:
    print("\n" + "=" * 78 + f"\n{texto}\n" + "=" * 78)


def correr_lote(version: str) -> list[tuple[int, str, dict]]:
    lote = json.loads((RAIZ_PROYECTO / "datos" / "lote_prueba.json").read_text(encoding="utf-8"))
    resultados = []
    for i, caso in enumerate(lote, start=1):
        print(f"\n▶ Caso {i} — {caso['tipo']}")
        print(f"  Qué observar: {caso['observar']}")
        resultado = procesar_mensaje(caso["mensaje"], caso["telefono"], caso["simulacion"], version)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        resultados.append((i, caso["tipo"], resultado))
    return resultados


def imprimir_tabla(resultados: list[tuple[int, str, dict]]) -> None:
    titulo("TABLA DEL LOTE (formato de la Entrega 2, Parte C)")
    print(f"{'#':<3}{'Tipo':<14}{'Intención':<22}{'¿JSON válido?':<15}{'Etapa / error'}")
    for i, tipo, r in resultados:
        intencion = r.get("extraccion", {}).get("intencion", "— (no se llamó al LLM)" if "extraccion" not in r
                                                and r.get("etapa") == "EMERGENCIA_ESCALADA" else "—")
        if r.get("error") in ("FORMATO", "COMUNICACION"):
            json_ok = "No"
        elif "extraccion" in r:
            json_ok = "Sí"
        else:
            json_ok = "—"
        etapa = r.get("error") or r.get("etapa", "—")
        print(f"{i:<3}{tipo:<14}{intencion:<22}{json_ok:<15}{etapa}")


def demostrar_errores() -> None:
    titulo("DEMOSTRACIÓN DE ERRORES — ¿qué etapa frena cada respuesta rota?")
    ufs = identificar_remitente(TELEFONO_DEMO)
    for descripcion, texto in RESPUESTAS_ROTAS:
        r = validar_respuesta(texto)
        if r["ok"]:
            r = aplicar_reglas(r["extraccion"], ufs)
        print(f"\n▶ {descripcion}")
        print(f"  Respuesta: {texto!r}")
        print(f"  Resultado: {r.get('error', 'OK')} → {r.get('detalle', r.get('accion', ''))}")

    print("\n▶ Entrada basura (mensaje vacío)")
    r = procesar_mensaje("   ¿¿??   ", TELEFONO_DEMO)
    print(f"  Resultado: {r.get('error', 'OK')} → {r.get('detalle', '')}")


if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else PROMPT_VERSION
    titulo(f"ENTREGA 2 — EXTRACCIÓN DE RECLAMOS DE ADMINISTRACIÓN OMBÚ (prompt {version})")
    imprimir_tabla(correr_lote(version))
    demostrar_errores()

    if detectar_proveedor() is None:
        print("\n⚠️  MODO SIMULACIÓN: el lote usó respuestas de ejemplo. Para usar un LLM real:")
        print("    cp .env.example .env   y completá GEMINI_API_KEY (gratis en https://aistudio.google.com)")
