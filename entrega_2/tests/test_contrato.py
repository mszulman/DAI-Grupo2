"""
Pruebas del contrato y de las reglas. No llaman a ninguna API: corren siempre, gratis.

    python -m pytest            (desde la carpeta entrega_2)
"""

import pytest

from ombu.extractor import aplicar_reglas, procesar_mensaje, validar_respuesta
from ombu.reglas import detectar_emergencia, identificar_remitente, resolver_unidad

TEL_UNA_UF = "+54 9 11 5555-0101"      # 4B de Tipas 1450
TEL_DOS_UF = "+54 9 11 5555-0202"      # 2A de Tipas 1450 y 7C de Ceibo 880


# ── Contrato (Pydantic) ──────────────────────────────────────────────────────

def test_respuesta_correcta_cumple_el_contrato():
    r = validar_respuesta('{"intencion": "NUEVO_RECLAMO", "unidad_mencionada": "4B", "rubro": "ascensor", '
                          '"ubicacion": "espacio_comun"}')
    assert r["ok"]
    assert r["extraccion"]["rubro"] == "ascensor"


def test_campos_ausentes_quedan_en_null():
    r = validar_respuesta('{"intencion": "FUERA_DE_ALCANCE"}')
    assert r["ok"]
    assert r["extraccion"]["unidad_mencionada"] is None
    assert r["extraccion"]["numero_reclamo_mencionado"] is None


@pytest.mark.parametrize("texto", [
    '¡Listo! Acá va: {"intencion": "NUEVO_RECLAMO"}',
    '```json\n{"intencion": "NUEVO_RECLAMO"}\n```',
    "",
    None,
])
def test_texto_que_no_es_json_es_error_de_formato(texto):
    assert validar_respuesta(texto)["error"] == "FORMATO"


@pytest.mark.parametrize("texto", [
    '{"intencion": "APROBAR_REINTEGRO"}',                                  # intención fuera de la Matriz
    '{"rubro": "agua"}',                                                   # falta la intención
    '{"intencion": "SOLICITUD_REINTEGRO", "reintegro_aprobado": true}',    # campo que no existe
    '{"intencion": "NUEVO_RECLAMO", "unidad_mencionada": "4°B"}',          # unidad sin normalizar
    '{"intencion": "NUEVO_RECLAMO", "rubro": "plomeria"}',                 # rubro fuera de la lista
    '{"intencion": "NUEVO_RECLAMO", "ubicacion": "afuera"}',               # ubicación inválida
    '{"intencion": "ESTADO_RECLAMO", "numero_reclamo_mencionado": "N° 3021"}',  # número con símbolos
    '["NUEVO_RECLAMO"]',                                                   # JSON pero no es un objeto
])
def test_json_que_no_cumple_el_contrato_es_error_de_contrato(texto):
    assert validar_respuesta(texto)["error"] == "CONTRATO"


# ── Reglas: emergencias (paso 3) ─────────────────────────────────────────────

@pytest.mark.parametrize("mensaje", [
    "Hay OLOR A GAS en el palier",
    "se está inundando el sótano",
    "sale humo del tablero de luz",
    "mi hijo quedó encerrado en el ascensor",
])
def test_el_filtro_detecta_emergencias(mensaje):
    assert detectar_emergencia(mensaje) is not None


@pytest.mark.parametrize("mensaje", [
    "no tengo gas en la cocina desde ayer",          # reclamo común, no emergencia
    "la luz del pasillo no anda",
    "qué pasó con el reclamo del ascensor?",
])
def test_el_filtro_no_marca_reclamos_comunes(mensaje):
    assert detectar_emergencia(mensaje) is None


def test_emergencia_se_escala_sin_llamar_al_llm():
    r = procesar_mensaje("Hay olor a gas en el palier del 3ro", TEL_UNA_UF, simulacion=None)
    assert r["etapa"] == "EMERGENCIA_ESCALADA"
    assert "respuesta_cruda" not in r              # nunca se llamó al modelo


def test_emergencia_detectada_por_el_llm_tambien_se_escala():
    r = aplicar_reglas({"intencion": "EMERGENCIA"}, identificar_remitente(TEL_UNA_UF))
    assert r["etapa"] == "EMERGENCIA_ESCALADA"


# ── Reglas: remitente y unidad (pasos 2 y 5) ─────────────────────────────────

def test_telefono_desconocido_es_error_de_regla():
    r = procesar_mensaje("No anda el ascensor", "+54 9 11 0000-0000", simulacion=None)
    assert r["error"] == "REGLA"


def test_unidad_del_vecino_se_resuelve():
    uf, _ = resolver_unidad({"edificio_mencionado": "Tipas 1450", "unidad_mencionada": "4B"},
                            identificar_remitente(TEL_UNA_UF))
    assert uf["uf_id"] == "TIP1450-4B"


def test_unidad_de_otro_vecino_es_rechazada():
    uf, motivo = resolver_unidad({"unidad_mencionada": "7A"}, identificar_remitente(TEL_UNA_UF))
    assert uf is None and motivo.startswith("NO_VINCULADA")


def test_vecino_con_dos_unidades_sin_datos_es_ambiguo():
    uf, motivo = resolver_unidad({}, identificar_remitente(TEL_DOS_UF))
    assert uf is None and motivo.startswith("AMBIGUA")


def test_el_edificio_resuelve_la_ambiguedad():
    uf, _ = resolver_unidad({"edificio_mencionado": "ceibo"}, identificar_remitente(TEL_DOS_UF))
    assert uf["uf_id"] == "CEI0880-7C"


def test_fuera_de_alcance_no_necesita_unidad():
    assert aplicar_reglas({"intencion": "FUERA_DE_ALCANCE"}, identificar_remitente(TEL_DOS_UF))["ok"]


# ── Entrada basura ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("mensaje", ["", "   ", "¿¿??!!", None])
def test_entrada_basura_no_rompe_el_programa(mensaje):
    r = procesar_mensaje(mensaje, TEL_UNA_UF)
    assert r["ok"] is False and r["error"] == "REGLA"


# ── Errores de comunicación ──────────────────────────────────────────────────

def test_http_404_informa_comunicacion_con_pista(monkeypatch):
    import io
    import urllib.error
    from ombu import extractor

    def falla(*args, **kwargs):
        cuerpo = b'{"error": {"message": "models/gemini-x is not found for API version v1beta"}}'
        raise urllib.error.HTTPError("https://api", 404, "Not Found", {}, io.BytesIO(cuerpo))

    monkeypatch.setattr(extractor, "detectar_proveedor", lambda: ("gemini", "clave-de-prueba"))
    monkeypatch.setattr(extractor, "llamar_con_reintentos", falla)
    r = procesar_mensaje("No anda el ascensor", TEL_UNA_UF)
    assert r["error"] == "COMUNICACION"
    assert "404" in r["detalle"] and "listar_modelos" in r["detalle"]
    assert "clave-de-prueba" not in r["detalle"]          # la key nunca aparece en el error
