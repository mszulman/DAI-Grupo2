"""
Pruebas del RAG (Parte B). Sin API y sin descargar el modelo de embeddings: usan una base en
memoria con embeddings de juguete (tests/embeddings_prueba.py). Prueban la MECÁNICA: el corpus,
el filtrado híbrido, el umbral, la simulación y la validación de la respuesta.
La calidad de la búsqueda con el modelo real se mide aparte: `python rag.py calibrar`.
"""

import io
import urllib.error

import pytest
from embeddings_prueba import EmbeddingsDePrueba

from ombu import rag
from ombu.base_conocimiento import BaseConocimiento, cargar_corpus, codigo_edificio, filtro_para
from ombu.rag import SIN_INFORMACION, responder_consulta, validar_respuesta_rag

UMBRAL_PRUEBA = 0.25      # el de juguete da similitudes más bajas que el modelo real
OBRAS = "horario permitido para obras y arreglos de técnicos"


@pytest.fixture(scope="module")
def base():
    return BaseConocimiento(EmbeddingsDePrueba(), en_memoria=True, umbral=UMBRAL_PRUEBA).abrir()


def ids(candidatos):
    return [c["id"] for c in candidatos]


def con_llm(monkeypatch, respuesta):
    """Simula que hay API key y que el modelo responde `respuesta` (o lanza la excepción)."""
    monkeypatch.setattr(rag, "detectar_proveedor", lambda: ("gemini", "key-de-prueba"))

    def falso(*_args, **_kwargs):
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta
    monkeypatch.setattr(rag, "llamar_con_reintentos", falso)


# ── B.1 · El corpus ─────────────────────────────────────────────────────────

def test_el_corpus_tiene_entre_10_y_15_documentos_con_descripcion_y_metadatos():
    corpus = cargar_corpus()
    assert 10 <= len(corpus) <= 15
    assert len({d["id"] for d in corpus}) == len(corpus)
    for d in corpus:
        assert len(d["descripcion_semantica"]) > 100
        m = d["metadatos"]
        assert m["edificio"] in ("TODOS", "TIP1450", "CEI0880")
        assert isinstance(m["vigente"], bool) and m["codigo"] and m["tema"]


def test_cada_version_reemplazada_tiene_su_version_vigente():
    corpus = cargar_corpus()
    vigentes = {d["metadatos"]["codigo"] for d in corpus if d["metadatos"]["vigente"]}
    reemplazadas = [d["metadatos"]["codigo"] for d in corpus if not d["metadatos"]["vigente"]]
    assert reemplazadas and set(reemplazadas) <= vigentes


def test_se_indexan_todos_los_documentos(base):
    assert len(base.documentos()) == len(cargar_corpus())


# ── B.2 · Filtrado híbrido ──────────────────────────────────────────────────

def test_filtro_para_combina_vigencia_y_edificio():
    assert filtro_para(["TIP1450"]) == {"$and": [{"vigente": True}, {"edificio": {"$in": ["TODOS", "TIP1450"]}}]}
    assert filtro_para(None) == {"vigente": True}
    assert filtro_para(None, solo_vigentes=False) is None
    assert codigo_edificio("CEI0880-PBA") == "CEI0880"


def test_sin_filtro_gana_la_version_reemplazada_y_con_filtro_desaparece(base):
    pregunta = "reintegro: mando el ticket y lo descuentan de la liquidación de expensas"
    assert base.buscar(pregunta)[0]["id"] == "POL-REINTEGRO-2025"          # la vieja es la más parecida
    filtrados = base.buscar(pregunta, filtro=filtro_para(["TIP1450"]))
    assert filtrados[0]["id"] == "POL-REINTEGRO" and all(c["vigente"] for c in filtrados)


def test_el_reglamento_de_otro_edificio_no_aparece(base):
    assert "REG-CEI-OBRAS" in ids(base.buscar(OBRAS))                       # sin filtro, el más parecido
    tipas = ids(base.buscar(OBRAS, filtro=filtro_para(["TIP1450"])))
    ceibo = ids(base.buscar(OBRAS, filtro=filtro_para(["CEI0880"])))
    assert "REG-TIP-OBRAS" in tipas and "REG-CEI-OBRAS" not in tipas
    assert "REG-CEI-OBRAS" in ceibo and "REG-TIP-OBRAS" not in ceibo


def test_un_vecino_con_unidades_en_dos_edificios_ve_los_dos_reglamentos(base):
    encontrados = ids(base.buscar(OBRAS, filtro=filtro_para(["TIP1450", "CEI0880"])))
    assert {"REG-TIP-OBRAS", "REG-CEI-OBRAS"} <= set(encontrados)


def test_los_candidatos_vienen_ordenados_y_marcados_contra_el_umbral(base):
    c = base.buscar("plazos para la primera visita del técnico según la prioridad")
    assert [x["similitud"] for x in c] == sorted((x["similitud"] for x in c), reverse=True)
    assert all(x["supera_umbral"] == (x["similitud"] >= UMBRAL_PRUEBA) for x in c)


