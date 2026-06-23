# Quiniela IA Pro

Motor predictivo de quinielas de futbol con aprendizaje autonomo por jornada.

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

El workflow de GitHub Actions ejecuta cada 30 minutos:

```
.github/workflows/main.yml
  -> python actualizar_todo.py
```

`actualizar_todo.py` ejecuta los scripts activos en orden y falla si uno rompe,
evitando actualizaciones silenciosas con datos incompletos.

Antes de actualizar datos se ejecutan los tests:

```
python -m unittest discover -s tests
```

---

## Competiciones activas

| Competicion | Estado |
|---|---|
| Mundial 2026 | Activo |
| Ligas europeas (segun quiniela) | Activo segun jornada |
| Primera Division 2026/2027 | Pendiente inicio agosto 2026 |
| Segunda Division 2026/2027 | Pendiente inicio agosto 2026 |

Cuando empiece la liga 2026/2027, el sistema inicializara automaticamente
las tablas clasificatorias y el calendario de Primera y Segunda.

---

## Scripts activos principales

### Datos base
- `actualizar_jornadas_detalle.py` — detalle de jornadas y partidos
- `actualizar_resultados_directo.py` — resultados oficiales
- `actualizar_clasificaciones_oficiales.py` — clasificaciones de ligas
- `actualizar_ligas_football_data.py` — datos de ligas externas
- `actualizar_contexto_equipos.py` — contexto competitivo por equipo
- `actualizar_analisis_ia.py` — analisis IA por partido
- `actualizar_aprendizaje_ia.py` — aprendizaje por jornada

### Memoria e inteligencia
- `construir_memoria_ia.py` — memoria global de aprendizaje
- `memoria_autonoma_quiniela.py` — memoria persistente de quinielas
- `generar_contexto_competitivo.py` — contexto competitivo global
- `generar_memoria_mundial_2026.py` — memoria especifica Mundial 2026
- `aprender_patrones_competitivos.py` — patrones aprendidos por competicion

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
  - Campos: jornada, aciertos, fallos, premio_eur, fuente_premio, boleto
  - Si no hay dato oficial disponible, premio queda como 0.0 EUR y fuente como `pendiente`

### Control de calidad
- `guardar_snapshot_prediccion.py` — foto pre-cierre de prediccion
- `backtesting_pre_cierre.py` — backtesting solo con snapshots validos
- `calibrar_probabilidades.py` — calibracion de probabilidades
- `diagnostico_sistema.py` — diagnostico del estado del sistema
- `control_calidad_actualizacion.py` — control de calidad del pipeline
- `validar_publicacion_autonoma.py` — valida publicacion antes de subir

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

## Copia de seguridad

Antes del refactor estructural de junio 2026:

```
git checkout backup/pre-refactor-auditoria-total
```

---

## Estado del sistema

- Competicion activa: **Mundial 2026**
- Proxima transicion: **Liga 2026/2027** (agosto 2026)
- Workflow: **automatico cada 30 minutos**
- Premios: **automaticos si hay dato fiable, pendiente si no**
