# Quiniela IA Pro

Motor predictivo de quinielas de futbol con aprendizaje autonomo por jornada.

Ver [DECISION_LOG.md](DECISION_LOG.md) para el porque de las decisiones tecnicas
importantes (que no son obvias leyendo solo el codigo).

---

## Que hace este sistema

Genera una prediccion 1X2 para cada jornada de La Quiniela combinando:

- datos reales de resultados, clasificaciones y jornadas
- contexto competitivo por equipo (necesidad de puntos, dinamica, objetivos)
- memoria historica de quinielas jugadas y resultados
- capa predictiva entrenable con baseline Elo/Poisson y modelo scikit-learn
- datos profesionales opcionales (cuotas, bajas, alineaciones)
- logica quinielista para fijos, dobles, triples y Elige 8

El sistema **no predice la siguiente jornada mientras la actual este en juego**.
Una vez cerrada la jornada, consolida los resultados, aprende de los errores
y genera la prediccion para la siguiente.

---

## Estructura del flujo

El workflow de GitHub Actions tiene el cron configurado a cada 30 minutos,
pero GitHub Actions lo ejecuta en la practica cada 1-4 horas segun su propia
carga (el cron es una peticion, no una garantia):

```
.github/workflows/main.yml
  -> python actualizar_todo.py
```

`actualizar_todo.py` ejecuta los ~60 scripts activos en orden. Solo dos son
criticos (`motor_prediccion_objetivo.py` y `validar_publicacion_autonoma.py`):
si fallan, paran todo el proceso. El resto son tolerantes — si uno falla, se
registra un `AVISO` y se continua con el siguiente, para no bloquear toda la
actualizacion por una fuente externa caida. Para que un fallo tolerado no
pase desapercibido para siempre, `actualizar_todo.py` lleva la cuenta de
fallos consecutivos por script (`data/diagnostico_fallos_cronicos.json`) y
lanza un `ALERTA_FALLO_CRONICO` bien visible en el log a partir de 3 fallos
seguidos.

Antes de actualizar datos se ejecutan los tests:

```
python -m unittest discover -s tests
```

---

## Competiciones activas

| Competicion | Estado |
|---|---|
| Ligas europeas (segun quiniela) | Activo segun jornada |
| Primera Division 2026/2027 | Pendiente inicio agosto 2026 |
| Segunda Division 2026/2027 | Pendiente inicio agosto 2026 |

El Mundial 2026 se retiro por completo del sistema (pestana, datos y scripts)
el 1 de julio de 2026: el proyecto se reorienta a la Liga 2026/2027. Cuando
empiece, el sistema inicializara automaticamente las tablas clasificatorias
y el calendario de Primera y Segunda.

---

## Scripts activos principales

### Datos base
- `actualizar_jornadas_detalle.py` — detalle de jornadas y partidos
- `actualizar_resultados_directo.py` — resultados oficiales
- `actualizar_clasificaciones_oficiales.py` — clasificaciones de ligas
- `actualizar_ligas_football_data.py` — datos de ligas externas
- `actualizar_contexto_equipos.py` — contexto competitivo por equipo: busca bajas/lesiones/sanciones/dudas por equipo en Google News RSS (principal) con Bing News RSS como respaldo gratuito si Google no da resultados; sus alertas ajustan probabilidades en el motor
- `actualizar_analisis_ia.py` — analisis IA por partido
- `actualizar_aprendizaje_ia.py` — aprendizaje por jornada

### Memoria e inteligencia
- `construir_memoria_ia.py` — memoria global de aprendizaje
- `memoria_autonoma_quiniela.py` — memoria persistente de quinielas
- `generar_contexto_competitivo.py` — contexto competitivo global
- `aprender_patrones_competitivos.py` — patrones aprendidos por competicion
- `alimentar_sorpresas_mercado.py` — memoria de casos donde el motor predijo FIJO y fallo
- `ajustar_aprendizaje_elige8.py` — aprendizaje de aciertos/fallos del Elige 8
- `construir_memoria_historica_profunda.py` — resumen dinamico (pesos, fallos, estado real de la jornada) para el contexto del chat IA

### Motor predictivo
- `motor_prediccion_quiniela.py` — nucleo de prediccion 1X2 (motor principal)
- `modelo_metricas_1x2.py` — capa entrenable Elo/Poisson + scikit-learn
- `alinear_boleto_con_analisis.py` — asignacion de fijos/dobles/triples
- `aplicar_elige8_seguro.py` — seleccion de Elige 8
- `generar_estado_vivo_ia.py` — estado vivo para la web

### Datos profesionales (opcionales)
- `datos_profesionales.py` — cuotas, bajas, alineaciones
- `actualizar_datos_profesionales.py` — carga desde secrets o esqueleto

Configuracion via GitHub Secrets/Vars:
- `QUINIHUB_PRO_DATA_URL` — endpoint con datos profesionales
- `QUINIHUB_PRO_DATA_TOKEN` — token bearer opcional
- `QUINIHUB_PRO_DATA_PROVIDER` — proveedor (ej: `api_football`)
- `QUINIHUB_PRO_DATA_LEAGUES` — ligas activas
- `QUINIHUB_PRO_DATA_SEASON` — temporada

