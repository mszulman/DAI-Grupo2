# Entrega 2 — Primer Prototipo Operativo

**Caso:** Asistente de reclamos de mantenimiento para Administración Ombú (administradora de consorcios)
**Microcredencial #2 — Diseño de Aplicaciones Inteligentes · Instituto de Tecnología ORT**

---

## Parte A — Prompt versionado

### A.1 — Técnica de prompting: few-shot

Elegimos **few-shot** con cinco ejemplos, uno por cada intención salvo `EMERGENCIA` (esa la frena antes un filtro determinista). El prompt v1 ([prompts/extraccion_v1.txt](prompts/extraccion_v1.txt)) los incluye.

**Por qué funciona para nuestro caso:**

1. **Las fronteras entre intenciones de reclamos son finas y dependen del español rioplatense.** *"¿Qué onda con lo de la humedad? Sigo igual"* es `ESTADO_RECLAMO`, pero *"por el reclamo 3021: ahora también gotea en la cocina"* es `AMPLIAR_RECLAMO`, porque agrega información. *"Tuve que llamar yo al cerrajero, ¿me lo descuentan?"* describe un problema, pero según la Matriz es `SOLICITUD_REINTEGRO`, que tiene riesgo **ALTO** y nunca se resuelve sola. Equivocarse en esas fronteras cambia la acción del backend y el riesgo, así que preferimos mostrarlas con ejemplos y no solo con definiciones.
2. **Hay campos que el modelo tiene que inferir, no copiar.** El `rubro` ("se llueve el techo" → `agua`) y la `ubicacion` ("el pasillo del segundo piso" → `espacio_comun`) no aparecen literalmente en el mensaje. Los ejemplos muestran el criterio esperado.
3. **La normalización de la unidad es informal.** Los vecinos escriben "4°B", "PB A", "planta baja A" o "el 2 C". Los ejemplos "2°C" → `"2C"` y "PB A de Tipas" → `"PBA"` fijan el formato que después valida el contrato.

Además, cada ejemplo funciona como **test de regresión**: si una versión futura del prompt hace fallar uno de ellos, el cambio rompió algo.

**Evidencia (comparación con zero-shot):** para no justificar la técnica con una falla que nunca probamos, armamos también una versión **v0 zero-shot** ([prompts/extraccion_v0.txt](prompts/extraccion_v0.txt)). Es el mismo prompt, palabra por palabra, sin la sección de ejemplos. Corremos el lote de la Parte C con las dos versiones y comparamos.
