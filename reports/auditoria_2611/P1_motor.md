# Auditoria 26/11 - paquete P1_motor

Ficheros tocados: `motor_prediccion_quiniela.py`, `motor_prediccion_objetivo.py`,
`modelo_dixon_coles.py`, `calibrar_probabilidades.py`, `backtest_dixon_coles.py`
y el test nuevo `tests/test_aud_P1_motor_auditoria_2611.py` (46 tests).
No se ha tocado ningun dato de `data/`. Sin commit ni push.

## Arreglado

| Indice | Que | Donde |
|---|---|---|
| 0 | Buscador de nombres: los tokens genericos (`sporting`, `atletico`, `racing`, `rayo`, `deportivo`, `athletic`, `madrid`, `barcelona`, `union`, `balompie`, `inter`, `dinamo`...) y los de 1 letra ya no bastan; primer equipo y filial no casan; empate entre equipos distintos = `None`. Lo usan `buscar_equipo`, contexto, contexto competitivo, Losilla, lesiones, calendario y pretemporada. | `tokens_nombre_equipo`, `puntuacion_nombre_equipo`, `mejor_coincidencia_nombre` |
| 37 | `buscar_perfil_autonomo`: prefijo solo con 3+ letras, sin tokens de 1 letra ni relleno, token generico solo no vale, empate del mismo equipo -> mas partidos, empate de equipos distintos -> `None`. | motor |
| 32, 114 | El motor ya NO escribe el snapshot pre-cierre. Unico escritor: `guardar_snapshot_prediccion.py` al final de la cadena. `snapshot_pre_cierre` queda en la salida como `{"creado": false, "motivo": ...}`. | `predecir` |
| 44 | `es_equipo_liga_f` reconoce `Femenino/Femenina/Femeni`. | motor |
| 140, 164 | Dixon-Coles: el fallo de entrenamiento se guarda (`error_entrenamiento()`), no se reintenta 14 veces, la traza lleva `motivo` (`error_entrenamiento: ...` o `equipo_no_cubierto`) y se avisa si no converge. | `modelo_dixon_coles.py`, `ajustar_por_dixon_coles` |
| 141 | Bloques nuevos `cobertura_capas` y `cobertura_mercado` en la prediccion (partidos con mercado, jornada de la fuente, D-C activos). Si falta mercado en algun partido o D-C fallo: alerta `alta` en `alertas_boleto` y `ALERTA motor` por consola. | `resumen_cobertura_capas` |
| 155 | El mercado Losilla se empareja por numero Y al menos un equipo; si no, por los dos equipos. Un `numero` sucio ya no tumba el motor. Si solo casa el numero, ver "Segunda pasada". | `emparejar_partido_losilla` |
| 43 | `partido_es_derbi` compara equipo a equipo con el buscador (antes ninguno casaba con nombres largos, y el Clasico, el derbi madrileno y el vasco nunca). | motor |
| 156, 224 | Temporada por fecha real (`temporada_de_jornada`, con `cronologia_jornadas`) en la prediccion bloqueada y en espera; si el fichero de jornada esta roto o vacio no se pisa `ultima_prediccion.json`. | motor, `motor_prediccion_objetivo.py` |
| 157 | `detectar_jornada_activa` imprime la excepcion y, sin ficheros, para (`SystemExit`) en vez de devolver 61. | motor |
| 160 | Traza del revulsivo con `eventos` (uno por equipo) y `doble`. | `ajustar_por_revulsivo` |
| 161 | La alerta de sorpresa potencial usa categorias del vocabulario y solo marca favorito atacable si hay favorito. | `marcar_sorpresa_potencial` |
| 162 | `detalle_reciente` en orden cronologico (ahora J7-J24; antes J3-J9 + J66-J76) y sin evaluar un snapshot contra la jornada de otra temporada. Los buckets y el global salen identicos (490 partidos). | `calibrar_probabilidades.py` |
| 163 | Repetir el backtest no pisa `backtest_dixon_coles.json` (va a `..._repeticion_AAAAMMDD.json`) y el Test B descarta ficheros `jornada_N` que no sean de la 26/27. | `backtest_dixon_coles.py` |
| 152 (parcial) | La traza `ajuste_motivacion.clasificacion_losilla.fuente_vacia` dice cuando no hay tablas. | `calcular_ajuste_motivacion` |
| 1 (parte del motor) | Bloque nuevo `reparto_motor` (triples, dobles, X de autor, coberturas de autor cubiertas y sin cubrir, y fila por partido) que ningun paso posterior reescribe. Contrato en el docstring de `reparto_del_motor`. | motor |

