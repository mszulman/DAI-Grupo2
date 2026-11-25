"""
Entrega 3 · Parte B — RAG sobre el reglamento y las políticas de reclamos de Ombú
=================================================================================
Uso (desde la carpeta entrega_3/):

    python rag.py indexar                                  → paso OFFLINE: corpus → embeddings → ChromaDB
    python rag.py ver                                      → qué quedó guardado en ChromaDB
    python rag.py buscar "¿Puedo hacer venir al albañil un sábado?" --edificio CEI0880
    python rag.py buscar "..." --todas                     → sin filtro: aparecen las versiones reemplazadas
                                                             y los reglamentos de otros edificios
    python rag.py preguntar "..." --edificio TIP1450       → RAG completo: recuperar + responder
    python rag.py calibrar                                 → similitudes de preguntas dentro y fuera del corpus
    python rag.py comparar                                 → B.3: sin grounding vs. con RAG (necesita API key)

La búsqueda usa embeddings locales (sin API key). La primera vez se descarga el modelo (~640 MB).
`calibrar` y `comparar` guardan la corrida en salidas/ (evidencia para el informe).
"""

import argparse
import json
import os
import time
from datetime import datetime

from ombu.base_conocimiento import K, base_por_defecto, filtro_para
from ombu.config import RAIZ_PROYECTO, detectar_proveedor
from ombu.llm import modelo_configurado
from ombu.rag import responder_consulta, responder_sin_grounding

PAUSA_SEGUNDOS = float(os.getenv("PAUSA_SEGUNDOS", "4"))
EDIFICIOS = ("TIP1450", "CEI0880")


def titulo(texto: str) -> None:
    print("\n" + "=" * 78 + f"\n{texto}\n" + "=" * 78)


def mostrar_candidatos(candidatos: list[dict], umbral: float) -> None:
    for c in candidatos:
        marca = "✅" if c["supera_umbral"] else "✗ "
        estado = "" if c["vigente"] else "  ⚠️ REEMPLAZADA"
        print(f"  {marca} {c['similitud']:.2f}  {c['id']:<20} [{c['edificio']:<7}] {c['titulo']}{estado}")
    print(f"  (umbral {umbral}: ✅ se usa como contexto · ✗ se descarta)")


def guardar(nombre: str, datos: dict, simulacion: bool = False) -> None:
    carpeta = RAIZ_PROYECTO / "salidas"
    carpeta.mkdir(exist_ok=True)
    destino = carpeta / f"{nombre}_{datetime.now():%Y%m%d-%H%M%S}{'_SIMULACION' if simulacion else ''}.json"
    destino.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n💾 Corrida guardada en {destino.relative_to(RAIZ_PROYECTO)}")


def datos_corrida() -> dict:
    proveedor = detectar_proveedor()
    base = base_por_defecto()
    return {"fecha": datetime.now().isoformat(timespec="seconds"),
            "proveedor": proveedor[0] if proveedor else "simulacion",
            "modelo": modelo_configurado(proveedor[0]) if proveedor else "simulacion",
            "embeddings": base.embeddings.nombre, "umbral": base.umbral, "k": K}


# ── Comandos ────────────────────────────────────────────────────────────────

def cmd_indexar(_args) -> None:
    base = base_por_defecto()
    print(f"✅ {base.indexar()} documentos indexados en indice_chroma/ con {base.embeddings.nombre}")


def cmd_ver(_args) -> None:
    docs = base_por_defecto().documentos()
    titulo(f"COLECCIÓN reglamento_ombu · {len(docs)} documentos")
    for d in sorted(docs, key=lambda x: x["id"]):
        print(f"\n🆔 {d['id']}  ·  {d['titulo']}")
        print(f"   metadatos: edificio={d['edificio']} vigente={d['vigente']} tema={d['tema']} "
              f"tipo={d['tipo']} versión={d['version']}")
        print(f"   texto:     {d['texto'][:100]}…")


def cmd_buscar(args) -> None:
    base = base_por_defecto()
    filtro = None if args.todas else filtro_para(args.edificio)
    titulo(f"BUSCAR: {args.pregunta}")
    print(f"  Filtro: {filtro or 'ninguno (--todas)'}\n")
    mostrar_candidatos(base.buscar(args.pregunta, filtro=filtro), base.umbral)


def cmd_preguntar(args) -> None:
    titulo(f"PREGUNTAR: {args.pregunta}")
    r = responder_consulta(args.pregunta, args.edificio)
    print(f"  Recuperó: {'  '.join(f'{i} {s:.2f}{chr(9989) if ok else chr(10007)}' for i, s, ok in r['candidatos'])}")
    print(f"  Estado:   {r['estado']}  ·  {r['origen']}")
    print(f"\n  ✉️  {r['texto'] or '(no se envía: ' + r.get('texto_rechazado', '')[:200] + ')'}")


