"""
El workflow de reclamos: la llamada suelta de la Entrega 2 convertida en una SECUENCIA de pasos.

El orden de los pasos lo fija EL DESARROLLADOR (este archivo). El modelo no decide qué paso
sigue: solo interviene en los pasos marcados [LLM]. Esa es la diferencia con un agente (Parte C).

    Mensaje + teléfono
      │
      ├─ 1  Recepción (¿el mensaje tiene texto?) ................. [Regla]    ┐
      ├─ 3  Filtro de emergencias (antes del LLM) ................ [Regla]    │  componente de la
      │       └─ ✋ coincide → EMERGENCIA_ESCALADA (respuesta fija)            │  Entrega 2
      ├─ 2  Identificar al vecino en el padrón ................... [Regla]    │  (extractor.py)
      ├─ 4  Interpretar el mensaje ............................... [LLM]      │
      ├─ 5  Validar contrato y que la unidad sea del vecino ...... [Regla]    ┘
      │       └─ ✋ falla → REVISION_HUMANA  ·  ambigua → PEDIR_ACLARACION
      ├─    Enrutar según la intención ........................... [Regla]
      │       └─ FUERA_DE_ALCANCE → DERIVADO (respuesta fija)
      ├─ 6  Buscar el reclamo: duplicado, citado o del vecino .... [Herramienta: sensor]
      │       └─ ✋ el reclamo no existe o no es del vecino → REVISION_HUMANA
      ├─ 7  Registrar, sumar aviso o ampliar; prioridad por reglas [Herramienta: actuador] + [Regla]
      ├─ 8  ✋ Reintegros y daños: decide una persona ............. [Humano]   → REINTEGRO_EN_EVALUACION
      ├─ 9  Redactar la respuesta ................................ [LLM]      ┐ redactor.py
      ├─ 10 Validar la salida (si falla → plantilla fija) ........ [Regla]    ┘
      └─ 11 Enviar y registrar la interacción .................... [Regla]

Estados posibles al terminar:
    EMERGENCIA_ESCALADA     → riesgo físico: guardia + respuesta fija, sin redacción del LLM
    REVISION_HUMANA         → algo no es confiable (extracción, padrón, unidad, reclamo ajeno): revisa una persona
    PEDIR_ACLARACION        → el vecino tiene varias unidades y no dijo cuál
    DERIVADO                → no es un reclamo de mantenimiento: respuesta fija
    RECLAMO_REGISTRADO      → reclamo nuevo, con número real y prioridad calculada por reglas
    AVISO_SUMADO            → ya había un reclamo abierto por lo mismo: se suma el aviso, no se duplica
    RECLAMO_AMPLIADO        → se agregó información a un reclamo del vecino
    ESTADO_INFORMADO        → se informa el estado real de un reclamo
    SIN_RECLAMO             → no hay reclamo por ese problema: se ofrece registrarlo
    REINTEGRO_EN_EVALUACION → pedido con consecuencia económica: queda para decisión humana
"""

from datetime import date
from typing import Optional

from .extractor import PROMPT_VERSION, procesar_mensaje
from .redactor import redactar_respuesta
from .registro import RegistroReclamos
from .reglas import RESPUESTA_EMERGENCIA, calcular_prioridad, identificar_remitente

RESPUESTAS_FIJAS = {
    "REVISION_HUMANA": "Recibimos tu mensaje. Una persona del equipo de Administración Ombú lo va a revisar "
                       "y te va a responder por este medio.",
    "DERIVADO": "Este canal es para reclamos de mantenimiento del edificio. Derivamos tu consulta al equipo "
                "administrativo, que te va a responder por este medio.",
}


class Traza:
    """Registro de qué pasó en cada paso. Sirve para depurar y para la prueba de falla (A.3)."""

    def __init__(self):
        self.pasos: list[dict] = []

    def registrar(self, paso: str, tipo: str, nombre: str, resultado: str) -> None:
        self.pasos.append({"paso": paso, "tipo": tipo, "nombre": nombre, "resultado": resultado})


