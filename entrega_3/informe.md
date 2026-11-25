# Entrega 3 — Workflow + RAG + Agente

**Caso:** Asistente de reclamos de mantenimiento para Administración Ombú (administradora de consorcios)
**Microcredencial #2 — Diseño de Aplicaciones Inteligentes · Instituto de Tecnología ORT**

> Este informe continúa el de la [Entrega 2](../entrega_2/informe.md). La Parte A convierte el componente de extracción en un **workflow** que recorre el journey completo de un reclamo (adenda de la [Entrega 1](../entrega_1/informe.md), B.2 v2). Las Partes B (RAG) y C (agente) se completan en las Clases 5 y 6.

---

## Parte A — Workflow encadenado (Hito 1)

### A.1 — El workflow

El workflow está en [ombu/workflow.py](ombu/workflow.py) y se corre con [workflow.py](workflow.py). Está escrito en Python directo: con una secuencia fija, un framework no agrega mucho, y la consigna lo permite. **El orden de los pasos lo fija el desarrollador**; el LLM interviene solo en los pasos 4 (interpretar) y 9 (redactar), y nunca decide qué paso sigue. Esa es la diferencia con el agente de la Parte C.

Cumple los tres mínimos de la consigna:

| Mínimo | Cómo se cumple |
|---|---|
| **3+ pasos en secuencia** | 11 pasos: recepción → filtro de emergencias → padrón → interpretar (LLM) → validar → buscar reclamo → registrar / ampliar / informar → decisión humana (reintegros) → redactar (LLM) → validar la salida → enviar |
| **Validación en código con lógica del dominio** | Varias, ninguna en el LLM: la unidad tiene que estar vinculada al teléfono del vecino; un reclamo citado tiene que existir y ser de su unidad o de un espacio común de su edificio; los duplicados se detectan por edificio + rubro + estado; la prioridad se calcula con reglas; la respuesta redactada se valida antes de enviarla |
| **Punto de control donde el flujo se detiene** | `REVISION_HUMANA` (paso 5 o 6) cuando algo no es confiable; `PEDIR_ACLARACION` cuando la unidad es ambigua; `EMERGENCIA_ESCALADA` antes del LLM; `REINTEGRO_EN_EVALUACION`, donde decide una persona |

**Qué se suma respecto de la Entrega 2:**

- **Un registro de reclamos** ([ombu/registro.py](ombu/registro.py)) con sus operaciones clasificadas como **sensores** (buscar duplicado, buscar por número, reclamos visibles: solo leen) y **actuadores** (registrar, sumar aviso, agregar nota: escriben). Es la "base de datos que es la autoridad": el número de reclamo y su estado salen de acá, nunca del modelo. El workflow lo **recibe** en lugar de construirlo (inyección de dependencias), así los tests usan un registro propio y el archivo `datos/reclamos.json` nunca se modifica.
- **La prioridad por reglas** (`calcular_prioridad` en [ombu/reglas.py](ombu/reglas.py)): ALTA para gas, ascensor o falta de un servicio básico; MEDIA para espacios comunes y para agua, electricidad o estructura; BAJA para el resto.
- **El redactor** ([ombu/redactor.py](ombu/redactor.py), [prompts/redaccion_v1.txt](prompts/redaccion_v1.txt)): el LLM recibe un JSON con el resultado ya resuelto y solo lo pone en palabras. Recibe lo mínimo: el número y el estado del reclamo, nunca las notas internas (pueden nombrar a otras unidades).
- **La validación de la salida** (`validar_salida`, paso 10): antes de enviar, el código controla que la redacción mencione el número de reclamo correcto y ningún otro, y que no tenga montos, fechas, días de visita, depósitos ni nada "aprobado". Si falla, se envía una **plantilla fija**. Lo mismo pasa si no hay key o la API falla: el resultado ya está resuelto y se puede comunicar igual.
- **Los patrones de emergencia nuevos** ("adentro del ascensor", "no puede salir"): es la conclusión de la reflexión de la Entrega 2. Ahora el caso que solo había detectado el LLM lo frena el filtro.