Si los secrets no existen, el workflow no falla: genera un esqueleto auditable.

### Premios
- `calcular_premios.py` — calcula y persiste premios por jornada cerrada
  - Salida: `data/premios/historial_premios.json`
  - Campos: jornada, aciertos, fallos, premio_eur, fuente_premio, origen_prediccion, boleto
  - Si no hay dato oficial disponible, premio queda como 0.0 EUR y fuente como `pendiente`
  - Prioriza siempre `data/quinielas_jugadas.json` (lo realmente jugado y confirmado)
    sobre la predicción cruda del motor para contar aciertos. Si un registro ya
    guardado no viene de ahí pero la jugada real llega despues, se recalcula
    automáticamente en la siguiente ejecución (`puede_mejorarse_con_jugada_real`)
  - El cálculo multicolumna (dobles/triples) tiene límites de plausibilidad
    (5.000€ por columna, 20.000€ total): si el scrapeo de la tabla de premios
    devuelve un número irreal, se descarta y se revierte solo a pendiente

### Control de calidad
- `guardar_snapshot_prediccion.py` — foto pre-cierre de prediccion
- `backtesting_pre_cierre.py` — backtesting solo con snapshots validos
- `calibrar_probabilidades.py` — calibracion de probabilidades (Brier, log loss, por rango y competicion)
- `evaluar_valor_senales.py` — compara la precision real de los partidos con cada senal del motor activa (contexto competitivo/motivacion, datos profesionales de cuotas, refuerzo por sorpresas de mercado) frente a sin ella, usando solo snapshots pre-cierre inmutables. No concluye nada por debajo de 100 partidos con la senal activa. Salida: `data/memoria_ia/valor_de_senales.json`, tambien consultable desde el chat IA.
- `diagnostico_sistema.py` — diagnostico del estado del sistema
- `control_calidad_actualizacion.py` — control de calidad del pipeline (estructura y datos base, sin afirmaciones sobre equipos o temporadas concretas)
- `validar_publicacion_autonoma.py` — valida publicacion antes de subir (unico paso, junto a `motor_prediccion_objetivo.py`, que puede parar todo el proceso)

### Herramientas manuales (no forman parte del pipeline automatico)
- `validar_esquema_datos.py` — valida sintaxis, ausencia de BOM y esquema minimo (claves y tipos, nunca valores) de los ~150 JSON de `data/`. Se ejecuta a mano; siempre en modo informe, nunca falla ni bloquea nada.

---

## Estrategia de boleto

El sistema decide la cobertura de cada partido:

| Tipo | Cuando se usa |
|---|---|
| **FIJO** | alta confianza, bajo riesgo de sorpresa |
| **DOBLE** | riesgo medio, dos signos plausibles |
| **TRIPLE** | alta incertidumbre, cubre los tres signos |

Los triples garantizan acierto en ese partido para Elige 8.
El Elige 8 se forma con los 8 partidos de mayor probabilidad de acierto.

---

## Memoria y aprendizaje

El aprendizaje es real y acumulativo. Despues de cada jornada cerrada:

1. Se compara la prediccion (snapshot pre-cierre) con los resultados oficiales
2. Se detectan errores por tipo: empate infravalorado, sorpresa no detectada, etc.
3. Se actualiza la memoria con patrones nuevos
4. Se genera un resumen de aprendizaje de la jornada
5. Se ajustan pesos dinamicos para la siguiente prediccion

La memoria se divide en:
- **transferible**: patrones utiles para cualquier equipo o competicion
- **no transferible**: habitos especificos de equipos o contextos concretos

---

## Tests

Los tests se ejecutan antes de cada actualizacion automatica:

```
python -m unittest discover -s tests
```

Cobertura actual: jornadas, resultados, prediccion, boleto, Elige 8,
datos profesionales, memoria, compuerta, control de calidad y premios.
Incluye tambien tests de calidad matematica sobre la ultima prediccion real
(`test_calidad_prediccion.py`: probabilidades suman ~100, tipo coincide con
signo_final, Elige 8 tiene exactamente 8, coste coherente con dobles/triples)
y del mecanismo de alertas de fallo cronico (`test_alertas_fallo_cronico.py`).
`test_evaluar_valor_senales.py` prueba la logica de veredicto (ayuda/perjudica/
sin diferencia/sin muestra) y la extraccion real de cada senal desde el JSON
de snapshots pre-cierre.

---

## Dependencias

```
beautifulsoup4
lxml
joblib
numpy
pandas
requests
scikit-learn
```

---

## Estado del sistema

- Competicion activa: **ligas europeas segun jornada** (Mundial 2026 retirado el 1 jul 2026)
- Proxima transicion: **Liga 2026/2027** (agosto 2026)
- Workflow: cron cada 30 min, ejecucion real cada 1-4 horas segun GitHub Actions
- Premios: **automaticos si hay dato fiable, pendiente si no**
- Fallos no criticos: tolerados y avisados; alerta especial si un script lleva 3+ ejecuciones seguidas fallando