## Contrato del reparto que exporta el motor (indice 1)

Por partido en `partidos[]`:

- `tipo`: `FIJO`, `DOBLE` o `TRIPLE`.
- `signo_final`: los signos jugados.
- `cobertura_autor.activo`: el motor pide cubrir la X. `cobertura_autor.cubierta` es `true`
  solo si `tipo` es `DOBLE` y `signo_final` lleva la X; `false` si se pidio y quedo de fijo.
- `x_de_autor.activo`: fijo jugado a la X.

Quien cambie `tipo` o `signo_final` despues (P7 en `alinear_boleto_con_analisis.py`, P8 en la web)
debe recalcular esos dos campos con esas reglas. `reparto_motor` guarda el original para comparar.

## Cambia la prediccion publicada

Comparado ejecutando el motor viejo y el nuevo sobre dos copias aisladas del repo (J25):

- P1 Betis - Rayo: 70,4 / 20,7 / 8,9 -> 70,1 / 20,8 / 9,1 (el Betis deja de usar el perfil de "Belgica").
- P8 R. Sociedad - Sevilla: 50,8 / 27,2 / 22,0 -> 51,4 / 27,1 / 21,5 (perfil de 28 partidos en vez de 2).
- Ningun signo, doble ni triple cambia en la J25. El resto de partidos, identicos.

Fuera de la J25 (prior del motor, antes del mercado):

- J26 P10 Atletico Paso - Sevilla: 57,2 / 26,9 / 15,9 -> 18,9 / 27,6 / 53,5.
- J26 P8 Rayo Majadahonda - Mallorca: 19,4 / 30,8 / 49,8 -> 20,2 / 26,7 / 53,0.
- J24 P12 Sporting Lisboa - Man. United: 57,9 / 28,0 / 14,0 -> 35,9 / 34,7 / 29,4.
- J24 P1 Arsenal - B. Dortmund: 18,5 / 28,7 / 52,8 -> 33,7 / 35,4 / 30,9.
- Los derbis de la lista (Clasico, Madrid-Atletico, Athletic-Real Sociedad, Sevilla-Betis,
  Espanyol-Barcelona, Deportivo-Celta) vuelven a recibir el caso H (X +10, favorito -5, rival +5).
  No hay ninguno en J25, J26 ni J27.

## Segunda pasada (27/11, tras la revision independiente)

- 155: el arreglo dejaba SIN mercado un partido cuando el numero coincidia pero ninguno de los dos nombres
  casaba por abreviatura (`Sporting Lisboa` / `SPORTING DE PORTUGAL`, `PSG` / `PARIS SG`). Ahora
  `emparejar_partido_losilla` devuelve `(item, modo)` y acepta el partido **solo por numero** cuando se cumplen
  las tres cosas: ninguno de los dos equipos aparece en otro partido de la fuente, los equipos del partido N de
  la fuente no son los de otro partido de la jornada, y el resto de la fuente casa con la jornada numero a
  numero (3 partidos o mas y al menos la mitad). Si no se cumple, el partido queda sin mercado y salta la
  alerta de siempre. Traza por partido en `trazabilidad_datos.mercado_losilla_emparejamiento`
  (`emparejamiento`: `numero_y_equipo`, `numero_sin_nombres`, `equipos`, `solo_por_numero` o `sin_mercado`),
  lista en `cobertura_capas.mercado.emparejados_solo_por_numero` y alerta `media` en `alertas_boleto` para
  que se compruebe a ojo. En la J25 real: 14 de 14 por `numero_y_equipo`, mismos items que antes.
