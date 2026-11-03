# DAI-Grupo2
Microcredencial

# Entrega 1 — Del Diagnóstico al Concepto de Solución

**Caso:** Asistente de pre-atención para Administración Ombú (administradora de consorcios)
**Microcredencial #2 — Diseño de Aplicaciones Inteligentes · Instituto de Tecnología ORT**

## Parte A — Diagnóstico y Ficha de Oportunidad (Clase 1)

### A.1 — El caso

**Administración Ombú** administra **38 consorcios** en CABA, unas **1.900 unidades funcionales**. Propietarios, inquilinos y encargados escriben por un **WhatsApp único** y por mail, y llegan unos **250 mensajes por día**. En esos mensajes se mezclan reclamos de mantenimiento, consultas sobre expensas, reservas del SUM y trámites administrativos. Hoy **tres administrativos** leen cada mensaje y lo clasifican a mano. Después buscan los datos en el sistema de liquidación de expensas y en la planilla de reclamos, derivan a proveedores y responden. El proceso que queremos mejorar es la **pre-atención**: interpretar el mensaje, detectar qué pide y con qué urgencia, y responder con datos reales.

Ejemplo real del tipo de mensaje que reciben:

> *"Hola, soy del 4°B de Tipas 1450. Hace 3 días que no anda el ascensor y ya avisé. Además me vino la expensa de octubre re alta, ¿por qué? ¿La puedo pagar en dos cuotas sin recargo?"*

Un solo mensaje trae **tres intenciones**: un reclamo con posible urgencia, una consulta sobre la liquidación y un pedido de facilidad de pago. También trae una identificación informal de la unidad, sin número de UF.

---

### A.2 — Evidencia de la necesidad (réplica de "El Proveedor Enojado")

**Modelo usado:** Gemini
**Fecha de la prueba:** 27/10/2026

**Prompt utilizado** (sin darle ninguna fuente de verdad):

```
Actuá como el sistema de atención de Administración Ombú, una administradora de consorcios de CABA.
Un usuario pregunta: 'Hola, soy del 4°B de Tipas 1450. Hace 3 días que no anda el ascensor y ya
avisé. Además me vino la expensa de octubre re alta, ¿por qué? ¿La puedo pagar en dos cuotas sin
recargo?'
Respondé como lo haría el sistema.
```

**Respuesta del modelo (copy-paste textual, sin editar):**

> Hola, buenas tardes. Tomamos conocimiento de tu consulta para el departamento **4° "B" de Tipas 1450**. A continuación, te respondemos punto por punto:
> 1. **Estado del ascensor:**
> Lamentamos mucho las molestias ocasionadas por la demora. Verificamos que el reclamo ya fue asentado y se encuentra derivado a la empresa conservadora asignada al edificio. En el transcurso del día nos contactaremos con el técnico de guardia para exigir prioridad de visita y te confirmaremos por esta vía el diagnóstico y la fecha estimada de reparación.
> 2. **Liquidación de expensas de octubre:**
> El incremento en el valor final respecto al mes anterior suele deberse a dos factores principales:
> * **Gastos comunes extraordinarios o reparaciones:** si se realizaron trabajos de mantenimiento edilicio, abonos no habituales o service mayor de instalaciones.
> * **Incrementos en el rubro laboral:** impacto de acuerdos paritarios de SUTERH (encargados de edificio), bonificaciones y cargas sociales correspondientes al período.
> Podés verificar el detalle ítem por ítem en la liquidación adjunta, en las columnas de **Gastos Ordinarios** y **Extraordinarios**. Si tenés dudas sobre algún comprobante puntual, indicanos el número de concepto para > detallártelo.
> 3. **Pago en dos cuotas:**
> De acuerdo con el Reglamento de Propiedad Horizontal del consorcio y los plazos de rendición de cuentas, las expensas deben abonarse en término para afrontar las obligaciones mensuales del edificio (sueldos, servicios y seguros).
> * **Sin recargo:** Solo pueden ingresarse pagos parciales antes del primer vencimiento oficial estipulado en la liquidación.
> * **Con saldo pendiente posterior al vencimiento:** Cualquier remanente cancelado con posterioridad devenga el interés resarcitorio aprobado en asamblea de propietarios.
> Si estás ante una situación particular, podés solicitar formalmente que elevemos tu pedido de plan de pago al Consejo de Propietarios para evaluar si autorizan una excepción sin punitorios.
> Quedamos a disposición para cualquier consulta adicional sobre el consorcio.

| # | Fragmento inventado | Qué dato real haría falta | Nivel de confianza con que lo presentó |
|---|---|---|---|
| 1 |Verificamos que el reclamo ya fue asentado y se encuentra derivado a la empresa conservadora asignada al edificio | Registro real de reclamos del consorcio | Alto |
| 2 | En el transcurso del día nos contactaremos con el técnico de guardia para exigir prioridad de visita y te confirmaremos por esta vía el diagnóstico y la fecha estimada de reparación | Agenda del proveedor de ascensores | Alto |
| 3 | se realizaron trabajos de mantenimiento edilicio, abonos no habituales o service mayor de instalaciones | Liquidación de octubre del consorcio | Alto |
| 4 | De acuerdo con el Reglamento de Propiedad Horizontal del consorcio y los plazos de rendición de cuentas, las expensas deben abonarse en término para afrontar las obligaciones mensuales del edificio (sueldos, servicios y seguros) | Reglamento de Propiedad | Alto |

> Elementos que suelen aparecer inventados: número de reclamo, plazo de reparación, nombre del proveedor, motivo del aumento, monto de la expensa, política de cuotas, intereses por mora.

**Qué le faltó al modelo para responder bien:**

