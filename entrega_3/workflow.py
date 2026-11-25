"""
Entrega 3 · Parte A — Workflow de reclamos de Administración Ombú
=================================================================
Corre el lote (datos/lote_workflow.json) por el workflow (ombu/workflow.py) y muestra:
  1. La TRAZA de cada caso: qué pasos recorrió y dónde se detuvo.
  2. La respuesta que recibiría el vecino.
  3. La tabla del lote: estado obtenido vs. estado esperado (prueba de falla controlada, A.3).
Además guarda la corrida completa en salidas/ (evidencia para el informe).

Uso (desde la carpeta entrega_3/):
    python workflow.py               → los 10 casos
    python workflow.py --caso 5      → solo un caso
    python workflow.py --sin-guardar → no escribe en salidas/
"""

import argparse
import json
import os
import time
from datetime import datetime

from ombu.config import RAIZ_PROYECTO, detectar_proveedor
from ombu.llm import modelo_configurado
from ombu.registro import RegistroReclamos
from ombu.workflow import workflow_reclamo

ICONOS = {"LLM": "🤖", "Regla": "📏", "Herramienta": "🔧", "Humano": "🙋", "LLM + Regla": "🤖📏"}
PAUSA_SEGUNDOS = float(os.getenv("PAUSA_SEGUNDOS", "4"))   # para no chocar con el límite por minuto


def titulo(texto: str) -> None:
    print("\n" + "=" * 78 + f"\n{texto}\n" + "=" * 78)


def mostrar(resultado: dict) -> None:
    for p in resultado["traza"]:
        print(f"  {ICONOS.get(p['tipo'], '  ')} [{p['paso']:>2}] {p['nombre']:<44} {p['resultado']}")
    print(f"\n  ➜ Estado final: {resultado['estado']}")
    if "motivo" in resultado:
        print(f"    Motivo: {resultado['motivo']}")
    print(f"\n  ✉️  Respuesta al vecino [{resultado['respuesta']['origen']}]:")
    for linea in resultado["respuesta"]["texto"].splitlines():
        print(f"     {linea}")


def correr_lote(caso: int | None) -> list[dict]:
    lote = json.loads((RAIZ_PROYECTO / "datos" / "lote_workflow.json").read_text(encoding="utf-8"))
    api_real = detectar_proveedor() is not None
    registros = []
    for i, c in enumerate(lote, start=1):
        if caso and i != caso:
            continue
        titulo(f"Caso {i} — {c['tipo']}")
        print(f"  Mensaje: {c['mensaje']}")
        print(f"  Qué observar: {c['observar']}\n")
        if api_real and registros:
            time.sleep(PAUSA_SEGUNDOS)
        # Un registro nuevo por caso: cada caso arranca del mismo estado (datos/reclamos.json).
        resultado = workflow_reclamo(c["mensaje"], c["telefono"], RegistroReclamos.desde_archivo(), c["simulacion"])
        mostrar(resultado)
        registros.append({"caso": i, "tipo": c["tipo"], "mensaje": c["mensaje"],
                          "estado_esperado": c["estado_esperado"], "resultado": resultado})
    return registros


def imprimir_tabla(registros: list[dict]) -> None:
    titulo("TABLA DEL LOTE — ¿el workflow se detuvo donde tenía que detenerse?")
    print(f"{'#':<4}{'Caso':<26}{'Esperado':<26}{'Obtenido':<26}")
    for r in registros:
        obtenido = r["resultado"]["estado"]
        marca = "✅" if obtenido == r["estado_esperado"] else "❌"
        print(f"{r['caso']:<4}{r['tipo']:<26}{r['estado_esperado']:<26}{obtenido:<24}{marca}")


def guardar(registros: list[dict]) -> None:
    proveedor = detectar_proveedor()
    datos = {"fecha": datetime.now().isoformat(timespec="seconds"),
             "proveedor": proveedor[0] if proveedor else "simulacion",
             "modelo": modelo_configurado(proveedor[0]) if proveedor else "simulacion",
             "registros": registros}
    carpeta = RAIZ_PROYECTO / "salidas"
    carpeta.mkdir(exist_ok=True)
    destino = carpeta / f"workflow_{datetime.now():%Y%m%d-%H%M%S}{'' if proveedor else '_SIMULACION'}.json"
    destino.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n💾 Corrida guardada en {destino.relative_to(RAIZ_PROYECTO)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corre el lote del workflow de la Entrega 3.")
    parser.add_argument("--caso", type=int, help="correr solo un caso (1 a 10)")
    parser.add_argument("--sin-guardar", action="store_true", help="no guardar la corrida en salidas/")
    args = parser.parse_args()

    titulo("ENTREGA 3 · PARTE A — WORKFLOW DE RECLAMOS DE ADMINISTRACIÓN OMBÚ")
    registros = correr_lote(args.caso)
    imprimir_tabla(registros)
    if not args.sin_guardar:
        guardar(registros)
    if detectar_proveedor() is None:
        print("\n⚠️  MODO SIMULACIÓN: la extracción usó respuestas de ejemplo y la redacción, la plantilla fija.")
        print("    Para usar un LLM real: cp .env.example .env   y completá GEMINI_API_KEY")
