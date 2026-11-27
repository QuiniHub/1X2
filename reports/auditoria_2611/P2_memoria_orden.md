# Auditoria 26/11 - paquete P2_memoria_orden

Familia unica: ordenar por la fecha en TEXTO o por el numero de jornada en vez de
por la fecha real. Todo pasa ahora por `cronologia_jornadas.py`.

## Arreglado

| Indice | Fichero | Que se hizo |
|---|---|---|
| 2, 28 | `modelo_metricas_1x2.py` | `iter_closed_matches` da `fecha_orden` siempre ISO (fecha real del partido o de la jornada) y excluye lo que no tiene fecha parseable. `build_dataset`, `rolling_backtest` y `build_prediction_state` recorren esa lista. Orden real ahora: J28...J76 (25/26) y despues J1...J24 (26/27); antes J61-76, J1-24 y al final J28-60 por dia de la semana. |
| 14, 35 | `memoria_autonoma_quiniela.py` | Cada registro lleva `fecha_iso`; `cerrar_perfil` ordena por fecha real (forma, racha y decay). `parse_fecha` ya no inventa el 1 de enero. |
| 15 | `memoria_autonoma_quiniela.py` | `normalizar()` repara mojibake antes de quitar acentos: desaparecen las claves `ba lgica`, `ta nez` y `rumana a`; el Betis vuelve a su perfil. |
| 33 | `memoria_autonoma_quiniela.py` | `cargar_predicciones` usa primero el snapshot pre-cierre (comprobando que es de la misma jornada real) y el espejo solo de respaldo. Cada jornada del historial guarda `origen_prediccion`. Hoy: 36 jornadas con snapshot, 4 con espejo. |
| 79, 201 | `memoria_autonoma_quiniela.py` | Rendimiento y estado por fecha real: ultima detectada J27, ultima cerrada J24 (antes 76/76); ultimas 8 = J17-J24 (antes J69-J76). Temporadas: 25/26 = J28-J76, 26/27 = J1-J27 (antes dic-2025 caia en 2024_2025). |
| 18 | `construir_memoria_ia.py`, `sincronizar_dinamicas_memoria.py` | `analizar_liga` aplica los partidos por fecha real (aplazados incluidos): Levante 4 sin ganar, igual que la oficial (antes 7). En la sincronizacion manda `data/clasificaciones_oficiales.json`. |
| 187, 225 | `sincronizar_dinamicas_memoria.py`, `construir_memoria_ia.py` | Fuera la ruta fija `temporadas/2025_2026`: se sincroniza el resumen de la temporada detectada y solo si el fichero declara esa temporada. `construir_memoria_ia` no escribe el resumen si los calendarios son de otra temporada. |
| 48 | `modelo_metricas_1x2.py` | `partidos_esta_temporada` se cuenta en `data/jornadas` por fecha real (hoy 336, antes 250 fijo por el recorte). El log-score lleva un bloque `ventana` que avisa de que es ventana movil. |
| 247 | `modelo_metricas_1x2.py` | Si falta sklearn/joblib y el artefacto existe, `load_trained_model` lanza `dependencias_no_disponibles (...)`; el motor lo publica como `error_cargando_modelo: ...` en vez de `artefacto_modelo_no_disponible`. |

## Segunda pasada (correcciones tras la revision independiente)

- **Indice 33, prediccion de otro partido** (`memoria_autonoma_quiniela.py`). El snapshot se
  emparejaba con el partido solo por `num`. Ahora `prediccion_es_del_partido` descarta la
  prediccion si algun nombre es de relleno (`Ganador Octavos 5`, `3o Grupo EFGIJ`,
  `F1 Hypermotion`) o si no coincide ninguno de los dos equipos; con uno basta, porque hay
  alias que no se reconocen (VPS / vaasa PS, Rep. Irlanda / Eire). En ese caso se usa el
  partido del espejo si es ese partido, y si no queda sin prediccion. En datos reales caen
  al espejo exactamente los 6 partidos senalados: J67 P14, J71 P2 y P5, J72 P1-P3. Ninguno
  se queda sin prediccion. Cada jornada del historial guarda
  `predicciones_de_respaldo_espejo` y `predicciones_descartadas_otro_partido`.
