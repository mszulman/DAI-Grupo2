"""
Entrega 2 — Primer prototipo operativo de Administración Ombú (reclamos de mantenimiento)
=========================================================================================
Corre el lote de prueba (datos/lote_prueba.json) contra el modelo y muestra:
  1. El resultado de cada caso.
  2. La tabla del lote, con el formato de la Entrega 2 (Parte C).
  3. Una demostración de errores: qué etapa frena cada respuesta rota.
Además guarda la corrida completa en salidas/ (evidencia para la Parte C).

Uso (desde la carpeta entrega_2/):
    python app.py                       → prompt v1 (few-shot), los 4 casos
    python app.py v0                    → prompt v0 (zero-shot), para comparar
    python app.py v1 --caso 3 --repetir 5   → solo el caso 3, cinco veces
    python app.py --sin-guardar         → no escribe en salidas/
"""

import argparse
import json
import os
import time
from datetime import datetime

from ombu.config import RAIZ_PROYECTO, detectar_proveedor
from ombu.extractor import PROMPT_VERSION, aplicar_reglas, procesar_mensaje, validar_respuesta
from ombu.llm import modelo_configurado
from ombu.reglas import identificar_remitente
from ombu.reporte import cumple_esperado, etapa_de, intencion_de, json_valido

# Pausa entre llamadas reales, para no chocar con el límite por minuto de la capa gratuita.
PAUSA_SEGUNDOS = float(os.getenv("PAUSA_SEGUNDOS", "4"))

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


def correr_lote(version: str, caso: int | None, repetir: int) -> list[dict]:
    lote = json.loads((RAIZ_PROYECTO / "datos" / "lote_prueba.json").read_text(encoding="utf-8"))
    indices = [caso] if caso else range(1, len(lote) + 1)
    api_real = detectar_proveedor() is not None
    registros = []
    for i in indices:
        c = lote[i - 1]
        for corrida in range(1, repetir + 1):
            print(f"\n▶ Caso {i} — {c['tipo']}" + (f" (corrida {corrida}/{repetir})" if repetir > 1 else ""))
            print(f"  Qué observar: {c['observar']}")
            if api_real and registros:
                time.sleep(PAUSA_SEGUNDOS)
            resultado = procesar_mensaje(c["mensaje"], c["telefono"], c["simulacion"], version)
            print(json.dumps({k: v for k, v in resultado.items() if k != "respuesta_cruda"},
                             indent=2, ensure_ascii=False))
            registros.append({"caso": i, "tipo": c["tipo"], "corrida": corrida,
                              "mensaje": c["mensaje"], "esperado": c.get("esperado"), "resultado": resultado})
    return registros


def imprimir_tabla(registros: list[dict]) -> None:
    titulo("TABLA DEL LOTE (formato de la Entrega 2, Parte C)")
    print(f"{'#':<3}{'Corr.':<6}{'Tipo':<14}{'Intención':<24}{'¿JSON válido?':<25}{'Etapa / error':<22}{'¿Esperado?'}")
    for r in registros:
        res = r["resultado"]
        ok = cumple_esperado(res, r.get("esperado"))
        marca = "—" if ok is None else ("Sí" if ok else "NO ⚠️")
        print(f"{r['caso']:<3}{r['corrida']:<6}{r['tipo']:<14}{intencion_de(res):<24}"
              f"{json_valido(res):<25}{etapa_de(res):<22}{marca}")


def guardar(registros: list[dict], version: str) -> None:
    proveedor = detectar_proveedor()
    datos = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "prompt": version,
        "proveedor": proveedor[0] if proveedor else "simulacion",
        "modelo": modelo_configurado(proveedor[0]) if proveedor else "simulacion",
        "registros": registros,
    }
    carpeta = RAIZ_PROYECTO / "salidas"
    carpeta.mkdir(exist_ok=True)
    sufijo = "" if proveedor else "_SIMULACION"
    alcance = f"_caso{registros[0]['caso']}" if len({r['caso'] for r in registros}) == 1 else ""
    repeticiones = max(r["corrida"] for r in registros)
    base = f"lote_{version}{alcance}{f'_x{repeticiones}' if repeticiones > 1 else ''}_{datetime.now():%Y%m%d-%H%M%S}{sufijo}"
    destino = carpeta / f"{base}.json"
    n = 2
    while destino.exists():          # dos corridas en el mismo segundo no se pisan
        destino = carpeta / f"{base}_{n}.json"
        n += 1
    destino.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n💾 Corrida guardada en {destino.relative_to(RAIZ_PROYECTO)}")


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
    parser = argparse.ArgumentParser(description="Corre el lote de prueba de la Entrega 2.")
    parser.add_argument("version", nargs="?", default=PROMPT_VERSION, help="versión del prompt (v0, v1...)")
    parser.add_argument("--caso", type=int, choices=range(1, 5), help="correr solo un caso (1 a 4)")
    parser.add_argument("--repetir", type=int, default=1, help="cuántas veces correr cada caso")
    parser.add_argument("--sin-guardar", action="store_true", help="no guardar la corrida en salidas/")
    args = parser.parse_args()

    titulo(f"ENTREGA 2 — EXTRACCIÓN DE RECLAMOS DE ADMINISTRACIÓN OMBÚ (prompt {args.version})")
    registros = correr_lote(args.version, args.caso, max(1, args.repetir))
    imprimir_tabla(registros)
    if not args.sin_guardar:
        guardar(registros, args.version)
    if not args.caso:
        demostrar_errores()

    if detectar_proveedor() is None:
        print("\n⚠️  MODO SIMULACIÓN: el lote usó respuestas de ejemplo (NO sirven como evidencia de la Parte C).")
        print("    Para usar un LLM real: cp .env.example .env   y completá GEMINI_API_KEY")
