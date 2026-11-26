"""
La base de conocimiento del RAG: corpus → embeddings → ChromaDB.

RAG tiene dos momentos:

    [OFFLINE · una vez]  corpus/reglamento_ombu.json → embedding de cada documento → ChromaDB (en disco)
                         BaseConocimiento.indexar()

    [ONLINE · cada vez]  pregunta → embedding → los k más parecidos QUE CUMPLEN EL FILTRO → ¿superan el umbral?
                         BaseConocimiento.buscar()

El filtro es el FILTRADO HÍBRIDO: una condición exacta sobre los metadatos que se combina con la
búsqueda por significado. Acá filtra dos cosas que la similitud no puede saber:
    - vigente = True   → nunca responder con una versión reemplazada de una política
    - edificio ∈ {TODOS, el edificio del vecino} → el reglamento de otro consorcio no le aplica
El edificio sale del PADRÓN (código), no de lo que el vecino escribe ni del LLM.

Los embeddings se calculan EN LA COMPU, sin API key, con un modelo entrenado en español
(jina-embeddings-v2-base-es, el mismo de la práctica de la Clase 5). La primera vez se descarga
(~640 MB) y queda guardado en ~/.cache/fastembed.

El modelo de embeddings se INYECTA: las pruebas usan uno de juguete (tests/test_rag.py) para no
depender de la descarga, igual que el workflow recibe el registro de reclamos.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional, Protocol

from .config import RAIZ_PROYECTO

MODELO_EMBEDDINGS = os.getenv("EMBEDDINGS_MODEL", "jinaai/jina-embeddings-v2-base-es")
CACHE_MODELOS = Path.home() / ".cache" / "fastembed"
CARPETA_INDICE = RAIZ_PROYECTO / "indice_chroma"     # derivado del corpus: está en el .gitignore
CORPUS = RAIZ_PROYECTO / "corpus" / "reglamento_ombu.json"
COLECCION = "reglamento_ombu"

K = 3                     # cuántos fragmentos se recuperan
UMBRAL_SIMILITUD = 0.43   # por debajo de esto: "No tengo información oficial sobre esa consulta."
# Calibrado con NUESTRO corpus (`python rag.py calibrar`, ver informe B.2). Con 0.35 (el valor de la
# cátedra) pasaban preguntas de afuera del corpus: "¿Puedo tener un perro?" sacaba 0.41. Las de adentro
# dan 0.46 o más, salvo el olor a gas (0.33), que nunca llega al RAG: lo frena antes el filtro de
# emergencias. Si se cambia el corpus o el modelo de embeddings, hay que recalibrarlo.

logging.getLogger("chromadb").setLevel(logging.ERROR)


class Embeddings(Protocol):
    """Lo único que la base necesita de un modelo de embeddings: texto → vector."""
    nombre: str

    def vectorizar(self, textos: list[str]) -> list[list[float]]: ...


class EmbeddingsLocales:
    """jina-embeddings-v2-base-es con fastembed: 768 números por texto, sin API key."""

    def __init__(self, modelo: str = MODELO_EMBEDDINGS):
        from fastembed import TextEmbedding   # import acá: solo se carga si se usa
        self.nombre = modelo
        self._modelo = TextEmbedding(modelo, cache_dir=str(CACHE_MODELOS))

    def vectorizar(self, textos: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._modelo.embed(textos)]


# ── Filtros (la parte "exacta" del filtrado híbrido) ─────────────────────────

def codigo_edificio(uf_id: str) -> str:
    """"TIP1450-4B" → "TIP1450". El código del consorcio es el prefijo de la unidad funcional."""
    return uf_id.split("-")[0]


def filtro_para(edificios: Optional[list[str]], solo_vigentes: bool = True) -> Optional[dict]:
    """
    Arma el `where` de ChromaDB.
        filtro_para(["TIP1450"]) → vigente = True  Y  edificio ∈ {TODOS, TIP1450}
        filtro_para(None, False) → sin filtro (solo para la demo de `rag.py buscar --todas`)
    """
    condiciones = []
    if solo_vigentes:
        condiciones.append({"vigente": True})
    if edificios is not None:
        condiciones.append({"edificio": {"$in": ["TODOS", *edificios]}})
    if not condiciones:
        return None
    return condiciones[0] if len(condiciones) == 1 else {"$and": condiciones}


# ── La base ──────────────────────────────────────────────────────────────────

def cargar_corpus(ruta: Path = CORPUS) -> list[dict]:
    """
    Cada documento del corpus ya es una unidad de sentido (una regla o una política): ese es el
    chunking. Cortar cada N caracteres partiría una regla por la mitad.
    """
    return json.loads(ruta.read_text(encoding="utf-8"))


class BaseConocimiento:
    def __init__(self, embeddings: Optional[Embeddings] = None, en_memoria: bool = False,
                 corpus: Path = CORPUS, umbral: float = UMBRAL_SIMILITUD):
        import chromadb
        from chromadb.config import Settings

        self.embeddings = embeddings or EmbeddingsLocales()
        self.corpus = corpus
        self.umbral = umbral
        ajustes = Settings(anonymized_telemetry=False)
        self._cliente = (chromadb.EphemeralClient(settings=ajustes) if en_memoria
                         else chromadb.PersistentClient(path=str(CARPETA_INDICE), settings=ajustes))
        self._coleccion = None

    def _huella(self) -> str:
        """Si cambia el corpus o el modelo de embeddings, cambia la huella y hay que volver a indexar."""
        return hashlib.sha256(self.corpus.read_bytes() + self.embeddings.nombre.encode()).hexdigest()[:16]

    # PASO OFFLINE
    def indexar(self) -> int:
        """Calcula el embedding de cada documento y lo guarda en ChromaDB. Devuelve cuántos guardó."""
        try:
            self._cliente.delete_collection(COLECCION)
        except Exception:
            pass   # no existía
        docs = cargar_corpus(self.corpus)
        self._coleccion = self._cliente.create_collection(
            COLECCION, embedding_function=None,      # los vectores los calculamos nosotros
            metadata={"hnsw:space": "cosine", "huella": self._huella(), "modelo": self.embeddings.nombre})
        self._coleccion.add(
            ids=[d["id"] for d in docs],
            documents=[d["descripcion_semantica"] for d in docs],      # lo que se convierte en vector
            embeddings=self.embeddings.vectorizar([d["descripcion_semantica"] for d in docs]),
            metadatas=[{"titulo": d["titulo"], "fuente": d["fuente"], **d["metadatos"]} for d in docs],
        )
        return len(docs)

    def abrir(self) -> "BaseConocimiento":
        """Usa el índice guardado si está al día; si no existe o el corpus cambió, indexa primero."""
        try:
            coleccion = self._cliente.get_collection(COLECCION)
            if (coleccion.metadata or {}).get("huella") == self._huella():
                self._coleccion = coleccion
                return self
        except Exception:
            pass   # todavía no existe
        print("  ⚙️  Indexando el corpus (paso OFFLINE: se hace una vez y queda en indice_chroma/)...")
        self.indexar()
        return self

    def documentos(self) -> list[dict]:
        if self._coleccion is None:
            self.abrir()
        datos = self._coleccion.get(include=["documents", "metadatas"])
        return [{"id": i, "texto": t, **m} for i, t, m in zip(datos["ids"], datos["documents"], datos["metadatas"])]

    # PASO ONLINE
    def buscar(self, consulta: str, k: int = K, filtro: Optional[dict] = None) -> list[dict]:
        """
        Devuelve los k candidatos más parecidos que cumplen el filtro, del más al menos parecido.
        Cada uno trae "similitud" (coseno, de 0 a 1) y "supera_umbral".
        """
        if self._coleccion is None:
            self.abrir()
        r = self._coleccion.query(query_embeddings=self.embeddings.vectorizar([consulta]),
                                  n_results=k, where=filtro, include=["documents", "metadatas", "distances"])
        candidatos = []
        for id_, texto, meta, distancia in zip(r["ids"][0], r["documents"][0], r["metadatas"][0], r["distances"][0]):
            similitud = round(1 - distancia, 2)      # ChromaDB devuelve distancia coseno = 1 - similitud
            candidatos.append({"id": id_, "texto": texto, **meta,
                               "similitud": similitud, "supera_umbral": similitud >= self.umbral})
        return candidatos


_base_por_defecto: Optional[BaseConocimiento] = None


def base_por_defecto() -> BaseConocimiento:
    """La base real (jina + índice en disco). El modelo tarda en cargar: se abre una sola vez."""
    global _base_por_defecto
    if _base_por_defecto is None:
        _base_por_defecto = BaseConocimiento().abrir()
    return _base_por_defecto
