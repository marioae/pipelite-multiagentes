# Comparación contra el oráculo de referencia

Sección 10.1 del documento de arquitectura: las 12 filas ya llenas de
`Formulario_Salida_Vitalis.xlsx` se usan como set de referencia, **no como
respuesta exacta a igualar carácter por carácter**. Lo que se valida es que los
campos categóricos coincidan *o sean clínicamente defendibles*.

**Resultado: 48 de 60 comparaciones categóricas coinciden (80%).** Las 12
divergencias se detallan abajo, cada una con su justificación.

---

## Dos inconsistencias del propio material de clase

Antes de las divergencias por criterio, hay dos casos donde el
`Formulario_Salida` de referencia **contradice a las Historias de Prueba del
mismo paquete**. No son diferencias de opinión: son un conflicto interno del
material.

### 1. PAC-005 — la referencia dice `medio`, pero TC-12 exige `alto`

| Fuente | Valor |
|---|---|
| `Formulario_Salida_Vitalis.xlsx`, fila PAC-005 | `nivel_riesgo = medio` |
| `Historias_de_Prueba_Pipeline_Clinico.xlsx`, TC-12 | «Resultado esperado: `nivel_riesgo = 'alto'`, dado el antecedente cardiovascular y el control inadecuado» |

Un pipeline que reproduzca la fila de referencia **falla TC-12**. Se siguió el
caso de prueba, que además es el clínicamente correcto: hipertensión no
controlada (162/98 mmHg) en prevención secundaria tras un infarto es riesgo alto.

### 2. PAC-006 — la referencia afirma un diagnóstico que TC-04 pide no afirmar

| Fuente | Valor |
|---|---|
| `Formulario_Salida_Vitalis.xlsx`, fila PAC-006 | `enfermedad_probable = artritis reumatoide`, `confianza = media` |
| `Historias_de_Prueba_Pipeline_Clinico.xlsx`, TC-04 | «…el campo `enfermedad_probable` **no afirma un diagnóstico definitivo sin respaldo**» |

El texto de REG-06 tiene 2 semanas de evolución, sin reactantes de fase aguda,
sin factor reumatoide ni anti-CCP y sin imagen. Nombrar «artritis reumatoide»
ahí es exactamente lo que TC-04 pide evitar. Se declaró `indeterminado` con
`confianza = baja`.

---

## Divergencias por criterio clínico

### Precisión del diagnóstico (3 casos)

| Código | Referencia | Esta corrida | Razón |
|---|---|---|---|
| PAC-001 | diabetes tipo 2 | diabetes mellitus tipo 2 | Mismo diagnóstico, nomenclatura completa. Equivalente. |
| PAC-005 | hipertensión arterial | hipertensión arterial no controlada | El «no controlada» es la información accionable: ya está en tratamiento y no alcanza meta. |
| PAC-009 | asma | asma mal controlada | El propio texto dice «actualmente mal controlada». Omitirlo pierde el motivo de consulta. |

### Interpretación de `consumo_sustancias` (4 casos)

| Código | Referencia | Esta corrida | Razón |
|---|---|---|---|
| PAC-001 | No registrado | No | El texto dice explícitamente «Niega consumo de sustancias». Eso es un «No», no una ausencia de dato. |
| PAC-006 | No registrado | No | Ídem: «Niega consumo de sustancias». |
| PAC-011 | No registrado | No | Ídem: «Niega consumo de sustancias». |
| PAC-007 | Sí | No | El único consumo referido es café (más de 5 tazas/día). Para un formulario de seguimiento epidemiológico, la cafeína no equivale a consumo de sustancias; queda registrada en `antecedentes` y en `comportamiento_observado`. |

La distinción de fondo: **«No registrado» significa que el texto no dice nada al
respecto**; cuando el texto niega expresamente el consumo, el valor correcto es
«No». Tratar ambos igual destruye información en un formulario epidemiológico.

### Nivel de riesgo (1 caso adicional)

| Código | Referencia | Esta corrida | Razón |
|---|---|---|---|
| PAC-012 | bajo | medio | Paciente de 19 años con consumo diario de cannabis durante 8 meses, aislamiento social y caída del rendimiento académico. La posibilidad de un pródromo psicótico no descartado no es un escenario de riesgo bajo. |

### Confianza (1 caso adicional)

| Código | Referencia | Esta corrida | Razón |
|---|---|---|---|
| PAC-009 | media | alta | El asma ya está diagnosticada desde la infancia según el propio texto: no hay incertidumbre diagnóstica que justifique bajar la confianza. La incertidumbre está en el control, no en el diagnóstico. |

---

## Regla `indeterminado`: comparación

| | Referencia | Esta corrida |
|---|---|---|
| Casos marcados `indeterminado` | 5 (PAC-003, 004, 008, 010, 012) | 6 (los mismos 5 + PAC-006) |
| Todos con `confianza = baja` | Sí | Sí — forzado por el contrato, no por convención |

La sección 10.1 advierte: «Un pipeline que "acierta" diagnósticos pero nunca
produce `indeterminado` está violando la regla de negocio, no superándola».
Esta corrida produce uno más que la referencia, y en el caso donde el propio
TC-04 lo pide.

---

## Cómo reproducir esta comparación

```bash
python3 comparar_con_oraculo.py
```
