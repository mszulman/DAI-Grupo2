# DAI-Grupo2
Microcredencial

A.1 — El caso
Administración Ombú administra 38 consorcios en CABA, unas 1.900 unidades funcionales. Propietarios, inquilinos y encargados escriben por un WhatsApp único y por mail, y llegan unos 250 mensajes por día. En esos mensajes se mezclan reclamos de mantenimiento, consultas sobre expensas, reservas del SUM y trámites administrativos. Hoy tres administrativos leen cada mensaje y lo clasifican a mano. Después buscan los datos en el sistema de liquidación de expensas y en la planilla de reclamos, derivan a proveedores y responden. El proceso que queremos mejorar es la pre-atención: interpretar el mensaje, detectar qué pide y con qué urgencia, y responder con datos reales.

Ejemplo real del tipo de mensaje que reciben:
"Hola, soy del 4°B de Tipas 1450. Hace 3 días que no anda el ascensor y ya avisé. Además me vino la expensa de octubre re alta, ¿por qué? ¿La puedo pagar en dos cuotas sin recargo?"

Un solo mensaje trae tres intenciones: un reclamo con posible urgencia, una consulta sobre la liquidación y un pedido de facilidad de pago. También trae una identificación informal de la unidad, sin número de UF.

-------------

Integrantes
- Jasan, David
- Szulman, Matias

-------------

A.3 — Aplicación de los 4 criterios de viabilidad
Valor:	¿Ahorra tiempo, dinero o reduce errores?
  Alto. Son ~250 mensajes por día y cada uno lleva 3–5 minutos entre leer, clasificar, buscar datos y responder: unas 15–20 horas diarias de trabajo administrativo. La demora típica es de 24–48 h, y los reclamos urgentes (pérdidas de agua, olor a gas, ascensor detenido) quedan enterrados entre consultas de rutina. Eso genera riesgo para los vecinos y conflictos con los consejos de propietarios.
Factibilidad	¿Se puede resolver hoy sin inventar tecnología?
  Viable. Los LLM actuales extraen intenciones y entidades (unidad, rubro, urgencia) de mensajes informales en español rioplatense. El resto es software convencional: consultar el sistema de expensas, leer la planilla de reclamos, validar la unidad contra el padrón y aplicar reglas de prioridad.
Disponibilidad de datos	¿Hay información real sobre la que trabajar?
  Disponibles, pero desordenados. Hay liquidaciones mensuales por consorcio (PDF/planilla), un registro de reclamos (planilla compartida), el padrón de UF con titulares, los reglamentos de copropiedad y las actas de asamblea (PDF, uno por edificio) y el listado de proveedores. Además, el historial de WhatsApp sirve para armar un lote de prueba realista.
Riesgo	¿Qué pasa si se equivoca?	Moderado, y crítico en dos puntos.
  (1) Si clasifica como rutina una emergencia (gas, agua, electricidad), puede haber daño físico: crítico.
  (2) Si informa una deuda o un monto incorrecto, o promete una facilidad de pago inexistente, hay consecuencia económica y conflicto: alto. Una consulta mal respondida sobre horarios del SUM es tolerable. El riesgo es controlable si el LLM nunca decide: los montos salen siempre del sistema, las emergencias se detectan también con reglas deterministas (palabras clave) y escalan a una persona, y las facilidades de pago las aprueba un humano.
