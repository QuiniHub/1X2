# Auditoria 26/11 - paquete P3_aprendizaje

Estado: codigo corregido y probado con tests en directorios temporales. No se ha
ejecutado ningun script contra `data/` real ni contra la red; los JSON de `data/`
los regenera el pipeline en el siguiente ciclo. Sin commit (lo hace el coordinador).

Tests: `python -m unittest tests.test_aud_P3_aprendizaje_auditoria_2611` (47 tests, OK)
y los ya existentes de estos modulos (todos OK; se actualizo un test obsoleto de
`tests/test_alimentar_sorpresas_mercado.py` que exigia el comportamiento defectuoso).

## Arreglado

| Indice | Fichero | Que cambia |
|---|---|---|
| 13, 82 | actualizar_aprendizaje_ia.py | Jornada empezada o cerrada: manda el snapshot pre-cierre (validado como la misma jornada real). Sin snapshot, `data/predicciones` solo vale si no se genero despues del primer partido. La retroalimentacion de factores se reconstruye desde cero y usa la misma fuente. |
| 16 | ajustar_estado_vivo_motivacion.py | `lado` se compara con 'local'/'visitante' (las penalizaciones +22/-16/+24 estaban muertas) y la necesidad solo cuenta a falta de 10 jornadas o menos. |
| 17, 77, 121 | construir_memoria_historica_profunda.py | Fuera el filtro `num < 61`; premios por jugada real con temporada y fecha; patrones del chat leidos de `patrones_competitivos.json`; la "sorpresa" se apunta al visitante que gana; `temporadas_analizadas` calculadas. |
| 19 (parcial), 88 | generar_contexto_competitivo.py | Objetivo principal = el objetivo vivo mas cercano en puntos (el lider ya no sale con "permanencia por cerrar"). "Asegurado/salvado/campeon" contra el techo de TODOS los perseguidores. |
| 20, 190 (parcial) | actualizar_contexto_equipos.py | Jornada activa por fecha real (J25, no J76). Palabras completas y filtro de femenino/filial en las alertas de noticias. |
| 31, 73, 74, 105 | ajustar_aprendizaje_elige8.py | Solo toca la jornada activa y no empezada; nunca una prediccion congelada. Memoria en orden cronologico, con temporada, y `premio_eur` declarado manda. Un fichero incoherente ya no tumba el paso. |
| 78, 135 | construir_historial_quinielas.py | `signo_nuestro` (prediccion del motor) ya no convierte una jornada en "validada"; el historial no se realimenta con `historial_preservado`; la jugada debe ser de la misma temporada. |
| 80 | aprender_de_historial_resultados.py | Orden y peso por posicion cronologica, no por numero. |
| 81, 115, 120 | alimentar_sorpresas_mercado.py, actualizar_aprendizaje_ia.py, evaluar_valor_senales.py | Esquema unico (`num_partido` y `numero_partido`), clave (temporada, jornada, partido); el segundo escritor ya no borra lo del primero. |
| 83 | evaluar_valor_senales.py | Senales de riesgo: veredicto `marca_partidos_dificiles`, no `perjudica`. |
| 38, 84, 133, 236, 237, 239, 240 | estudio_ver_sorpresas.py, estudio_terceros_espana.py | Fuente = snapshot pre-cierre; orden y temporada por fecha; A7 descartada; metrica A2b; masa sin tope en J60 y con equipos comprobados. NO se han re-ejecutado: sus JSON actuales quedan invalidados (lo dice el docstring y la salida). |
| 182, 245 | generar_estado_vivo_ia.py, diagnostico_sistema.py, control_calidad_actualizacion.py | Respaldos por fecha real; alerta critica si `ultima_prediccion.json` es ilegible; alerta si no se puede calcular la jornada objetivo; "recta final" solo con 10 jornadas o menos. |
| 183 | diagnostico_sistema.py | Losilla y % LAE cuentan como fuentes de mercado y de masa. |
| 184 | control_calidad_actualizacion.py | Cruce tolerante de nombres en "clasificacion congelada". |
| 185 | estudio_efecto_revulsivo.py | Real Madrid ya no casa con el Atletico. |
| 186, 238 | generar_diario_aprendizaje.py | Guarda: no se puede ejecutar (no se ha borrado). |
| 192, 226 | actualizar_analisis_ia.py | Solo cuenta signos de la columna `resultado_oficial`; forma por fecha. |
| 220 (parcial) | normalizar_textos_generados.py | Recorre tambien `data/jornadas`, `data/premios`, `data/temporadas`. |

