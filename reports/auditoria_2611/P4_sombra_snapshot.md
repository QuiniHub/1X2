# Auditoria 26/11 - paquete P4 "sombra y snapshot pre-cierre"

Indices asignados: 9, 10, 27, 39, 41, 42, 49, 52, 64, 65, 66, 67, 68, 69, 70, 131, 137, 149,
165, 174, 176, 202, 216, 231, 246, 250.

## Arreglado

| Indice | Que se hizo | Fichero |
|---|---|---|
| 9 | Los seis marcadores de sombra leen el bloque del snapshot PRE-CIERRE (`senal_valiente.bloques_del_cierre`, que usa `cronologia_jornadas.prediccion_del_cierre`) y solo con la jornada cerrada (14 signos). El espejo `data/predicciones/jornada_N.json` ya no se lee. | senal_valiente, tercero_valor, radar_tormenta, sorpresa_nombrada, columna_valiente, ranker_favoritos |
| 10, 41 | La temporada del registro sale de la fecha real de la jornada, no de `now()`. | los mismos |
| 49, 216 | `configuracion` entra en `BLOQUES_DECISION`. Sobre una copia de la J24: triples 2 -> 1 (1 partido TRIPLE). | congelar_bloques_sombra |
| 52 | Congelado, snapshot, backtesting pre-cierre, calibracion_x y mezcla_benter descartan un snapshot que no es de la misma jornada real (equipos o fecha). El snapshot guarda `temporada`. Resumen por temporada y orden cronologico en backtesting_pre_cierre. | guardar_snapshot_prediccion (`snapshot_de_otra_jornada`), congelar_bloques_sombra, backtesting_pre_cierre, calibracion_x, mezcla_benter |
| 64 | El radar ya no exige 10 de 14 pares identicos; con snapshot validado basta. Las no evaluables se devuelven con motivo (`no_evaluables`). | radar_tormenta |
| 65 | `nombres_casan` (sufijos femeninos y comparador tolerante comun); con snapshot validado el num basta. | senal_valiente, sorpresa_nombrada |
| 66 | La auditoria de vetos usa `SENALES_RETIRADAS` + suspendidas en el vivo y en los dos vetos. | aprendizaje_modulos |
| 67 | Recaudacion validada (0,3-20 M, reconstruccion desde la categoria de 13) y escrutinio placebo excluido. | aprendizaje_modulos |
| 68 | `cargar_masa` saca la temporada de la fecha de la jornada y no salta a otras temporadas. | columna_valiente (lo usan ranker y elige8_ev) |
| 69, 250 (parte) | prior_europeo: muestra identificada por temporada 2026_2027 + numero; si la muestra ya no esta completa en disco se conserva el veredicto guardado. | prior_europeo |
| 70 | ranker_favoritos y elige8_ev retiran su bloque si la prediccion esta bloqueada y no dejan el de la ejecucion anterior. | ranker_favoritos, elige8_ev, columna_valiente (`publicar_bloque_sombra`) |
| 131, 137 | Tope de jornadas 60 -> 100. | aprendizaje_modulos, senal_valiente |
| 149 | La inversion usa el peso real de la traza; con peso >= 0,80 la fila se marca no fiable y no entra en el ajuste (salvo que el snapshot traiga `probabilidades_motor_pre_mercado`). Hoy 0 de 378 filas afectadas: ninguna jornada cerrada lleva aun el 0,85. | mezcla_benter |
| 165, 202 | Se marca inmutable antes del corte por resultados, no se fabrica un snapshot a posteriori (ni sin fechas) y `marcar_inmutables_vencidos()` corrige los ya vencidos. | guardar_snapshot_prediccion |
| 174 | Alias `esperado` en el resumen del marcador. | ranker_favoritos |
| 176 (parte) | El aviso sale del veredicto real del backtest. | elige8_ev |
| 246 | Si las fuentes de senales no cargan el bloque sale `no_disponible` con `fuentes_senales: error...`. | ranker_favoritos |

