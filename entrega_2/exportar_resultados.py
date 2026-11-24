"""
Arma un BORRADOR de resultados_lote.md a partir de las corridas guardadas en salidas/.

Toma solo datos reales de las corridas (lo que devolvió el modelo): no escribe
análisis ni conclusiones. Esas partes quedan marcadas para completar a mano.

Uso (desde la carpeta entrega_2/):
    python exportar_resultados.py --salida resultados_lote.md      → todas las corridas de salidas/
    python exportar_resultados.py --modelo gemini-3.5-flash --salida resultados_lote.md
    python exportar_resultados.py salidas/lote_v1_*.json salidas/lote_v0_*.json
(Los comodines * funcionan también en Windows/PowerShell: los expande el script.)

Por defecto escribe salidas/resultados_lote_borrador.md (no pisa el archivo final).
Ignora las corridas en modo simulación, salvo con --permitir-simulacion (solo para probar).
"""

import argparse
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ombu.config import RAIZ_PROYECTO
from ombu.reporte import cumple_esperado, etapa_de, intencion_de, json_valido


def resumir_extraccion(resultado: dict) -> str:
    ex = resultado.get("extraccion")
    if not ex:
        if resultado.get("error") in ("FORMATO", "CONTRATO", "COMUNICACION"):
            return f"`{resultado['error']}`: {resultado.get('detalle')}"
        return resultado.get("motivo") or resultado.get("detalle") or "—"
    partes = [f"`{ex['intencion']}`"]
    for campo, etiqueta in (("edificio_mencionado", "edificio"), ("unidad_mencionada", "unidad"),
                            ("rubro", "rubro"), ("ubicacion", "ubicación"),
                            ("numero_reclamo_mencionado", "reclamo N°")):
        partes.append(f"{etiqueta} `{ex[campo]}`" if ex.get(campo) is not None else f"{etiqueta} `null`")
    return ", ".join(partes)


def celda(texto: str) -> str:
    return str(texto).replace("|", "\\|").replace("\n", " ")


def expandir(patrones: list[str]) -> list[str]:
    """Expande comodines (* ?) acá mismo: PowerShell no lo hace y pasa el texto literal."""
    archivos = []
    for patron in patrones or [str(RAIZ_PROYECTO / "salidas" / "lote_*.json")]:
        encontrados = sorted(glob.glob(patron)) if glob.has_magic(patron) else [patron]
        if not encontrados:
            print(f"⚠️  Ningún archivo coincide con {patron}")
        archivos += [a for a in encontrados if Path(a).is_file() or print(f"⚠️  No existe {a}")]
    return list(dict.fromkeys(archivos))


def cargar(archivos: list[str], permitir_simulacion: bool, modelo: str | None = None) -> dict[str, list[dict]]:
    """Agrupa las corridas por versión del prompt: {"v1": [corrida, ...], "v0": [...]}."""
    por_version = defaultdict(list)
    for a in expandir(archivos):
        datos = json.loads(Path(a).read_text(encoding="utf-8"))
        if datos["proveedor"] == "simulacion" and not permitir_simulacion:
            print(f"⚠️  Ignoro {a}: es una corrida en modo simulación (no sirve como evidencia).")
            continue
        if modelo and datos["modelo"] != modelo:
            print(f"ℹ️  Ignoro {a}: es del modelo {datos['modelo']} (filtro --modelo {modelo}).")
            continue
        datos["archivo"] = Path(a).name
        por_version[datos["prompt"]].append(datos)
    return por_version


def registros_por_caso(corridas: list[dict]) -> dict[int, list[dict]]:
    casos = defaultdict(list)
    for c in corridas:
        for r in c["registros"]:
            casos[r["caso"]].append(r)
    return dict(sorted(casos.items()))


def tabla_c1(casos: dict[int, list[dict]]) -> list[str]:
    lineas = [
        "| # | Input (resumido) | Salida del modelo | ¿JSON válido? | Tipo de error si falló | ¿Coincide con la Matriz? |",
        "|---|---|---|---|---|---|",
    ]
    for n, regs in casos.items():
        primero = regs[0]
        res = primero["resultado"]
        entrada = f"**{primero['tipo']}.** \"{primero['mensaje'][:110]}{'…' if len(primero['mensaje']) > 110 else ''}\""
        salida = resumir_extraccion(res)
        if len(regs) > 1:
            dist = Counter(intencion_de(r["resultado"]) for r in regs)
            salida = (f"**Varía entre {len(regs)} corridas:** "
                      + ", ".join(f"`{k}` en {v} de {len(regs)}" for k, v in dist.most_common())
                      + f". Primera corrida: {salida}")
        error = res.get("error") or "Ninguno"
        if res.get("error") == "REGLA" or res.get("etapa") == "EMERGENCIA_ESCALADA":
            error = f"{etapa_de(res)} — {res.get('detalle') or res.get('motivo', '')}"
        oks = [cumple_esperado(r["resultado"], r.get("esperado")) for r in regs]
        coincide = f"{sum(bool(o) for o in oks)} de {len(oks)}" if len(oks) > 1 else ("Sí" if oks[0] else "**No**")
        lineas.append(f"| {n} | {celda(entrada)} | {celda(salida)} | {json_valido(res)} | {celda(error)} | {coincide} |")
    return lineas