## Efecto sobre lo publicado

- **13**: el acierto que "aprende" el motor baja porque deja de puntuarse con
  predicciones regeneradas tras el cierre. Cifras de `aprendizaje_ia.json` (medidas el
  27/11 ejecutando `actualizar_aprendizaje_ia.py` sobre una copia temporal de `data/`;
  las cifras 389/546 -> 335/504 de la primera version de este informe eran un recuento
  en memoria distinto del que escribe el script y quedan retiradas):

  | Campo de `aprendizaje_ia.json` | Hoy publicado | Con el arreglo |
  |---|---|---|
  | precision | 70,24% (413/588) | 65,65% (386/588) |
  | ajuste_motor.umbral_fijo_seguro | 54 | 58 |
  | ajuste_motor.min_dobles_auto | 0 | 3 |
  | ajuste_motor.min_triples_auto | 1 | 1 |
  | ajuste_motor.riesgo_extra_fijo_fragil | 1,42 | 8,08 |
  | ajuste_motor.riesgo_extra_triple_insuficiente | 1,91 | 2,67 |
  | ajuste_motor.boost_empate_zona_riesgo | 6,0 | 4,1 |
  | fijo fallado sobre total | 12,24% | 17,86% |
  | no cubrio empate sobre total | 11,39% | 9,52% |

  Ejemplos por jornada: J72 de 25/26 14 -> 6, J71 13 -> 7, J73 12 -> 5, J15 de 26/27
  11 -> 8.

  **Efecto medido en la J25** (cierra el 28/11). `motor_prediccion_objetivo.py` ejecutado
  dos veces sobre copias temporales, mismo codigo y mismos datos, cambiando solo el
  aprendizaje (A = `aprendizaje_ia.json` de hoy; B = el regenerado con el arreglo):
  - Los 14 signos son IDENTICOS: `1 2 2 1 1X 2 X2 1 1 1X 1X 1 1X2 1` (4 dobles, 1 triple).
  - Elige 8 por partido identico. Configuracion identica.
  - Probabilidades: diferencia maxima 0,2 pp (la X baja 0,1-0,2 pp en 10 partidos por el
    boost de empate 6,0 -> 4,1; min_dobles_auto 3 no muerde porque el boleto ya lleva 4).
  - Cambian textos internos de riesgo/explicacion de 11 partidos.
  Es decir: hoy el arreglo NO cambia el boleto de la J25 a la salida del motor. No se han
  ejecutado los pasos posteriores del ciclo (alinear boleto, optimizador), que son de otros
  paquetes; la prediccion publicada hoy difiere de A en los partidos 7, 10 y 13 por esos
  pasos, no por este arreglo. Aun asi, es Marc quien decide si esto se sube antes o
  despues del cierre de la J25 (este paquete no hace commit ni push).
- **31/74/105**: el Elige 8 de jornadas cerradas deja de reescribirse (J24 vuelve a ser
  estable). El de la jornada activa lo sigue decidiendo `aplicar_elige8_seguro`.
- **17**: el chat pasa de "mejor J70, 97,34 EUR" a mejor J18 de 26/27 (13 aciertos),
  320,90 EUR cobrados (97,34 en 25/26 + 223,56 en 26/27), precision 68,8%.
- **16, 19, 20, 78, 81**: cambian textos, listas de la web y memoria; no los % del motor
  hoy (el motor ignora la motivacion con mas de 10 jornadas por jugar).

## Pendiente de decision de Marc

- **19 (resto)**: `nivel_motivacion` sigue sumando todos los objetivos vivos: hoy los 20
  de Primera salen "maxima" (25 partidos restantes). No afecta al motor hasta que queden
  10 jornadas; cambiar la formula es decision de modelado.
- **190 (resto)**: ventana de noticias de 60 dias y consulta RSS con las palabras clave
  dentro. Acortarla a 7-10 dias cambia las alertas que restan 3 pp en el motor.
- **81/115 (resto)**: las sorpresas de mercado ya sobreviven, pero el refuerzo del motor
  sigue sin dispararse (exige categoria + alerta coincidentes en 3 casos y hoy no hay
  alertas de motivacion activas). Rehacer las categorias es modelado.

## Fuera de este paquete