def _terminar(traza: Traza, estado: str, respuesta: dict, **extra) -> dict:
    traza.registrar("11", "Regla", "Enviar y registrar la interacción", f"estado {estado}")
    return {"estado": estado, "respuesta": respuesta, "traza": traza.pasos, **extra}


def _fija(estado: str) -> dict:
    return {"texto": RESPUESTAS_FIJAS[estado], "origen": "RESPUESTA FIJA"}


def _revision_humana(traza: Traza, paso: str, motivo: str, **extra) -> dict:
    """✋ Punto de control: no seguimos con datos que no son confiables."""
    traza.registrar(paso, "Regla", "Punto de control", f"✋ {motivo}")
    return _terminar(traza, "REVISION_HUMANA", _fija("REVISION_HUMANA"), motivo=motivo, **extra)


def _redactar(traza: Traza, resultado: dict) -> dict:
    respuesta = redactar_respuesta(resultado)
    traza.registrar("9", "LLM", "Redactar la respuesta", respuesta["origen"])
    valida = respuesta["origen"].startswith("LLM")
    traza.registrar("10", "Regla", "Validar la salida",
                    "✅ sin datos inventados" if valida else "se usa la plantilla fija")
    return respuesta


def workflow_reclamo(mensaje: str, telefono: str, registro: RegistroReclamos,
                     simulacion: Optional[str] = None, version: str = PROMPT_VERSION,
                     fecha: Optional[str] = None) -> dict:
    """
    Ejecuta el journey de un reclamo de punta a punta.
    `registro` se inyecta (no se construye acá): así el workflow se prueba con un registro de prueba.
    `simulacion` es la respuesta de ejemplo del LLM que se usa cuando no hay API key.
    """
    traza = Traza()
    fecha = fecha or date.today().isoformat()

    # ── Pasos 1 a 5 · el componente de la Entrega 2 [Regla + LLM + Regla] ───────
    r = procesar_mensaje(mensaje, telefono, simulacion, version)

    if r.get("etapa") == "EMERGENCIA_ESCALADA":
        por_filtro = "respuesta_cruda" not in r
        traza.registrar("1", "Regla", "Recepción", "✅ mensaje con texto")
        traza.registrar("3" if por_filtro else "5", "Regla" if por_filtro else "LLM + Regla",
                        "Filtro de emergencias" if por_filtro else "Segunda red: el LLM clasificó EMERGENCIA",
                        f"🚨 {r['motivo']}")
        return _terminar(traza, "EMERGENCIA_ESCALADA", {"texto": RESPUESTA_EMERGENCIA, "origen": "RESPUESTA FIJA"},
                         accion="protocolo_guardia")
    detalle = r.get("detalle", "") if not r["ok"] else ""
    if "vacío" not in detalle:
        traza.registrar("1", "Regla", "Recepción", "✅ mensaje con texto")
        traza.registrar("3", "Regla", "Filtro de emergencias", "sin coincidencias")
    if "vacío" not in detalle and "padrón" not in detalle:
        traza.registrar("2", "Regla", "Identificar al vecino en el padrón", "✅ teléfono registrado")

    if not r["ok"]:
        if r["error"] in ("COMUNICACION", "FORMATO", "CONTRATO"):
            traza.registrar("4", "LLM", "Interpretar el mensaje", f"❌ {r['error']}")
            return _revision_humana(traza, "5", f"Falló la interpretación ({r['error']}): {r['detalle']}",
                                    mensaje_original=mensaje)
        if r.get("extraccion"):
            traza.registrar("4", "LLM", "Interpretar el mensaje", f"intención = {r['extraccion']['intencion']}")
        if detalle.startswith("AMBIGUA"):
            traza.registrar("5", "Regla", "Validar la unidad", f"✋ {detalle}")
            opciones = [f"{u['unidad']} de {u['consorcio']}" for u in identificar_remitente(telefono)]
            resultado = {"tipo": "PEDIR_ACLARACION", "opciones": opciones}
            return _terminar(traza, "PEDIR_ACLARACION", _redactar(traza, resultado), extraccion=r.get("extraccion"))
        paso = "2" if "padrón" in detalle else ("1" if "vacío" in detalle else "5")
        return _revision_humana(traza, paso, detalle, mensaje_original=mensaje)

    datos = r["extraccion"]
    traza.registrar("4", "LLM", "Interpretar el mensaje", f"intención = {datos['intencion']}")
    traza.registrar("5", "Regla", "Validar contrato y unidad", f"✅ {r.get('uf', {}).get('uf_id', 'sin unidad')}")

    # ── Enrutamiento [Regla]: el CÓDIGO decide el camino según la intención ───────
    intencion = datos["intencion"]
    if intencion == "FUERA_DE_ALCANCE":
        traza.registrar("—", "Regla", "Enrutar por intención", "FUERA_DE_ALCANCE → respuesta fija")
        return _terminar(traza, "DERIVADO", _fija("DERIVADO"), extraccion=datos)
    traza.registrar("—", "Regla", "Enrutar por intención", f"{intencion} → flujo de {intencion.lower()}")

    uf = r["uf"]
    if intencion == "NUEVO_RECLAMO":
        return _nuevo_reclamo(traza, datos, uf, registro, fecha)
    if intencion == "AMPLIAR_RECLAMO":
        return _ampliar_reclamo(traza, datos, uf, registro, mensaje)
    if intencion == "ESTADO_RECLAMO":
        return _estado_reclamo(traza, datos, uf, registro)
    if intencion == "SOLICITUD_REINTEGRO":
        return _reintegro(traza, datos, uf, mensaje)
    raise ValueError(f"Intención sin flujo definido: {intencion}")