def comparacion(v0: dict[int, list[dict]], v1: dict[int, list[dict]]) -> list[str]:
    lineas = ["| # | Tipo | v0 (zero-shot) | v1 (few-shot) | ¿Diferencia? |", "|---|---|---|---|---|"]
    for n in sorted(set(v0) | set(v1)):
        def desc(regs):
            if not regs:
                return "—"
            dist = Counter(f"{intencion_de(r['resultado'])} / {etapa_de(r['resultado'])}" for r in regs)
            return "; ".join(f"{k} ({v}/{len(regs)})" if len(regs) > 1 else k for k, v in dist.items())
        a, b = desc(v0.get(n, [])), desc(v1.get(n, []))
        tipo = (v0.get(n) or v1.get(n))[0]["tipo"]
        resultados = lambda regs: {f"{intencion_de(r['resultado'])}/{etapa_de(r['resultado'])}" for r in regs}
        if not v0.get(n) or not v1.get(n):
            dif = "—"
        else:
            dif = "No" if resultados(v0[n]) == resultados(v1[n]) else "Sí"
        lineas.append(f"| {n} | {tipo} | {celda(a)} | {celda(b)} | {dif} |")
    return lineas


def evidencia(version: str, casos: dict[int, list[dict]]) -> list[str]:
    lineas = [f"### Respuestas crudas — prompt {version}", ""]
    for n, regs in casos.items():
        for r in regs:
            cruda = r["resultado"].get("respuesta_cruda")
            corrida = f" (corrida {r['corrida']})" if len(regs) > 1 else ""
            lineas.append(f"**Caso {n} — {r['tipo']}{corrida}:**")
            lineas += ["", "```json", cruda, "```", ""] if cruda else ["", f"_No se llamó al modelo: {etapa_de(r['resultado'])}._", ""]
    return lineas


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("archivos", nargs="*", help="corridas de app.py (por defecto: salidas/lote_*.json)")
    p.add_argument("--salida", default=str(RAIZ_PROYECTO / "salidas" / "resultados_lote_borrador.md"))
    p.add_argument("--permitir-simulacion", action="store_true")
    p.add_argument("--modelo", help="usar solo las corridas de este modelo (ej. gemini-3.5-flash)")
    args = p.parse_args()

    por_version = cargar(args.archivos, args.permitir_simulacion, args.modelo)
    if not por_version:
        sys.exit("No hay corridas reales para exportar. Corré app.py con la GEMINI_API_KEY en el .env.")

    principal = "v1" if "v1" in por_version else sorted(por_version)[-1]
    md = ["# Entrega 2 — Resultados del lote de prueba", ""]
    if any(c["proveedor"] == "simulacion" for cs in por_version.values() for c in cs):
        md += ["> ⚠️ **BORRADOR CON CORRIDAS SIMULADAS — no entregar.**", ""]

    md += ["## Corridas", "", "| Archivo | Fecha | Prompt | Modelo | Casos | Errores de comunicación |", "|---|---|---|---|---|---|"]
    for version, corridas in sorted(por_version.items()):
        for c in corridas:
            com = sum(r["resultado"].get("error") == "COMUNICACION" for r in c["registros"])
            md.append(f"| `{c['archivo']}` | {c['fecha']} | {version} | {c['proveedor']} `{c['modelo']}` | "
                      f"{len(c['registros'])} | {com} |")
    md += ["", "Temperatura 0 en todas las corridas.", ""]

    casos_principal = registros_por_caso(por_version[principal])
    md += [f"## C.1 — Tabla del lote (prompt {principal})", ""] + tabla_c1(casos_principal) + [""]
    md += ["**Errores de comunicación observados:** _[completar: 503/429 que aparecieron en consola y si los reintentos los resolvieron]_", ""]

    if "v0" in por_version and "v1" in por_version:
        md += ["## Comparación zero-shot (v0) vs few-shot (v1)", ""]
        md += comparacion(registros_por_caso(por_version["v0"]), registros_por_caso(por_version["v1"])) + [""]
        md += ["_[completar: qué caso cambió y por qué; si no cambió ninguno, decirlo — es un resultado válido]_", ""]

    md += ["## Evidencia (respuestas textuales del modelo)", ""]
    for version, corridas in sorted(por_version.items()):
        md += evidencia(version, registros_por_caso(corridas))

    destino = Path(args.salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"📝 Borrador escrito en {destino}")


if __name__ == "__main__":
    main()
