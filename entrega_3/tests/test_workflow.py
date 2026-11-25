"""
Pruebas del workflow de reclamos (Parte A). Sin API: corren en modo simulación.

    python -m pytest            (desde la carpeta entrega_3)
"""

import json

import pytest

from ombu import extractor, redactor
from ombu.config import RAIZ_PROYECTO
from ombu.registro import RegistroReclamos
from ombu.workflow import workflow_reclamo

LOTE = json.loads((RAIZ_PROYECTO / "datos" / "lote_workflow.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def sin_api(monkeypatch):
    """Siempre modo simulación, aunque haya una key en el .env de quien corre los tests."""
    monkeypatch.setattr(extractor, "detectar_proveedor", lambda: None)
    monkeypatch.setattr(redactor, "detectar_proveedor", lambda: None)


@pytest.fixture
def registro():
    return RegistroReclamos.desde_archivo()


def correr(caso: dict, registro: RegistroReclamos) -> dict:
    return workflow_reclamo(caso["mensaje"], caso["telefono"], registro, caso["simulacion"], fecha="2026-11-24")


def pasos(resultado: dict) -> list[str]:
    return [p["paso"] for p in resultado["traza"]]


# ── Cada caso del lote termina donde tiene que terminar (A.3) ───────────────

@pytest.mark.parametrize("caso", LOTE, ids=[c["tipo"] for c in LOTE])
def test_cada_caso_del_lote_termina_en_su_estado_esperado(caso, registro):
    assert correr(caso, registro)["estado"] == caso["estado_esperado"]


# ── Puntos de control ───────────────────────────────────────────────────────

def test_reclamo_ajeno_se_detiene_en_el_paso_6_sin_informar_nada(registro):
    r = correr(LOTE[4], registro)
    assert r["estado"] == "REVISION_HUMANA" and "6" in pasos(r)
    assert "9" not in pasos(r)                           # nunca llegó a redactar
    assert "3050" not in r["respuesta"]["texto"]         # no le cuenta nada del reclamo ajeno


def test_unidad_ajena_se_detiene_en_el_paso_5_sin_registrar_nada(registro):
    antes = registro.buscar_por_numero("3051")
    r = correr(LOTE[5], registro)
    assert r["estado"] == "REVISION_HUMANA" and pasos(r)[-2] == "5"
    assert antes is None and registro.buscar_por_numero("3051") is None


def test_la_emergencia_se_frena_antes_del_llm(registro):
    r = correr(LOTE[8], registro)
    assert r["estado"] == "EMERGENCIA_ESCALADA"
    assert "4" not in pasos(r) and r["respuesta"]["origen"] == "RESPUESTA FIJA"


def test_el_reintegro_queda_para_una_persona_y_no_se_da_por_aprobado(registro):
    r = correr(LOTE[7], registro)
    assert r["requiere_decision_humana"] is True
    assert any(p["tipo"] == "Humano" for p in r["traza"])
    assert "aprobado" not in r["respuesta"]["texto"].lower().replace("no hay ningún reintegro confirmado", "")


def test_si_falla_la_interpretacion_va_a_revision_humana(registro):
    caso = {**LOTE[0], "simulacion": "¡Claro! Acá va el JSON: {\"intencion\": \"NUEVO_RECLAMO\"}"}
    r = correr(caso, registro)
    assert r["estado"] == "REVISION_HUMANA" and "FORMATO" in r["motivo"]


def test_telefono_desconocido_va_a_revision_humana_sin_llamar_al_llm(registro):
    caso = {**LOTE[0], "telefono": "+54 9 11 0000-0000"}
    r = correr(caso, registro)
    assert r["estado"] == "REVISION_HUMANA" and "4" not in pasos(r)


# ── Efectos sobre el registro ───────────────────────────────────────────────

def test_el_reclamo_nuevo_queda_registrado_con_prioridad_por_reglas(registro):
    r = correr(LOTE[0], registro)
    assert r["reclamo"]["numero"] == "3051" and r["reclamo"]["prioridad"] == "MEDIA"
    assert registro.buscar_por_numero("3051")["uf_id"] == "CEI0880-7C"
    assert "3051" in r["respuesta"]["texto"]


def test_el_duplicado_no_crea_un_reclamo_nuevo(registro):
    r = correr(LOTE[1], registro)
    assert r["reclamo"]["numero"] == "3044" and registro.buscar_por_numero("3051") is None
    assert "TIP1450-4B" in registro.buscar_por_numero("3044")["avisos"]


def test_ampliar_agrega_la_nota_al_reclamo_citado(registro):
    correr(LOTE[3], registro)
    assert any("segundo piso" in n for n in registro.buscar_por_numero("3050")["notas"])


def test_el_estado_no_filtra_notas_internas_al_vecino(registro):
    r = correr(LOTE[2], registro)
    assert r["estado"] == "ESTADO_INFORMADO" and "5B" not in r["respuesta"]["texto"]


def test_ampliar_un_reclamo_resuelto_va_a_revision_humana(registro):
    caso = {"mensaje": "Por el reclamo 2987: la puerta de la terraza volvió a fallar.",
            "telefono": "+54 9 11 5555-0303",
            "simulacion": json.dumps({"intencion": "AMPLIAR_RECLAMO", "edificio_mencionado": None,
                                      "unidad_mencionada": None, "rubro": "cerrajeria", "ubicacion": "espacio_comun",
                                      "descripcion_problema": "La puerta de la terraza volvió a fallar",
                                      "numero_reclamo_mencionado": "2987"})}
    r = correr(caso, registro)
    assert r["estado"] == "REVISION_HUMANA" and "resuelto" in r["motivo"]