# ── Un flujo por intención ──────────────────────────────────────────────────

def _nuevo_reclamo(traza, datos, uf, registro, fecha) -> dict:
    if datos["rubro"] is None:
        return _revision_humana(traza, "6", "El reclamo no tiene rubro: no se puede buscar duplicados ni priorizar")

    # Paso 6 · ¿ya existe? [Herramienta: sensor]
    dup = registro.buscar_duplicado(uf, datos["rubro"], datos["ubicacion"])
    if dup:
        traza.registrar("6", "Herramienta", "Buscar duplicado (sensor)",
                        f"reclamo N° {dup['numero']} abierto por el mismo problema")
        reclamo = registro.sumar_aviso(dup["numero"], uf)
        traza.registrar("7", "Herramienta", "Sumar aviso (actuador)", f"N° {reclamo['numero']}, no se crea uno nuevo")
        resultado = {"tipo": "AVISO_SUMADO", "numero_reclamo": reclamo["numero"], "descripcion": reclamo["descripcion"]}
        return _terminar(traza, "AVISO_SUMADO", _redactar(traza, resultado), reclamo=reclamo)
    traza.registrar("6", "Herramienta", "Buscar duplicado (sensor)", "no hay un reclamo abierto por esto")

    # Paso 7 · prioridad [Regla] + registro [Herramienta: actuador]
    prioridad, motivo = calcular_prioridad(datos["rubro"], datos["ubicacion"], datos["descripcion_problema"])
    traza.registrar("7", "Regla", "Calcular prioridad", f"{prioridad} ({motivo})")
    reclamo = registro.registrar(uf, datos["rubro"], datos["ubicacion"], datos["descripcion_problema"], prioridad, fecha)
    traza.registrar("7", "Herramienta", "Registrar reclamo (actuador)", f"N° {reclamo['numero']}")
    resultado = {"tipo": "RECLAMO_REGISTRADO", "numero_reclamo": reclamo["numero"], "descripcion": reclamo["descripcion"]}
    return _terminar(traza, "RECLAMO_REGISTRADO", _redactar(traza, resultado), reclamo=reclamo)