## Reparacion de datos: marcadores J22-J24 (indice 9)

Se quitaron los registros de J22, J23 y J24 (2026_2027) y se regeneraron con las propias
funciones del marcador leyendo el snapshot pre-cierre. Copia de los ficheros anteriores en el
scratchpad de la sesion (`p4/backup`); tambien estan en git (HEAD).

| Marcador | Antes | Despues |
|---|---|---|
| marcador_valiente | J22 P11 "1" fallo; J23 P6 X fallo; J24 P5 X fallo. 9 evaluadas, 1 acierto, 2,58 esperados | J22 y J24 fuera (el snapshot decia `sin_valiente`); J23 P6 X igual. 7 evaluadas, 1 acierto, 1,95 esperados |
| marcador_tercero_valor | J22 P2 "2" fallo; J23 P13 "2" fallo; J24 P1 "2" fallo. 9 evaluados, 0 aciertos, 2,41 esperados, 0 EUR | J22 P2 igual; J23 P9 "2" (masa 20%) ACIERTO; J24 P9 "2" (masa 9%) fallo. 9 evaluados, 1 acierto, 2,42 esperados, 5 EUR cobrados |
| marcador_radar_tormenta | J22 zona [8,3,14]; J23 [9,5,8]; J24 sin registrar. 5 jornadas, 5/15 terceros en zona (33,3% dentro, 14,5% fuera) | J22 [5,12]; J23 [9,5,1]; J24 [13,11,2]. 6 jornadas, 5/17 (29,4% dentro, 13,4% fuera) |
| marcador_sorpresa_nombrada | J23 P2 "2" acierto; J24 P5 X fallo. 2 evaluadas, 1 acierto | J23 fuera (el snapshot pre-cierre de la J23 no tenia el bloque: el modulo se creo despues del cierre); J24 igual. 1 evaluada, 0 aciertos |
| marcador_columna_valiente, marcador_ranker_favoritos | sin cambios (la J24 de la columna coincide con el snapshot) | no se tocaron |

Los registros anteriores a la J22 se conservan tal cual: los snapshots J14-J21 no guardan los
bloques de sombra, asi que no se pueden contrastar. Por el mismo motivo el radar no puede
recuperar J17, J19 y J20.

## No arreglado

- **42 (pendiente de decision de Marc).** Con el peso 0,85 las senales "motor distinto del
  mercado" casi no se disparan. Recuento de la auditoria: con el regimen anterior 71 de 392
  partidos tenian desacuerdo; simulando 0,15*motor + 0,85*mercado sobre 378 partidos, de 180
  desacuerdos del motor puro quedan 4; en la J25 viva, 1 de 14. Opciones: exportar la
  probabilidad del motor antes del mercado y calcular las senales sobre ella, o aceptar que
  quedan apagadas y relanzar los backtests prerregistrados.
- **27, 39 (fuera del paquete).** 27: los espejos J1, J22 y J23 de `data/predicciones` y los
  modulos que leen `signo_nuestro` no son de este paquete. 39: el emparejamiento de
  `mercado_losilla` y `estudio_ver_sorpresas.py` tampoco.
- **231 (aplazado).** Historico de calendarios con fechas reales y lista `CALENDARIOS` dinamica.
- **250, 176 (resto).** calibracion_x sigue recalculando su backtest en cada ciclo (quitarlo del
  pipeline es de `actualizar_todo.py`); los numeros escritos a mano en index.html son de la web.

## Efecto en lo publicado

- Probabilidades 1X2 y boleto: sin cambios.
- Resumenes de los marcadores de sombra: cambian como en la tabla.
- Factor de acertantes: publicado 1,002. El codigo de HEAD con los datos de hoy ya da 1,031 (la
  recaudacion de la J23 la corrigio otro paquete). El efecto propio de este paquete es
  1,031 -> 1,035: sale el escrutinio placebo de la J14 y entra la J22 con recaudacion reconstruida
  de 621.717 EUR (coherente con las categorias de 13 y de 14). Siguen siendo 23 escrutinios; las
  celdas pasan de 97 a 102. Lo lee optimizador_ev_premio (en sombra).
