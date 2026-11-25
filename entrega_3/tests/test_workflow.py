"""
Pruebas del workflow de reclamos (Partes A y B). Sin API: corren en modo simulación.

    python -m pytest            (desde la carpeta entrega_3)
"""

import json

import pytest

from ombu.base_conocimiento import cargar_corpus
from ombu.config import RAIZ_PROYECTO
from ombu.rag import SIN_INFORMACION
from ombu.registro import RegistroReclamos
from ombu.reglas import edificios_del_vecino, identificar_remitente
from ombu.workflow import workflow_reclamo

LOTE = json.loads((RAIZ_PROYECTO / "datos" / "lote_workflow.json").read_text(encoding="utf-8"))


class BaseFalsa:
    """
    Una base de conocimiento de mentira para probar el ENRUTAMIENTO del workflow (Parte B).
    Las similitudes son fijas por mensaje; el filtro (vigencia y edificio) sí se aplica de verdad.
    La búsqueda con embeddings se prueba en test_rag.py.
    """
    umbral = 0.35
    SIMILITUDES = {
        LOTE[10]["mensaje"]: {"REG-TIP-OBRAS": 0.62, "REG-CEI-OBRAS": 0.61, "POL-RESP-UNIDAD": 0.40},
        LOTE[11]["mensaje"]: {"POL-PLAZOS-2025": 0.70, "POL-PLAZOS": 0.66, "POL-PRIORIDAD": 0.41},
        LOTE[12]["mensaje"]: {"POL-INQUILINOS": 0.31, "POL-RESP-UNIDAD": 0.29, "REG-TIP-TERRAZA": 0.22},
    }

    def __init__(self):
        self.corpus = {d["id"]: d for d in cargar_corpus()}
        self.filtros: list = []

    def buscar(self, consulta, k=3, filtro=None):
        self.filtros.append(filtro)
        condiciones = filtro["$and"] if filtro and "$and" in filtro else [filtro] if filtro else []
        vigentes = any(c == {"vigente": True} for c in condiciones)
        edificios = next((c["edificio"]["$in"] for c in condiciones if "edificio" in c), None)
        candidatos = []
        for id_, sim in self.SIMILITUDES.get(consulta, {}).items():
            d = self.corpus[id_]
            m = d["metadatos"]
            if (vigentes and not m["vigente"]) or (edificios and m["edificio"] not in edificios):
                continue
            candidatos.append({"id": id_, "texto": d["descripcion_semantica"], "titulo": d["titulo"], **m,
                               "similitud": sim, "supera_umbral": sim >= self.umbral})
        return sorted(candidatos, key=lambda c: -c["similitud"])[:k]


@pytest.fixture
def registro():
    return RegistroReclamos.desde_archivo()


@pytest.fixture
def base():
    return BaseFalsa()


def correr(caso: dict, registro: RegistroReclamos, base=None) -> dict:
    return workflow_reclamo(caso["mensaje"], caso["telefono"], registro, caso["simulacion"], fecha="2026-11-24",
                            base=base or BaseFalsa())


def pasos(resultado: dict) -> list[str]:
    return [p["paso"] for p in resultado["traza"]]


# ── Cada caso del lote termina donde tiene que terminar (A.3) ───────────────

@pytest.mark.parametrize("caso", LOTE, ids=[c["tipo"] for c in LOTE])
def test_cada_caso_del_lote_termina_en_su_estado_esperado(caso, registro, base):
    assert correr(caso, registro, base)["estado"] == caso["estado_esperado"]
    consulta = json.loads(caso["simulacion"])["intencion"] == "CONSULTA_REGLAMENTO" if caso["simulacion"] else False
    assert bool(base.filtros) == consulta        # solo las consultas de reglamento tocan la base del RAG


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


# ── Parte B: consultas de reglamento con RAG ────────────────────────────────

def test_la_consulta_usa_el_reglamento_del_edificio_del_vecino(registro, base):
    r = correr(LOTE[10], registro, base)                    # vecino del 1D de Ceibo 880
    assert r["estado"] == "CONSULTA_RESPONDIDA"
    assert "REG-CEI-OBRAS" in r["respuesta"]["fuentes"] and "REG-TIP-OBRAS" not in r["respuesta"]["fuentes"]
    assert base.filtros[0]["$and"][1] == {"edificio": {"$in": ["TODOS", "CEI0880"]}}


def test_la_consulta_responde_con_la_politica_vigente(registro, base):
    r = correr(LOTE[11], registro, base)
    assert r["respuesta"]["fuentes"][0] == "POL-PLAZOS"
    assert "POL-PLAZOS-2025" not in [c[0] for c in r["rag"]["candidatos"]]
    assert "24 horas" in r["respuesta"]["texto"]            # simulación: el fragmento vigente, textual


def test_fuera_del_corpus_deriva_sin_llamar_al_llm(registro, base):
    r = correr(LOTE[12], registro, base)
    assert r["estado"] == "DERIVADO" and r["respuesta"]["texto"].startswith(SIN_INFORMACION)
    assert "9" not in pasos(r)                              # el LLM no redactó nada


def test_la_consulta_no_registra_ningun_reclamo(registro, base):
    correr(LOTE[11], registro, base)
    assert registro.buscar_por_numero("3051") is None


def test_edificios_del_vecino_salen_del_padron():
    dos = identificar_remitente("+54 9 11 5555-0202")       # 2A de Tipas 1450 y 7C de Ceibo 880
    assert edificios_del_vecino({"edificio_mencionado": None}, dos) == ["TIP1450", "CEI0880"]
    assert edificios_del_vecino({"edificio_mencionado": "Ceibo"}, dos) == ["CEI0880"]
    assert edificios_del_vecino({"edificio_mencionado": "Rivadavia 5000"}, dos) == ["TIP1450", "CEI0880"]

