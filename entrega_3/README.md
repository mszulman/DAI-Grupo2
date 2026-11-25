# Entrega 3 — Workflow + RAG + Agente (Administración Ombú)

El componente de la [Entrega 2](../entrega_2/) interpretaba **un mensaje suelto**. En la Parte A lo convertimos en un **workflow**: el journey completo de un reclamo (adenda de la [Entrega 1](../entrega_1/informe.md)), con un registro de reclamos, reglas de prioridad, puntos de control, la redacción de la respuesta y su validación.

En la Parte B el workflow suma una intención, `CONSULTA_REGLAMENTO`, que se responde con **RAG** sobre el reglamento de cada edificio y las políticas de reclamos de Ombú ([corpus/](corpus/)), filtrando por el edificio del vecino y por vigencia.

## Cómo correrlo

Desde esta carpeta (`entrega_3/`):

```bash
pip install -r requirements.txt
cp .env.example .env      # completar GEMINI_API_KEY (sin key corre en modo simulación)

python workflow.py             # los 13 casos del lote (11 a 13: consultas con RAG), con la traza
python workflow.py --caso 5    # un solo caso
python -m pytest               # pruebas sin API y sin descargar el modelo de embeddings
```

Parte B (RAG). La búsqueda usa embeddings **locales**, sin API key; la primera vez se descarga el modelo `jina-embeddings-v2-base-es` (~640 MB, queda en `~/.cache/fastembed`):

```bash
python rag.py indexar                                   # paso offline: corpus → ChromaDB (indice_chroma/)
python rag.py ver                                       # qué quedó guardado
python rag.py buscar "¿Puedo hacer venir al albañil un sábado?" --edificio CEI0880
python rag.py buscar "¿Puedo hacer venir al albañil un sábado?" --todas   # sin filtro
python rag.py preguntar "¿Cuánto tardan si se rompe el ascensor?" --edificio TIP1450
python rag.py calibrar                                  # similitudes dentro y fuera del corpus → umbral
python rag.py comparar                                  # B.3: sin grounding vs. con RAG (necesita la key)
```

## Estructura

```
entrega_3/
├── workflow.py               ← corre el lote del workflow y muestra la traza
├── rag.py                    ← Parte B: indexar, buscar, preguntar, calibrar y comparar
├── corpus/
│   └── reglamento_ombu.json  ← 14 documentos: políticas de Ombú y reglamentos de cada edificio
├── ombu/
│   ├── config.py, contrato.py, extractor.py   ← los de la Entrega 2 (pasos 1 a 5) + CONSULTA_REGLAMENTO
│   ├── llm.py                ← ahora con modo JSON (extraer) o texto (redactar)
│   ├── reglas.py             ← + patrones de emergencia nuevos, prioridad y validación de salida
│   ├── registro.py           ← registro de reclamos simulado: sensores y actuadores (nuevo)
│   ├── redactor.py           ← paso 9: el LLM redacta, con plantilla de respaldo (nuevo)
│   ├── workflow.py           ← la secuencia de pasos y los puntos de control (nuevo)
│   ├── base_conocimiento.py  ← Parte B: embeddings locales + ChromaDB + filtro híbrido
│   └── rag.py                ← Parte B: recuperar → umbral → responder → validar las citas
├── prompts/
│   ├── extraccion_v1.txt     ← el mismo prompt de la Entrega 2
│   ├── extraccion_v2.txt     ← + CONSULTA_REGLAMENTO (Parte B); es el que se usa
│   ├── redaccion_v1.txt      ← paso 9: "comunicá el resultado, no lo cambies"
│   ├── rag_v1.txt            ← Parte B: "usá ÚNICAMENTE los fragmentos… citá el código"
│   └── sin_grounding_v1.txt  ← Parte B: la misma pregunta sin contexto (para comparar)
├── datos/
│   ├── padron.json           ← teléfono → unidades (igual que en la Entrega 2)
│   ├── reclamos.json         ← el registro de reclamos simulado
│   ├── lote_workflow.json    ← 13 casos, cada uno con su estado esperado
│   ├── preguntas_calibracion.json  ← Parte B: preguntas dentro y fuera del corpus
│   └── preguntas_comparacion.json  ← Parte B: las preguntas de B.3
└── tests/                    ← contrato, registro, redactor, workflow y RAG
```

## Qué cambia respecto de la Entrega 2

| | Entrega 2 | Entrega 3 · Parte A |
|---|---|---|
| **Qué procesa** | Un mensaje: interpreta y valida | El reclamo completo, hasta la respuesta al vecino |
| **Llamadas al LLM** | 1 (interpretar) | 2: interpretar (JSON, temperatura 0) y redactar (texto, temperatura 0.3) |
| **Herramientas** | Ninguna | Registro de reclamos: sensores (buscar) y actuadores (registrar, sumar aviso, ampliar) |
| **Reglas** | Emergencias, padrón, unidad | + patrones de emergencia nuevos, prioridad, validación de la salida |
| **Resultado** | Extracción validada o error | Uno de 10 estados, con la traza de los pasos recorridos |
| **Humano** | No aparece | Revisión humana cuando algo no es confiable, y decisión humana en los reintegros |