### A.2 — Diagrama del workflow

```mermaid
flowchart TD
    M([Mensaje + teléfono]) --> P1[1 · ¿El mensaje tiene texto?]:::regla
    P1 -->|no| RH1[REVISION_HUMANA]:::control
    P1 --> P3[3 · Filtro de emergencias]:::regla
    P3 -->|coincide| EM[EMERGENCIA_ESCALADA<br/>respuesta fija, sin LLM]:::control
    P3 --> P2[2 · ¿Teléfono en el padrón?]:::regla
    P2 -->|no| RH2[REVISION_HUMANA]:::control
    P2 --> P4[4 · Interpretar el mensaje]:::llm
    P4 --> P5[5 · Validar contrato y unidad]:::regla
    P5 -->|JSON inválido o unidad ajena| RH3[REVISION_HUMANA]:::control
    P5 -->|vecino con varias unidades| AC[PEDIR_ACLARACION]:::control
    P5 -->|EMERGENCIA| EM
    P5 --> R{Enrutar por intención}:::regla
    R -->|FUERA_DE_ALCANCE| DE[DERIVADO<br/>respuesta fija]
    R -->|NUEVO_RECLAMO| D6[6 · ¿Hay un reclamo abierto igual?<br/>sensor]:::tool
    D6 -->|sí| SA[7 · Sumar aviso<br/>actuador]:::tool
    D6 -->|no| PR[7 · Calcular prioridad]:::regla --> RG[7 · Registrar reclamo<br/>actuador]:::tool
    R -->|AMPLIAR o ESTADO| B6[6 · Buscar el reclamo citado<br/>o del vecino · sensor]:::tool
    B6 -->|no existe, ajeno o resuelto| RH4[REVISION_HUMANA]:::control
    B6 -->|ampliar| AN[7 · Agregar nota<br/>actuador]:::tool
    B6 -->|estado| ES[Estado real del reclamo]
    R -->|SOLICITUD_REINTEGRO| H8[8 · Decide una persona]:::humano
    SA & RG & AN & ES & H8 & AC --> P9[9 · Redactar la respuesta]:::llm
    P9 --> P10[10 · Validar la salida]:::regla
    P10 -->|inventó un dato| PL[Plantilla fija]
    P10 -->|OK| P11([11 · Enviar y registrar])
    PL --> P11

    classDef llm fill:#dbeafe,stroke:#2563eb
    classDef regla fill:#f3f4f6,stroke:#6b7280
    classDef tool fill:#fef3c7,stroke:#d97706
    classDef humano fill:#fce7f3,stroke:#db2777
    classDef control fill:#fee2e2,stroke:#dc2626
```

Referencias: **azul** = LLM · **gris** = regla en código · **amarillo** = herramienta sobre el registro (sensor o actuador) · **rosa** = decisión humana · **rojo** = punto de control donde el flujo se detiene.

### A.3 — Prueba de falla controlada

Corrido contra **Gemini `gemini-3.5-flash` (API real) el 25/11/2026**, con el lote [datos/lote_workflow.json](datos/lote_workflow.json): 10 casos, cada uno con su estado esperado. La corrida completa, con la traza y la respuesta de cada caso, está en [salidas/workflow_20261125-111145.json](salidas/workflow_20261125-111145.json).

**Resultado: los 10 casos terminaron en el estado esperado**, y las 7 respuestas redactadas por el LLM pasaron la validación de salida (ninguna necesitó la plantilla de respaldo).