def _reclamo_citado(traza, datos, uf, registro) -> tuple[Optional[dict], Optional[str]]:
    """Paso 6 cuando el vecino cita un número: tiene que existir y ser visible para él (privacidad)."""
    numero = datos["numero_reclamo_mencionado"]
    reclamo = registro.buscar_por_numero(numero)
    if reclamo is None:
        return None, f"El reclamo N° {numero} no existe"
    if not registro.puede_ver(reclamo, uf):
        return None, f"El reclamo N° {numero} no corresponde a la unidad ni al edificio del vecino"
    traza.registrar("6", "Herramienta", "Buscar reclamo citado (sensor)", f"N° {numero}, {reclamo['estado']}")
    return reclamo, None


def _ampliar_reclamo(traza, datos, uf, registro, mensaje) -> dict:
    if datos["numero_reclamo_mencionado"]:
        reclamo, error = _reclamo_citado(traza, datos, uf, registro)
        if error:
            return _revision_humana(traza, "6", error)
    else:
        abiertos = [x for x in registro.reclamos_visibles(uf, datos["rubro"]) if x["estado"] != "RESUELTO"]
        traza.registrar("6", "Herramienta", "Buscar reclamos del vecino (sensor)", f"{len(abiertos)} abierto(s)")
        if len(abiertos) != 1:
            return _revision_humana(traza, "6", "No se puede saber con certeza a qué reclamo agregar la información")
        reclamo = abiertos[0]

    if reclamo["estado"] == "RESUELTO":
        return _revision_humana(traza, "6", f"El reclamo N° {reclamo['numero']} ya está resuelto")
    reclamo = registro.agregar_nota(reclamo["numero"], uf, datos["descripcion_problema"] or mensaje.strip()[:200])
    traza.registrar("7", "Herramienta", "Agregar información (actuador)", f"N° {reclamo['numero']}")
    resultado = {"tipo": "RECLAMO_AMPLIADO", "numero_reclamo": reclamo["numero"]}
    return _terminar(traza, "RECLAMO_AMPLIADO", _redactar(traza, resultado), reclamo=reclamo)


def _estado_reclamo(traza, datos, uf, registro) -> dict:
    if datos["numero_reclamo_mencionado"]:
        reclamo, error = _reclamo_citado(traza, datos, uf, registro)
        if error:
            return _revision_humana(traza, "6", error)
    else:
        visibles = registro.reclamos_visibles(uf, datos["rubro"])
        traza.registrar("6", "Herramienta", "Buscar reclamos del vecino (sensor)",
                        f"{len(visibles)} reclamo(s) de {datos['rubro'] or 'cualquier rubro'}")
        if not visibles:
            return _terminar(traza, "SIN_RECLAMO", _redactar(traza, {"tipo": "SIN_RECLAMO"}))
        reclamo = visibles[0]   # el más reciente

    # Al vecino le llega el estado, no las notas internas (pueden nombrar a otras unidades).
    resultado = {"tipo": "ESTADO_INFORMADO", "numero_reclamo": reclamo["numero"],
                 "estado_reclamo": reclamo["estado"], "descripcion": reclamo["descripcion"]}
    return _terminar(traza, "ESTADO_INFORMADO", _redactar(traza, resultado), reclamo=reclamo)


def _reintegro(traza, datos, uf, mensaje) -> dict:
    # Paso 8 · ✋ consecuencia económica: el sistema registra el pedido y decide una persona.
    pedido = {"uf_id": uf["uf_id"], "descripcion": datos["descripcion_problema"],
              "numero_reclamo_mencionado": datos["numero_reclamo_mencionado"], "mensaje_original": mensaje}
    traza.registrar("8", "Humano", "Decisión sobre el reintegro", "⏸ pendiente: lo evalúa la administración")
    resultado = {"tipo": "REINTEGRO_EN_EVALUACION", "descripcion": datos["descripcion_problema"]}
    return _terminar(traza, "REINTEGRO_EN_EVALUACION", _redactar(traza, resultado),
                     requiere_decision_humana=True, pedido=pedido)
