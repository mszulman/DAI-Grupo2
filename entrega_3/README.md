# Entrega 3 — Workflow + RAG + Agente (Administración Ombú)

El componente de la [Entrega 2](../entrega_2/) interpretaba **un mensaje suelto**. En la Parte A lo convertimos en un **workflow**: el journey completo de un reclamo (adenda de la [Entrega 1](../entrega_1/informe.md)), con un registro de reclamos, reglas de prioridad, puntos de control, la redacción de la respuesta y su validación.

## Cómo correrlo

Desde esta carpeta (`entrega_3/`):

```bash
pip install -r requirements.txt
cp .env.example .env      # completar GEMINI_API_KEY (sin key corre en modo simulación)

python workflow.py             # Parte A: los 10 casos del lote, con la traza de cada uno
python workflow.py --caso 5    # un solo caso
python -m pytest               # pruebas sin API
```

## Estructura

```
entrega_3/
├── workflow.py               ← Parte A: corre el lote del workflow y muestra la traza
├── ombu/
│   ├── config.py, contrato.py, extractor.py   ← igual que en la Entrega 2 (pasos 1 a 5)
│   ├── llm.py                ← ahora con modo JSON (extraer) o texto (redactar)
│   ├── reglas.py             ← + patrones de emergencia nuevos, prioridad y validación de salida
│   ├── registro.py           ← registro de reclamos simulado: sensores y actuadores (nuevo)
│   ├── redactor.py           ← paso 9: el LLM redacta, con plantilla de respaldo (nuevo)
│   └── workflow.py           ← la secuencia de pasos y los puntos de control (nuevo)
├── prompts/
│   ├── extraccion_v1.txt     ← el mismo prompt de la Entrega 2
│   └── redaccion_v1.txt      ← paso 9: "comunicá el resultado, no lo cambies"
├── datos/
│   ├── padron.json           ← teléfono → unidades (igual que en la Entrega 2)
│   ├── reclamos.json         ← el registro de reclamos simulado
│   └── lote_workflow.json    ← 10 casos, cada uno con su estado esperado
└── tests/                    ← contrato, registro, redactor y workflow
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