# ── El umbral: fuera del corpus no se llama al LLM ──────────────────────────

def test_fuera_del_corpus_responde_sin_informacion_sin_llamar_al_llm(base, monkeypatch):
    con_llm(monkeypatch, AssertionError("no se tenía que llamar al LLM"))
    r = responder_consulta("¿Aceptan criptomonedas o bitcoin?", ["TIP1450"], base)
    assert r["estado"] == "SIN_INFORMACION" and r["texto"] == SIN_INFORMACION
    assert r["fuentes"] == [] and "no se llama al LLM" in r["origen"]


def test_sin_api_key_devuelve_el_fragmento_recuperado_citado(base):
    r = responder_consulta("plazos para la primera visita del técnico según la prioridad", None, base)
    assert r["estado"] == "RESPONDIDA" and "SIMULACIÓN" in r["origen"]
    assert r["texto"].startswith("Según plazos de atención (POL-PLAZOS)")


# ── Segunda capa: la respuesta del LLM tiene que estar anclada en lo recuperado ──

PLAZOS = "plazos para la primera visita del técnico según la prioridad"


def test_respuesta_del_llm_que_cita_lo_recuperado_se_envia(base, monkeypatch):
    con_llm(monkeypatch, "Con prioridad ALTA, la primera visita es dentro de las 24 horas (POL-PLAZOS).")
    r = responder_consulta(PLAZOS, ["TIP1450"], base)
    assert r["estado"] == "RESPONDIDA" and r["origen"] == "LLM (gemini)"


@pytest.mark.parametrize("respuesta, motivo", [
    ("Con prioridad ALTA vienen dentro de las 24 horas.", "no cita"),
    ("Vienen en 48 horas (POL-PLAZOS) y te lo reintegran (POL-REINTEGRO).", "no estaban en el contexto"),
    ("Tu reintegro está aprobado según los plazos (POL-PLAZOS).", "aprobado"),
])
def test_respuesta_del_llm_no_anclada_no_se_envia(base, monkeypatch, respuesta, motivo):
    con_llm(monkeypatch, respuesta)
    r = responder_consulta(PLAZOS, ["TIP1450"], base)
    assert r["estado"] == "NO_VALIDADA" and r["texto"] is None
    assert motivo in r["origen"] and r["texto_rechazado"] == respuesta


def test_si_el_llm_dice_que_el_contexto_no_alcanza_es_sin_informacion(base, monkeypatch):
    con_llm(monkeypatch, SIN_INFORMACION)
    r = responder_consulta(PLAZOS, ["TIP1450"], base)
    assert r["estado"] == "SIN_INFORMACION" and r["fuentes"]          # hubo contexto, pero no responde


def test_si_falla_la_api_no_se_inventa_nada(base, monkeypatch):
    con_llm(monkeypatch, urllib.error.URLError("sin red"))
    r = responder_consulta(PLAZOS, ["TIP1450"], base)
    assert r["estado"] == "NO_VALIDADA" and r["texto"] is None


@pytest.mark.parametrize("sin_grounding", [False, True])
def test_error_http_muestra_codigo_y_mensaje(monkeypatch, sin_grounding):
    cuerpo = b'{"error":{"message":"invalid API key"}}'
    error = urllib.error.HTTPError("https://api.example.test", 401, "Unauthorized", {}, io.BytesIO(cuerpo))
    con_llm(monkeypatch, error)

    if sin_grounding:
        resultado = rag.responder_sin_grounding("¿Cuánto tardan si se rompe el ascensor?")
    else:
        class BaseFalsa:
            umbral = UMBRAL_PRUEBA

            def buscar(self, *_args, **_kwargs):
                return [{"codigo": "POL-PLAZOS", "id": "POL-PLAZOS", "titulo": "Plazos de atención",
                         "texto": "La primera visita se realiza dentro de las 24 horas.",
                         "similitud": 0.8, "supera_umbral": True}]

        resultado = responder_consulta(PLAZOS, ["TIP1450"], BaseFalsa())

    assert "HTTP 401: invalid API key" in resultado["origen"]


def test_error_http_muestra_respuesta_no_json():
    error = urllib.error.HTTPError("https://api.example.test", 403, "Forbidden", {},
                                   io.BytesIO(b"Blocked by network gateway"))
    assert rag._detalle_http(error) == "HTTP 403: Blocked by network gateway"


def test_validar_respuesta_acepta_la_negacion_de_una_aprobacion():
    ok, _ = validar_respuesta_rag("El reintegro no está aprobado: lo decide la administración (POL-REINTEGRO).",
                                  ["POL-REINTEGRO"])
    assert ok


def test_sin_grounding_sin_api_key_no_muestra_nada_inventado():
    assert rag.responder_sin_grounding("¿Cuánto tardan si se rompe el ascensor?") is None