- 36, 134: `index.html` y `construir_memoria_ia.py` (orden del chat y del diario).
- 234: `historico_quinielas_lae.json` lo escribe `cargar_historico_quinielas_lae.py`.
- 221 y el orden de pasos de 220; retirar `actualizar_analisis_ia.py` del pipeline
  (192/226): es `actualizar_todo.py`.
- 13/38/237: `memoria_autonoma_quiniela.cargar_predicciones` mantiene la prioridad
  predicciones > pre_cierre y el corte de temporada del 1 de agosto.
- 133/239: `senal_valiente.py` (texto "cae el 64%" y el mismo `or 100`).
- 120: `calibrar_probabilidades.py`.

## Avisos

- `generar_estado_vivo_ia.cargar_json` no captura JSON corrupto: con
  `ultima_prediccion.json` roto el script falla (ruidoso, no silencioso). No lo he tocado.
- A7 nemesis: el codigo ya no afirma "z<1" como resultado propio; el motivo de descarte
  dice que la cifra es de la auditoria y que aqui no se ha recalculado. El descarte se
  sostiene por la circularidad.

## Segunda pasada (27/11, tras la revision independiente)

| Problema del revisor | Que se hizo |
|---|---|
| Efecto del 13 en el motor sin medir | Medido (tabla y diff de la J25 arriba): mismos 14 signos, max 0,2 pp. |
| Sorpresas de mercado sin campos para el chat | `registrar_sorpresas_mercado` escribe `partido`, `pronostico_jugado`, `resultado`, `registrada_en`; `normalizar_entrada` rellena `partido`/`origen` en las antiguas. Simulado: 59 entradas, 0 sin `partido`. |
| Clave de sorpresas sin origen | La identidad es (temporada, jornada, partido, origen) en los dos escritores: la de mercado no tapa la del fijo fallado ni al reves. |
| Temporada del diario deducida del fichero de jornada | Un fallo de fijo ya guardado se reconoce por (jornada, partido, nombre del partido, signo real) y no se reanade con otra temporada. Fondo: `diario_aprendizaje.json` deberia llevar temporada/fecha (`construir_memoria_ia.py`, otro paquete). |
| Objetivo principal solo por distancia | Entre objetivos vivos a 3 puntos o menos decide la prioridad fija. Con la clasificacion real: Villarreal, Espanyol, Deportivo y Osasuna siguen en `riesgo_descenso`; cambian 20 de 42 equipos (todos de la mitad alta, que salian con "permanencia por cerrar"). Solo textos. |
| Barras invertidas en `origen` | `ruta_posix()` en los tres puntos de escritura. |
| J66/J67 reescritas en `historial_premios.json` | El registro existente de una jornada con quiniela real en `quinielas_jugadas.json` (misma temporada) ya no se toca desde aqui, y el registro nuevo lleva `temporada`. Simulado: J66 y J67 quedan como estan (11). |
| Cifra z<1 no medida | Texto corregido (docstring y `FEATURES_INVALIDADAS`). |
| Test de prediccion congelada no probaba el arreglo | Ahora usa una prediccion con `configuracion.elige8`: sin la guarda se reescribe. |
| `tests/test_actualizar_aprendizaje_ia.py` modificado | El bloque `if __name__ == "__main__"` estaba en mitad del fichero (dejaba fuera la ultima clase al ejecutarlo directo); esta movido al final. Declarado aqui. |

Para otros paquetes:
- **Web (index.html, ~linea 4311)**: el bloque "fijo jugado que fallo" recorre TODAS las
  entradas de `sorpresas_mercado.json`. Debe filtrar por
  `s.origen === 'diario_aprendizaje_fallo_fijo'` o titular aparte las de
  `mercado_favorito_no_gano` (en ellas `pronostico_jugado` es lo que decia el motor y
  puede ser un doble que acerto). Ya no saldra "undefined", pero el recuento "N fijos
  fallados" seguira inflado (59 en vez de 13) hasta que la web filtre.
- **Premios (calcular_premios.py)**: J66 y J67 tienen quiniela real pero su registro en
  `historial_premios.json` no lleva `fuente_aciertos: quinielas_jugadas`; los 11 aciertos
  que muestra salen de una prediccion regenerada, no de la jugada. Ademas la J22 (no
  jugada) se anade en cada ciclo desde este script con los 13 aciertos del motor
  (comportamiento anterior, no cambiado).
