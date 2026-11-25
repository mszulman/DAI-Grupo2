"""
Embeddings de JUGUETE para las pruebas: no necesitan descargar el modelo de ~640 MB.

Cada palabra (sin tildes, recortada a 5 letras para que "cañería" y "cañerías" coincidan) suma 1
en una posición del vector elegida por un hash. Es una "bolsa de palabras": dos textos se parecen
si comparten palabras. NO entiende sinónimos (el modelo real sí), así que sirve para probar la
mecánica del RAG (filtros, umbral, fallback, validación), no la calidad de la búsqueda.
La calidad con el modelo real se mide con `python rag.py calibrar`.
"""

import hashlib
import math
import re

from ombu.reglas import normalizar_texto

DIMENSIONES = 512
VACIAS = {"de", "la", "el", "los", "las", "un", "una", "y", "o", "a", "en", "que", "por", "para", "con",
          "se", "del", "al", "lo", "mi", "es", "no", "si", "me", "le", "su", "como", "hay", "son"}


class EmbeddingsDePrueba:
    nombre = "prueba-bolsa-de-palabras"

    def vectorizar(self, textos: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in textos]

    def _vector(self, texto: str) -> list[float]:
        v = [0.0] * DIMENSIONES
        for palabra in re.findall(r"[a-z0-9]+", normalizar_texto(texto)):
            if palabra in VACIAS:
                continue
            v[int(hashlib.md5(palabra[:5].encode()).hexdigest(), 16) % DIMENSIONES] += 1
        norma = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norma for x in v]