- 161: las lineas en linea pasan a `marcar_sorpresa_potencial`, con test de los dos casos (con y sin favorito).
- 163: test que llama a `test_b()` de verdad sobre un `data/` temporal con un `jornada_2.json` de la 25/26.
- 162: el docstring de `_snapshot_es_de_esta_jornada` decia 2 dias y el codigo usa 7; corregido el docstring.
- 32: `predecir()` imprime al final un aviso: el snapshot pre-cierre no se ha actualizado y, si el motor se
  lanza suelto, hay que ejecutar `guardar_snapshot_prediccion.py`.

## A confirmar por Marc antes del proximo derbi (indice 43)

El arreglo de `partido_es_derbi` no es una capa nueva (ya actuaba con nombres cortos), pero mueve numeros
publicados: el caso H se aplica DESPUES de la mezcla con el mercado (X +10, favorito -5, rival +5, y hasta 20
de riesgo) y, si el mercado supera el 80%, la alerta de derbi activa el caso D y fuerza un DOBLE. En todo
`data/jornadas` hay 3 derbis de la lista: J32 Espanyol - Barcelona y J55 Barcelona - Espanyol (ya se
detectaban) y J41 Athletic Club - Real Sociedad (nuevo). Ninguno en J25, J26 ni J27.

## Pendiente de decision de Marc (no tocado)

- 3: `USAR_CALIBRACION_EN_COBERTURA`. El backtest de hoy da 196 crudo frente a 195 calibrado (-1, "NO ACTIVAR");
  el del 17/10 daba 87 frente a 88. Las revisiones estan recortadas a 250.
- 4, 148, 151: `ajustar_por_calibracion` suma +4 al favorito en 9 de 14 partidos de la J25 con una tabla del motor
  anterior; el mercado en los mismos partidos esta calibrado (60-70: dice 64,3 y acierta 67,7).
- 47: la calibracion de cobertura sube el favorito hasta +18,2 (banda 50-60) y +16,5 (60-70).
- 46, 153: el riesgo del revulsivo (6 por debut, 3 por segundo partido) no entra en la incertidumbre.
- 123: `aplicar_patron_posicion` mezcla al 12% un perfil con n=55 por casilla.
- 158: "segunda mitad de la tabla" cuenta como evidencia contextual del boleto millonario (7 de 14 partidos en J25).
- 159: el boleto millonario cambia dobles y triples por un fijo; su docstring dice que es a proposito.
- 45: los ficheros de jornada se guardan por numero; `jornada_28.json` de la 25/26 se pisara a mediados de diciembre.

## Aplazado

- 154: `fuerza_pretemporada` en otra escala que `fuerza()`. Solo actua con pj=0 (arranque de temporada).
- 152 (resto): alimentar la motivacion por clasificacion desde otra fuente y parametrizar Segunda.

## Para otros paquetes

- `diagnostico_sistema` / `control_calidad` / `validar_publicacion_autonoma` pueden leer
  `cobertura_capas.mercado.completa` y `cobertura_capas.dixon_coles.error_entrenamiento` para su propia alerta.
- Si el motor se ejecuta suelto (fuera de `actualizar_todo.py`) el snapshot pre-cierre ya no se refresca:
  hay que ejecutar despues `guardar_snapshot_prediccion.py`.
- La clave con mojibake `ba lgica` sigue en `perfiles_equipos.json` (origen: P2); el motor ya no la casa con el Betis.

## Tests ejecutados

`python -m unittest tests.test_aud_P1_motor_auditoria_2611 tests.test_motor_prediccion tests.test_motor_liga_f
tests.test_jornada_activa tests.test_modelo_dixon_coles tests.test_revulsivo tests.test_fijos_calibrados
tests.test_auditoria_reparaciones tests.test_auditoria_16_11 tests.test_calibracion_x` -> 225 tests, OK (46 son del fichero nuevo).
