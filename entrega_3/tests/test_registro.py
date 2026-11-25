"""
Pruebas del registro de reclamos y de las reglas nuevas de la Entrega 3. Sin API.

    python -m pytest            (desde la carpeta entrega_3)
"""

import json

import pytest

from ombu.registro import ARCHIVO_RECLAMOS, RegistroReclamos
from ombu.reglas import calcular_prioridad, detectar_emergencia, identificar_remitente

UF_4B_TIPAS = identificar_remitente("+54 9 11 5555-0101")[0]     # TIP1450-4B
UF_7C_CEIBO = identificar_remitente("+54 9 11 5555-0202")[1]     # CEI0880-7C
UF_1D_CEIBO = identificar_remitente("+54 9 11 5555-0303")[0]     # CEI0880-1D


@pytest.fixture
def registro():
    return RegistroReclamos.desde_archivo()


# ── Filtro de emergencias: patrones nuevos ──────────────────────────────────

@pytest.mark.parametrize("mensaje", [
    "mi vieja quedó adentro del ascensor entre el 2 y el 3",     # caso 4 del lote de la Entrega 2
    "estamos en el palier y no podemos salir, la puerta no abre",
])
def test_los_patrones_nuevos_detectan_la_emergencia(mensaje):
    assert detectar_emergencia(mensaje) is not None


# ── Prioridad (paso 7) ──────────────────────────────────────────────────────

@pytest.mark.parametrize("rubro, ubicacion, descripcion, esperada", [
    ("ascensor", "espacio_comun", "No anda el ascensor", "ALTA"),
    ("gas", "unidad", "No tengo gas en la cocina", "ALTA"),
    ("agua", "unidad", "Estamos sin agua desde ayer", "ALTA"),
    ("electricidad", "espacio_comun", "No anda la luz del pasillo", "MEDIA"),
    ("agua", "unidad", "Mancha de humedad en el techo", "MEDIA"),
    ("cerrajeria", "unidad", "La cerradura de mi puerta está dura", "BAJA"),
])
def test_prioridad_por_reglas(rubro, ubicacion, descripcion, esperada):
    assert calcular_prioridad(rubro, ubicacion, descripcion)[0] == esperada


# ── Registro: sensores ──────────────────────────────────────────────────────

def test_duplicado_en_espacio_comun_lo_detecta_aunque_lo_haya_hecho_otro_vecino(registro):
    dup = registro.buscar_duplicado(UF_4B_TIPAS, "ascensor", "espacio_comun")
    assert dup["numero"] == "3044" and dup["uf_id"] != UF_4B_TIPAS["uf_id"]


def test_un_reclamo_resuelto_no_cuenta_como_duplicado(registro):
    assert registro.buscar_duplicado(UF_7C_CEIBO, "cerrajeria", "espacio_comun") is None


def test_dentro_de_una_unidad_solo_es_duplicado_si_es_la_misma_unidad(registro):
    assert registro.buscar_duplicado(UF_7C_CEIBO, "agua", "unidad") is None
    assert registro.buscar_duplicado(UF_4B_TIPAS, "agua", "unidad")["numero"] == "3021"


def test_un_vecino_no_ve_los_reclamos_de_otra_unidad(registro):
    numeros = {r["numero"] for r in registro.reclamos_visibles(UF_1D_CEIBO)}
    assert "3050" in numeros          # su reclamo
    assert "2987" in numeros          # espacio común de su edificio
    assert "3021" not in numeros      # unidad de otro edificio


def test_no_puede_ver_un_reclamo_de_otro_edificio(registro):
    assert not registro.puede_ver(registro.buscar_por_numero("3050"), UF_4B_TIPAS)


# ── Registro: actuadores ────────────────────────────────────────────────────

def test_registrar_asigna_un_numero_real_y_nuevo(registro):
    r = registro.registrar(UF_7C_CEIBO, "agua", "unidad", "Humedad en el living", "MEDIA", "2026-11-24")
    assert r["numero"] == "3051" and r["estado"] == "ABIERTO"
    assert registro.buscar_por_numero("3051") is not None


def test_sumar_aviso_no_crea_un_reclamo_nuevo(registro):
    antes = len(registro.reclamos_visibles(UF_4B_TIPAS))
    r = registro.sumar_aviso("3044", UF_4B_TIPAS)
    assert UF_4B_TIPAS["uf_id"] in r["avisos"]
    assert len(registro.reclamos_visibles(UF_4B_TIPAS)) == antes


def test_el_registro_trabaja_en_memoria_y_no_modifica_el_archivo(registro):
    original = ARCHIVO_RECLAMOS.read_text(encoding="utf-8")
    registro.registrar(UF_7C_CEIBO, "agua", "unidad", "Prueba", "MEDIA", "2026-11-24")
    registro.agregar_nota("3050", UF_1D_CEIBO, "nota de prueba")
    assert ARCHIVO_RECLAMOS.read_text(encoding="utf-8") == original
    assert len(json.loads(original)) == 4