- **Padrón de unidades:** para saber qué UF es "el 4°B de Tipas 1450" y si quien escribe es propietario o inquilino.
- **Registro de reclamos:** para saber si el reclamo del ascensor existe, en qué estado está y a qué proveedor se asignó.
- **Liquidación de expensas de octubre:** para conocer los rubros y la comparación con el mes anterior, que es lo que explica el aumento.
- **Reglamento y política de cobranza:** para saber si existen planes de pago y qué recargos aplican.
- **Herramientas:** el modelo no puede consultar ni registrar nada. Solo genera texto.

**Conclusión:** El modelo no falló por ser malo. Falló porque no tiene acceso a los datos reales del consorcio, y completó el vacío con información plausible presentada con total seguridad. En nuestro dominio, eso significa informar montos, plazos o facilidades de pago que no existen.

---

### A.3 — Aplicación de los 4 criterios de viabilidad

| Criterio | Pregunta | Respuesta aplicada a Administración Ombú |
|---|---|---|
| **Valor** | ¿Ahorra tiempo, dinero o reduce errores? | **Alto.** Son ~250 mensajes por día y cada uno lleva 3–5 minutos entre leer, clasificar, buscar datos y responder: unas **15–20 horas diarias** de trabajo administrativo. La demora típica es de 24–48 h, y los **reclamos urgentes** (pérdidas de agua, olor a gas, ascensor detenido) quedan enterrados entre consultas de rutina. Eso genera riesgo para los vecinos y conflictos con los consejos de propietarios. |
| **Factibilidad** | ¿Se puede resolver hoy sin inventar tecnología? | **Viable.** Los LLM actuales extraen intenciones y entidades (unidad, rubro, urgencia) de mensajes informales en español rioplatense. El resto es software convencional: consultar el sistema de expensas, leer la planilla de reclamos, validar la unidad contra el padrón y aplicar reglas de prioridad. |
| **Disponibilidad de datos** | ¿Hay información real sobre la que trabajar? | **Disponibles, pero desordenados.** Hay liquidaciones mensuales por consorcio (PDF/planilla), un registro de reclamos (planilla compartida), el padrón de UF con titulares, los **reglamentos de copropiedad** y las **actas de asamblea** (PDF, uno por edificio) y el listado de proveedores. Además, el historial de WhatsApp sirve para armar un lote de prueba realista. |
| **Riesgo** | ¿Qué pasa si se equivoca? | **Moderado, y crítico en dos puntos.** (1) Si clasifica como rutina una **emergencia** (gas, agua, electricidad), puede haber daño físico: **crítico**. (2) Si **informa una deuda o un monto incorrecto**, o promete una facilidad de pago inexistente, hay consecuencia económica y conflicto: **alto**. Una consulta mal respondida sobre horarios del SUM es **tolerable**. El riesgo es controlable si el LLM **nunca decide**: los montos salen siempre del sistema, las emergencias se detectan también con reglas deterministas (palabras clave) y escalan a una persona, y las facilidades de pago las aprueba un humano. |

**Ubicación en la matriz Valor × Factibilidad:** alto valor y alta factibilidad → ⭐ **Prioridad**.

---

### A.4 — Mapa inicial del sistema (seis piezas)

## Mapa inicial — Asistente de pre-atención de Administración Ombú

- **Usuario:** propietarios e inquilinos de las UF (escriben por WhatsApp o mail), encargados de edificio (reportan problemas) y el equipo administrativo de Ombú (recibe lo que el sistema escala).
- **Datos:** mensajes en lenguaje natural (texto, a veces con fotos), padrón de unidades y titulares, liquidaciones mensuales de expensas, registro de reclamos, reglamentos de copropiedad, actas de asamblea y listado de proveedores.
- **Modelo:** un LLM (por ejemplo Claude, GPT o Gemini) usado en dos momentos: **interpretar** el mensaje (intenciones, unidad, rubro, urgencia) y **redactar** la respuesta final a partir de datos ya validados.
- **Herramientas:** identificar la UF en el padrón, consultar el saldo y la liquidación de la unidad, consultar el estado de un reclamo, **registrar un reclamo nuevo**, consultar la disponibilidad del SUM, buscar en reglamentos y actas, y escalar a un administrativo.
- **Reglas:** la unidad tiene que existir en el padrón y quien escribe tiene que estar vinculado a ella; los montos y saldos salen **siempre** del sistema y nunca del modelo; las emergencias (gas, agua, electricidad, ascensor con personas) escalan a un humano de inmediato; no se otorgan planes de pago ni descuentos; no se informa la deuda de una unidad a quien no es su titular; las reservas del SUM respetan el reglamento del edificio.
- **Salida:** una respuesta en lenguaje natural con datos verificados (saldo, estado del reclamo, número de reclamo real), más la acción correspondiente: reclamo registrado, caso escalado o derivación a un administrativo.

---

### Ficha de oportunidad (resumen)

| Campo | Contenido |
|---|---|
| **Problema** | ~250 mensajes por día sin estructura, con intenciones mezcladas, se atienden a mano con 24–48 h de demora y las urgencias se pierden entre consultas de rutina. |
| **Usuario** | Propietarios, inquilinos y encargados (entrada); equipo administrativo de Ombú (beneficiario directo). |
| **Proceso actual** | Leer → clasificar → identificar la unidad → buscar en el sistema de expensas o la planilla de reclamos → derivar → responder. Todo manual. |
| **Intervención de IA** | Interpretar el mensaje y separar intenciones, extraer unidad, rubro y urgencia, y redactar la respuesta con datos reales. |
| **Valor esperado** | Respuesta inmediata a consultas de solo lectura, detección temprana de emergencias y liberación de horas administrativas. |
| **Riesgo principal** | Informar montos o condiciones de pago falsos, o no detectar una emergencia. Se mitiga con frontera regla/LLM y escalamiento humano. |

---