| # | Caso | Estado esperado | Estado obtenido | Dónde terminó el flujo |
|---|---|---|---|---|
| 1 | Reclamo nuevo (humedad en el living) | `RECLAMO_REGISTRADO` | `RECLAMO_REGISTRADO` ✅ | Paso 11. Reclamo N° 3051, prioridad MEDIA por reglas |
| 2 | Duplicado (ascensor) | `AVISO_SUMADO` | `AVISO_SUMADO` ✅ | Paso 11. Aviso sumado al N° 3044, sin crear un reclamo nuevo |
| 3 | Consulta de estado (filtración) | `ESTADO_INFORMADO` | `ESTADO_INFORMADO` ✅ | Paso 11. Informó N° 3021 "en curso" |
| 4 | Ampliar reclamo citado | `RECLAMO_AMPLIADO` | `RECLAMO_AMPLIADO` ✅ | Paso 11. Nota agregada al N° 3050 |
| **5** | **Falla: reclamo ajeno** | `REVISION_HUMANA` | `REVISION_HUMANA` ✅ | **Paso 6.** El N° 3050 es de otro edificio |
| **6** | **Falla: unidad ajena** | `REVISION_HUMANA` | `REVISION_HUMANA` ✅ | **Paso 5.** El 7A no está vinculado al teléfono |
| 7 | Ambiguo (dos unidades) | `PEDIR_ACLARACION` | `PEDIR_ACLARACION` ✅ | Paso 5. Pidió elegir entre 2A de Tipas 1450 y 7C de Ceibo 880 |
| 8 | Reintegro con manipulación | `REINTEGRO_EN_EVALUACION` | `REINTEGRO_EN_EVALUACION` ✅ | Paso 8, decisión humana |
| 9 | Emergencia (persona en el ascensor) | `EMERGENCIA_ESCALADA` | `EMERGENCIA_ESCALADA` ✅ | **Paso 3**, antes del LLM |
| 10 | Fuera de alcance (expensas) | `DERIVADO` | `DERIVADO` ✅ | Enrutamiento, respuesta fija |

**Los dos casos de falla controlada:**

- **Caso 5 — reclamo ajeno.** El vecino del 4°B de Tipas 1450 preguntó por el reclamo N° 3050, que es del palier de Ceibo 880. El LLM lo interpretó bien (`ESTADO_RECLAMO`, número `3050`) y la unidad del vecino era válida, pero en el **paso 6** el código comprobó que ese reclamo no es de su unidad ni de su edificio y **detuvo el flujo**. No se llamó al redactor y la respuesta fue la fija de revisión humana: el vecino no recibió ningún dato del reclamo de otro edificio.
- **Caso 6 — unidad ajena.** El mensaje decía "soy del 7°A de Tipas 1450" desde un teléfono vinculado al 4°B. El LLM extrajo la unidad `7A` y en el **paso 5** la regla de privacidad detuvo el flujo (`NO_VINCULADA`). **No se registró ningún reclamo**: el próximo número libre siguió siendo el 3051.

**Lo que mostró la corrida real:**

- **La manipulación no pasó.** En el caso 8 ("ya está aprobado… confirmame la fecha del depósito"), el workflow se detuvo en la decisión humana. La respuesta del LLM no repitió el monto ni la fecha, y dijo que "la aprobación queda sujeta a su análisis y decisión". La validación la aceptó, porque no da nada por aprobado.
- **La privacidad se respetó en la redacción.** En el caso 3, la nota interna del reclamo nombra a la unidad 5B; como el redactor solo recibe el número y el estado, la respuesta no la mencionó.
- **La mejora de la Entrega 2 funcionó.** La emergencia del caso 9, que en la Entrega 2 solo había detectado el LLM, ahora la frena el filtro determinista en el paso 3.
- **Un detalle para mejorar:** en el caso 3 el LLM escribió el estado en Markdown (`**EN CURSO**`). En WhatsApp la negrita se escribe con un solo asterisco, así que el vecino vería los asteriscos. Queda para la próxima versión del prompt de redacción: pedir texto sin formato.
- **La validación de salida no se activó en esta corrida**, porque ninguna redacción inventó datos. Su comportamiento ante fechas, montos, aprobaciones y números de reclamo ajenos está cubierto por las pruebas automáticas ([tests/test_redactor.py](tests/test_redactor.py)).

Pruebas automáticas, sin API: `python -m pytest` → 94 pruebas, incluida una por cada caso del lote.

---

## Parte B — RAG: base de conocimiento vectorial (Clase 5)

> _Pendiente._

## Parte C — Agente con LangGraph (Clase 6 · Hito 2)

> _Pendiente._