- Espejos ya cerrados (`data/predicciones/jornada_22/23/24.json`): NO se corrigen solos. El
  pipeline solo congela la jornada activa (hoy la J25), asi que la J24 sigue con
  `configuracion.triples` = 2 (snapshot: 1) y la J22 igual. Ver "Pendiente: espejos J22-J24".
- Snapshots J23 y J24: quedaran `inmutable: true` en el proximo ciclo (no se editaron a mano).

## Segunda pasada (27/11, tras la revision independiente)

- **165 (completado).** Sin fechas en la jornada y sin snapshot previo ya NO se fabrica un
  snapshot (`motivo`: "sin fechas no se puede garantizar que sea pre-cierre"). Comprobado: las
  unicas jornadas sin fecha por partido en disco son J28-J63 de la 25/26 (cerradas); todas las de
  la 26/27 traen fechas, asi que la jornada viva no pierde su snapshot.
- **52 (completado).** `ranker_favoritos.construir_dataset` descarta el snapshot que no es de la
  misma jornada real (`snapshot_de_otra_jornada`). Hoy 0 snapshots ajenos: el dataset no cambia.
- **149.** `nota_exclusion` calcula el factor con el peso real mas alto de las filas excluidas.
  Aviso para Marc y para el paquete del motor (va con el pendiente 42): desde la J25 las 14 filas
  de cada jornada llevan peso 0,85 y quedan fuera del ajuste, porque el motor no exporta
  `probabilidades_motor_pre_mercado` por partido. El estudio Benter deja de crecer hasta que el
  motor exporte esa clave. El umbral 0,80 (`PESO_MAX_INVERTIBLE`) es un criterio nuevo de este
  arreglo: a validar por Marc.
- **49.** `python congelar_bloques_sombra.py --jornada N` recongela a mano el espejo de una
  jornada pasada (sin argumento, el comportamiento del pipeline no cambia).

## Pendiente: espejos J22-J24 (decision de Marc / paquete del hallazgo 27)

`data/predicciones/` no es de este paquete y la restauracion se solapa con el hallazgo 27, asi
que NO se ha ejecutado sobre los datos reales. Medido sobre copia con `congelar(N)`:

| Jornada | Bloques restaurados | Retirados | configuracion.triples | Partidos con probabilidades distintas | signo_final distinto |
|---|---|---|---|---|---|
| J22 | valiente, tercero_valor, radar_tormenta | - | 2 -> 1 | 14 | 6 |
| J23 | valiente, tercero_valor, radar_tormenta | sorpresa_nombrada | 2 -> 2 | 14 | 3 |
| J24 | - | - | 2 -> 1 | 0 | 0 |

La J24 es inocua (solo `configuracion` y campos anadidos despues). J22 y J23 cambian
probabilidades y signos del espejo, es decir, `signo_nuestro` y las metricas que dependen de el
(hallazgo 27). Comando listo: `python congelar_bloques_sombra.py --jornada 24` (y 22, 23).

Tampoco se ha anotado nada en DECISION_LOG (no es de este paquete): conviene copiar alli la
tabla antes/despues de los marcadores y el desglose del factor de acertantes.

## Tests

`python -m unittest` de: test_aud_P4_sombra_snapshot_cierre (32), test_congelar_bloques_sombra (4),
test_columna_valiente (14), test_sorpresa_nombrada (13), test_ranker_favoritos (23),
test_elige8_ev (16), test_elige8_modos (13), test_radar_tormenta (24), test_senal_valiente (52),
test_tercero_valor (42), test_aprendizaje_modulos (38), test_calibracion_x (20),
test_mezcla_benter (13), test_prior_europeo (10). Todos OK.