- **Espejo identificado solo por numero** (`memoria_autonoma_quiniela.py`). El espejo
  `data/predicciones/jornada_N.json` solo se usa si `cj.misma_jornada(espejo, jornada)`.
  Hoy pasan los 40 espejos; el caso que cierra es la J28 de la 26/27 contra el espejo de
  la J28 de la 25/26.
- **Jornada de liga sin fechas** (`construir_memoria_ia.py`). Ya no va la primera: hereda
  el ultimo dia del fin de semana de la jornada anterior con fecha (sin contar aplazados)
  y el numero la deja justo detras. Con los calendarios actuales no cambia nada (129 y
  162 jugados, todos con fecha).
- **`partidos_esta_temporada`** (`modelo_metricas_1x2.py`). Sigue contando los partidos
  cerrados de la temporada (336) y la fuente lo dice asi. Se anade
  `partidos_temporada_con_prediccion_del_cierre`: los cerrados que ademas tienen
  probabilidades en el snapshot pre-cierre, que es la muestra realmente evaluable.

## Cambio en la prediccion (J25, antes del mercado)

Ajuste de perfiles autonomos sobre una base neutra 45/28/27 (1/X/2), viejo -> nuevo:

- P1 Betis-Rayo: 49,6/27,4/23,0 (perfil de "Belgica") -> 48,2/28,0/23,8 (perfil del Betis). -1,4 al 1.
- P2 Malaga-Athletic: 45,7 -> 44,1 al 1. P11 Eibar-Burgos: 46,6 -> 44,9. P12 Granada-Ceuta: 45,7 -> 47,2.
- Resto: 0,5 puntos o menos.
- 47 de 410 perfiles cambian su `forma_5_ppp`.

Modelo entrenado (mismo artefacto, estado Elo/forma en orden real): cambio maximo
0,5 puntos (P2: 1 de 32,0 a 31,5); en Segunda, nada. Con peso 0,24 y el mercado a
0,85, el efecto en lo publicado es de decimas (P1: unas 0,2).

## Pendiente (no es de este paquete o necesita decision)

- `data/temporadas/2025_2026/resumen_temporada.json` sigue contaminado con datos 26/27.
  El codigo ya no lo toca; recuperar la version buena de git (anterior al 10/08/2026)
  o marcarlo como no fiable es decision de Marc.
- El artefacto del modelo se entreno con features en el orden viejo; el pipeline lo
  reentrena solo. Las cifras de `backtesting_rolling` (44,6 % / 1,066) cambiaran en el
  proximo ciclo: las actuales tenian fuga de futuro.
- Motor (`buscar_perfil_autonomo`): el empate de score sigue quedandose con el primero
  por orden alfabetico. Fuera de este paquete.
- `diagnostico_sistema` no alerta si `modelo_predictivo.activo` es False. Fuera de este paquete.
- Los espejos de jornadas cerradas se siguen reescribiendo (resolver_competiciones,
  ajustar_aprendizaje_elige8). Fuera de este paquete; la memoria ya no los prefiere.

## Tests

`python -m unittest tests.test_aud_P2_memoria_orden_cronologia` (27 tests nuevos). De los
21 de la primera pasada, contra los modulos de HEAD: 11 fallan, 8 dan error (la funcion no
existia), 1 pasa (`test_sin_dependencias_y_sin_artefacto_devuelve_none`, guarda de no
regresion) y 1 depende de `data/jornadas` real y se salta si no existe. Los 6 de la
segunda pasada usan funciones que no existian antes de este arreglo. Tambien en verde: test_memoria_autonoma_quiniela,
test_modelo_metricas_1x2, test_metricas_logscore, test_metricas_rps,
test_dinamicas_orden_cronologico, test_construir_memoria_ia, test_auditoria_16_11,
test_diario_jornada_no_jugada, test_cronologia_jornadas.

No se ha regenerado ningun fichero de `data/`: lo hara el pipeline.
