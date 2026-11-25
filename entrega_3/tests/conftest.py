"""Configuración común de las pruebas: nunca llaman a una API, aunque haya un .env con key."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))   # para importar embeddings_prueba

from ombu import extractor, rag, redactor  # noqa: E402


@pytest.fixture(autouse=True)
def sin_api(monkeypatch):
    """
    Los LLM se simulan siempre, aunque haya una key en el .env de quien corre las pruebas.
    Ojo: ningún archivo de pruebas puede definir otro fixture llamado `sin_api`, porque pytest
    usaría ese en lugar de este (así se nos escapó el RAG en test_workflow.py).
    """
    for modulo in (extractor, redactor, rag):
        monkeypatch.setattr(modulo, "detectar_proveedor", lambda: None)
