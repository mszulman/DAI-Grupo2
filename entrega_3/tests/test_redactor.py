"""
Pruebas del redactor (paso 9) y de la validación de salida (paso 10). Sin API.

    python -m pytest            (desde la carpeta entrega_3)
"""

import urllib.error

import pytest

from ombu import redactor
from ombu.reglas import validar_salida

RESULTADOS = [
    {"tipo": "RECLAMO_REGISTRADO", "numero_reclamo": "3051", "descripcion": "Humedad en el techo del living"},
    {"tipo": "AVISO_SUMADO", "numero_reclamo": "3044", "descripcion": "Ascensor detenido en planta baja"},
    {"tipo": "RECLAMO_AMPLIADO", "numero_reclamo": "3050"},
    {"tipo": "ESTADO_INFORMADO", "numero_reclamo": "3021", "estado_reclamo": "EN_CURSO"},
    {"tipo": "SIN_RECLAMO"},
    {"tipo": "REINTEGRO_EN_EVALUACION", "descripcion": "Pagó un plomero por la bajada común"},
    {"tipo": "PEDIR_ACLARACION", "opciones": ["2A de Tipas 1450", "7C de Ceibo 880"]},
]


@pytest.fixture
def con_api(monkeypatch):
    """Simula que hay un proveedor configurado, sin llamar a ninguna API real."""
    monkeypatch.setattr(redactor, "detectar_proveedor", lambda: ("gemini", "clave-de-prueba"))
    return monkeypatch


# ── Paso 10: validar_salida ─────────────────────────────────────────────────

@pytest.mark.parametrize("texto, resultado", [
    ("Registramos tu reclamo N° 3051. Te avisamos cuando haya novedades.", {"numero_reclamo": "3051"}),
    ("Tu pedido quedó registrado; no está aprobado, lo evalúa la administración.", {}),
    ("Sumamos tu aviso al reclamo N° 3044 de Tipas 1450.", {"numero_reclamo": "3044"}),
])
def test_respuestas_correctas_pasan_la_validacion(texto, resultado):
    assert validar_salida(texto, resultado)[0]


@pytest.mark.parametrize("texto, resultado, motivo", [
    ("Registramos tu reclamo.", {"numero_reclamo": "3051"}, "no menciona"),
    ("Sumamos tu aviso al reclamo N° 3044 y al reclamo N° 3021.", {"numero_reclamo": "3044"}, "otro número"),
    ("Tu reclamo N° 3044: el técnico va el jueves.", {"numero_reclamo": "3044"}, "día de visita"),
    ("Tu reclamo N° 3044: el técnico va el 27/11.", {"numero_reclamo": "3044"}, "fecha"),
    ("Tu reintegro de $120.000 está en proceso.", {}, "monto"),
    ("Listo, tu reintegro está aprobado.", {}, "aprobado"),
    ("Te confirmamos el depósito para la semana próxima.", {}, "depósito"),
])
def test_respuestas_con_datos_inventados_no_pasan(texto, resultado, motivo):
    ok, detalle = validar_salida(texto, resultado)
    assert not ok and motivo in detalle


# ── Plantillas ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("resultado", RESULTADOS, ids=lambda r: r["tipo"])
def test_cada_plantilla_pasa_la_propia_validacion(resultado):
    assert validar_salida(redactor.plantilla_fija(resultado), resultado)[0]


def test_tipo_desconocido_es_un_error_de_programacion():
    with pytest.raises(ValueError):
        redactor.plantilla_fija({"tipo": "APROBAR_TODO"})


# ── Redactor: cuándo usa el LLM y cuándo la plantilla ───────────────────────

def test_sin_api_key_usa_la_plantilla(monkeypatch):
    monkeypatch.setattr(redactor, "detectar_proveedor", lambda: None)
    r = redactor.redactar_respuesta(RESULTADOS[0])
    assert r["origen"].startswith("PLANTILLA") and "3051" in r["texto"]


def test_una_redaccion_valida_del_llm_se_usa(con_api):
    con_api.setattr(redactor, "llamar_con_reintentos",
                    lambda *a, **k: "Listo, registramos tu reclamo N° 3051 por la humedad del living.")
    r = redactor.redactar_respuesta(RESULTADOS[0])
    assert r["origen"] == "LLM (gemini)"


def test_si_el_llm_inventa_una_fecha_se_usa_la_plantilla(con_api):
    con_api.setattr(redactor, "llamar_con_reintentos",
                    lambda *a, **k: "Registramos tu reclamo N° 3051, el plomero va el martes a las 10.")
    r = redactor.redactar_respuesta(RESULTADOS[0])
    assert "no pasó la validación" in r["origen"]
    assert "martes" not in r["texto"] and "martes" in r["texto_rechazado"]


def test_si_la_api_falla_se_usa_la_plantilla(con_api):
    def falla(*a, **k):
        raise urllib.error.URLError("sin conexión")
    con_api.setattr(redactor, "llamar_con_reintentos", falla)
    r = redactor.redactar_respuesta(RESULTADOS[3])
    assert r["origen"].startswith("PLANTILLA (falló la API") and "3021" in r["texto"]


def test_el_redactor_pide_texto_libre_y_no_json(con_api):
    capturado = {}

    def espia(*a, **k):
        capturado.update(k)
        return "Tu reclamo N° 3021 está en curso."
    con_api.setattr(redactor, "llamar_con_reintentos", espia)
    redactor.redactar_respuesta(RESULTADOS[3])
    assert capturado["json_mode"] is False
