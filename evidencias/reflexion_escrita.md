# Entregable 4 — Reflexión escrita

**Pregunta:** ¿Qué parte de este proceso fue automatización pura y qué parte requirió que el agente usara criterio? Justifique con un ejemplo de sus propias 3 historias.

**Límite:** 150 palabras.

---

**Automatización pura.** Las etapas de anonimización y escritura fueron automáticas. En REG-P02 se borraron nombre, cédula, dirección y teléfono. No hizo falta criterio porque la regla es siempre la misma para cualquier paciente: identifica los campos personales y los elimina, sin interpretar nada del caso.

**Criterio.** La clasificación sí lo necesitó. En REG-P01 la presión era 158/96, pero el agente no dijo "hipertensión confirmada" porque había una sola medición: puede estar elevada por estrés o "efecto bata blanca", y el diagnóstico exige lecturas elevadas repetidas. Además, para decidir el nivel de riesgo combinó el antecedente del padre, el hábito de fumar y los demás datos clínicos.

**Conclusión.** Una regla sirve cuando la tarea es repetitiva y predecible, con la misma acción para cualquier caso; hace falta un agente cuando hay que interpretar información incompleta, combinar varios datos y ponderarlos según el contexto.