def cmd_calibrar(_args) -> None:
    """Similitud del documento correcto (preguntas del corpus) vs. del mejor candidato (preguntas de afuera)."""
    base = base_por_defecto()
    preguntas = json.loads((RAIZ_PROYECTO / "datos" / "preguntas_calibracion.json").read_text(encoding="utf-8"))
    titulo(f"CALIBRAR EL UMBRAL · {base.embeddings.nombre} · umbral actual {base.umbral}")
    filas, dentro, fuera = [], [], []
    for p in preguntas:
        candidatos = base.buscar(p["pregunta"], filtro=filtro_para([p["edificio"]]))
        mejor = candidatos[0] if candidatos else None
        if p["esperado"]:
            hallado = next((c for c in candidatos if c["codigo"] == p["esperado"]), None)
            sim = hallado["similitud"] if hallado else None
            if sim is not None:
                dentro.append(sim)
            acierto = bool(mejor and mejor["codigo"] == p["esperado"])
            print(f"  {'✅' if acierto else '❌'} {p['pregunta'][:58]:<58} esperado {p['esperado']:<16} "
                  f"{'no está en el top ' + str(K) if sim is None else f'{sim:.2f}'}   (1° {mejor['id']} {mejor['similitud']:.2f})")
        else:
            sim, acierto = mejor["similitud"], None
            fuera.append(sim)
            print(f"  ⬜ {p['pregunta'][:58]:<58} FUERA DEL CORPUS          1° {mejor['id']} {sim:.2f}")
        filas.append({**p, "similitud_esperado_o_mejor": sim, "primero": mejor["id"], "acierto_top1": acierto,
                      "candidatos": [(c["id"], c["similitud"]) for c in candidatos]})

    minimo_dentro, maximo_fuera = (min(dentro) if dentro else None), max(fuera)
    print(f"\n  Preguntas del corpus:  el documento correcto saca {minimo_dentro} como mínimo")
    print(f"  Preguntas de afuera:   el mejor candidato saca {maximo_fuera} como máximo")
    if minimo_dentro is not None and minimo_dentro > maximo_fuera:
        sugerido = round((minimo_dentro + maximo_fuera) / 2, 2)
        print(f"  ➜ Se separan bien. Umbral sugerido (punto medio): {sugerido}")
    else:
        sugerido = None
        print("  ➜ Se superponen: ningún umbral separa todo. Hay que mejorar las descripciones del corpus "
              "o aceptar el error y que lo frene la segunda capa (el prompt y la validación de citas).")
    guardar("rag_calibracion", {**datos_corrida(), "minimo_dentro": minimo_dentro, "maximo_fuera": maximo_fuera,
                                "umbral_sugerido": sugerido, "preguntas": filas})


def cmd_comparar(_args) -> None:
    """B.3 — la misma pregunta sin contexto y con RAG."""
    preguntas = json.loads((RAIZ_PROYECTO / "datos" / "preguntas_comparacion.json").read_text(encoding="utf-8"))
    api_real = detectar_proveedor() is not None
    titulo("B.3 — SIN GROUNDING vs. CON RAG")
    if not api_real:
        print("⚠️  Sin API key: no se puede mostrar qué respondería el modelo sin contexto, y la columna "
              "'con RAG' muestra el fragmento recuperado. La recuperación sí es real.")
    filas = []
    for i, p in enumerate(preguntas, start=1):
        if api_real and i > 1:
            time.sleep(PAUSA_SEGUNDOS)
        titulo(f"{i}. {p['pregunta']}  (edificio {p['edificio']})")
        print(f"  Qué mirar: {p['que_mirar']}")
        sin = responder_sin_grounding(p["pregunta"])
        if api_real:
            time.sleep(PAUSA_SEGUNDOS)
        con = responder_consulta(p["pregunta"], [p["edificio"]])
        print(f"\n  ❌ SIN GROUNDING [{sin['origen'] if sin else 'no disponible sin API key'}]")
        print(f"     {sin['texto'] if sin else '—'}")
        print(f"\n  📚 CON RAG [{con['origen']}]")
        print(f"     Recuperó: {', '.join(f'{c} {s:.2f}' for c, s, ok in con['candidatos'] if ok) or 'nada sobre el umbral'}")
        print(f"     {con['texto'] or '(no se envía: ' + con.get('texto_rechazado', '')[:200] + ')'}")
        filas.append({**p, "sin_grounding": sin, "con_rag": con})
    guardar("rag_comparacion", {**datos_corrida(), "preguntas": filas}, simulacion=not api_real)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG de la Entrega 3 (Parte B).")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("indexar", help="paso offline: corpus → ChromaDB").set_defaults(f=cmd_indexar)
    sub.add_parser("ver", help="mostrar los documentos guardados").set_defaults(f=cmd_ver)
    for nombre, funcion in (("buscar", cmd_buscar), ("preguntar", cmd_preguntar)):
        p = sub.add_parser(nombre)
        p.add_argument("pregunta")
        p.add_argument("--edificio", nargs="+", choices=EDIFICIOS, default=None,
                       help="edificio(s) del vecino; sin esto se filtra solo por vigencia")
        if nombre == "buscar":
            p.add_argument("--todas", action="store_true", help="sin ningún filtro (demo del filtrado híbrido)")
        p.set_defaults(f=funcion)
    sub.add_parser("calibrar", help="medir similitudes para elegir el umbral").set_defaults(f=cmd_calibrar)
    sub.add_parser("comparar", help="B.3: sin grounding vs. con RAG").set_defaults(f=cmd_comparar)
    args = parser.parse_args()
    args.f(args)
