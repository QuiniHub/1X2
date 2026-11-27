# Auditoria 26/11 - paquete P7 "pipeline y boleto"

Ficheros tocados: `actualizar_todo.py`, `alinear_boleto_con_analisis.py`,
`validar_publicacion_autonoma.py`, `validar_contexto_actual.py`, `forzar_overrides.py`,
`compuerta_jornada.py`, `.github/workflows/main.yml`, `ci-pr.yml`,
`importar-memoria-quinielas.yml`, `tests/test_calidad_prediccion.py` (3 lineas) y cinco
tests nuevos `tests/test_aud_P7_*.py` (81 tests).

## CAMBIA EL BOLETO PUBLICADO (hallazgos 1 y 30)

`alinear_boleto_con_analisis.py` ya no reparte dobles ni triples: respeta `signo_final`,
`tipo`, `cobertura_autor` y `x_de_autor` del motor y solo reescribe textos, resumen y coste.
`validar_publicacion_autonoma.py` tenia una copia del mismo criterio alternativo
(`score_triple` / `score_cobertura`): retirada, porque habria avisado en falso cada ciclo.

Comprobado con la J25 real (prediccion del 27/11 11:20 UTC), reconstruyendo el boleto del
motor con las prioridades que el propio motor exporta por partido
(`prioridad_cobertura_triple` / `prioridad_cobertura_doble`):

| Partido | Motor (lo que se publicara) | Publicado hasta hoy |
|---|---|---|
| 7 Celta - Villarreal (cobertura de autor) | DOBLE **X2** | DOBLE 12 (sin la X, y marcado "cubierta") |
| 10 Albacete - Tenerife (cobertura de autor) | DOBLE **1X** | TRIPLE 1X2 |
| 13 Mallorca - Castellon | **TRIPLE 1X2** | DOBLE 12 |

Los otros 11 partidos, iguales. Coste igual: 48 apuestas, 36,00 EUR + 0,50 EUR de Elige 8.
El script antiguo, aplicado al boleto del motor, devuelve exactamente lo publicado; el nuevo
lo deja intacto.

Efecto secundario a saber: la **X de autor en un fijo** (motor, 19/10/2026) llegara por
primera vez al boleto publicado (antes este script la borraba siempre: fijo = `signo_base`).
En la J25 ningun partido la tiene activa. `tests/test_calidad_prediccion.py` exigia
`signo_base` dentro de `signo_final`; se ha anadido la excepcion para ese caso, porque si no
el paso "Ejecutar pruebas" bloquearia el pipeline el primer dia que el motor la use.

## Arreglado

- **181** Elige 8: se cobra sobre los 8 partidos elegidos (antes 48 x 0,50 = 24 EUR en vez de
  0,50 EUR, hasta que `aplicar_elige8_seguro` lo corregia al final). Prediccion retenida: coste 0.
- **112** `congelar_bloques_sombra.py` es critico cuando la jornada esta en juego: si falla,
  `actualizar_todo` se detiene y no hay commit. Ademas `validar_publicacion_autonoma` bloquea
  si la jornada esta en juego y la prediccion no lleva `prediccion_congelada_al_cierre`, o si
  el snapshot pre-cierre existe pero no se puede leer. "En juego" se decide con
  `cronologia_jornadas.snapshot_del_cierre` (misma jornada real, no solo el numero), primer
  partido ya empezado y jornada sin cerrar.
- **118** Congelacion temprana: `congelar_bloques_sombra.py` corre tambien justo despues de
  `alinear_boleto_con_analisis.py` (no hace nada si la jornada no ha empezado), asi estado
  vivo, premios, diagnostico y memoria historica se calculan con la prediccion congelada. La
  congelacion final se mantiene.
- **104** `main.yml`: paso nuevo "Comprobar el boleto recien generado" entre el pipeline y el
  commit (`tests.test_calidad_prediccion` + `tests.test_aud_P7_boleto_publicado`, este ultimo
  solo activo con `QUINIELA_POST_PIPELINE=1`). `validar_publicacion_autonoma` anade como
  errores criticos: numeracion 1-14, signo invalido, FIJO con mas de un signo, `coste.apuestas`
  o `importe_quiniela` que no cuadran. Como aviso: `signo_base` fuera del signo, doble de autor
  sin X, Elige 8 distinto de 8, espejo `jornada_N.json` distinto de `ultima_prediccion.json`.
- **169** `timeout=900 s` por subproceso (variable `ACTUALIZAR_TODO_TIMEOUT_SEG`); un script
  colgado cuenta como fallo (critico si es el motor o el validador). `timeout-minutes`: 45 en
  `main.yml`, 20 en `ci-pr.yml`, 10 en el importador.
- **50, 85, 116, 122, 139** `validar_contexto_actual.py` usa la misma guardia
  `overrides_vigentes` que quien aplica los overrides; los de la ultima jornada 25/26 ya no se
  exigen. Los fallos cronicos salen ahora como anotacion `::warning::` en Actions y en
  `diagnostico_publicacion.json` (`fallos_cronicos` y avisos).
- **117, 138** `temporada_ya_iniciada()` mira la fecha real de la J1 (solo cuenta si es del
  1 de julio de la temporada en curso o posterior). La pretemporada busca
  `preparar_temporada_<inicio>_<fin>.py` de SU temporada; si no existe avisa y no ejecuta el
  de otra. Etiqueta de temporada correcta de enero a junio.
- **167, 217, 222** `SCRIPTS_NO_CRITICOS_RED` ya no es una lista escrita a mano: se deriva de
  `SCRIPTS_ACTIVOS` menos los criticos, y `es_critico()` es la unica regla que usa
  `ejecutar_script`.
- **166** `compuerta_jornada.py` tiene `main()`: deja en el log el estado de la compuerta
  (no escribe nada; la compuerta real sigue en el motor).
- **170** `aplicar_objetivos_oficiales_json.py` sale de `SCRIPTS_ACTIVOS` (su resultado lo
  pisaba siempre `forzar_overrides.py`); `forzar_overrides.py` ya no revienta si falta un fichero.
- **51, 128, 146, 249** Importador por issue: clave `(temporada, jornada)` con la temporada
  sacada de la fecha real de la jornada; no hereda ni pisa la jugada de otra temporada;
  escribe `temporada` en todas las jugadas; signos normalizados y validados; `validado_en`
  solo ISO no futuro; `pleno15` solo marcador 0/1/2/M; jugadas que no son objeto se ignoran.

## Pendiente de decision de Marc

- **5, 119** El cron `*/30` de GitHub corre en la practica cada 6-8 h. No se toca (disparo
  externo: Cloudflare Worker o cron externo). Hace falta decidir si se anade un disparo
  `workflow_dispatch` externo unos 30 min antes de `primer_partido_utc`.

## Avisos para otros paquetes

- **generar_contexto_competitivo.py**: `validar_contexto_actual` tiene ahora una comprobacion
  de coherencia y encuentra una contradiccion REAL en el contexto publicado hoy: FC Barcelona
  (lider de Primera) y UD Almeria (lider de Segunda) tienen como `objetivo_principal`
  `descenso` / `permanencia_por_cerrar`. Hasta que se corrija el generador, el validador
  seguira fallando (no critico), esta vez con motivo.
- **P9 (tests)**: `test_optimizador_ev_premio.py:122-123`, `test_senal_valiente.py:476` y
  `test_tercero_valor.py:401` siguen pasando, pero comprobar pertenencia a
  `SCRIPTS_NO_CRITICOS_RED` ya esta cubierto por `tests/test_aud_P7_pipeline.py` (que prueba
  el comportamiento de `ejecutar_script`); se pueden borrar. `test_optimizador_ev_premio.py:133`
  ancla el orden a `corregir_emparejamiento_equipos.py`, que no hace nada (hallazgo 223): si se
  ancla a `alinear_boleto_con_analisis.py` se puede quitar ese paso de la cadena.
- **111** `seleccionar_pleno15.py` y `aplicar_elige8_seguro.py` (no son de este paquete) siguen
  dejando el espejo distinto de `ultima_prediccion.json` en `elige8_modos`, `elige8_seguro` y
  `pleno15`. Ahora sale como aviso en `diagnostico_publicacion.json`.
- **146** `calcular_premios.jugada_por_jornada` sigue buscando la jugada solo por numero; ya
  tiene el campo `temporada` para usarlo. `data/quinielas_jugadas.json` no lo ha tocado este
  paquete (otro equipo ya le ha puesto `temporada` con el mismo formato `2026_2027`, compatible
  con el importador). En la proxima importacion el importador rellena la temporada que falte y
  reordena la lista cronologicamente (25/26 primero).
- **index.html** (hallazgo 1, parte web): el boton "Generar quiniela" sigue repartiendo con su
  propio criterio.
- `congelar_bloques_sombra.py` sigue respondiendo `sin_snapshot` con codigo 0 cuando el
  snapshot no se puede leer; lo detecta ahora el validador final.

## Segunda pasada (27/11, tras la revision independiente)

1. Paso post-pipeline de main.yml: solo BLOQUEAN el commit las incoherencias criticas del boleto y la jornada en juego sin congelar. Boleto distinto del del motor y espejo jornada_N.json distinto de ultima_prediccion.json pasan a anotacion ::warning:: (tests/test_aud_P7_boleto_publicado.py, funcion avisar). Mismo criterio que validar_publicacion_autonoma.
2. validar_contexto_actual.validar_coherencia_tabla ya no hace SystemExit: devuelve la lista, imprime AVISO y ::warning::. Comprobado con el contexto real: codigo 0 con 2 avisos (FC Barcelona y UD Almeria lideres con objetivo de descenso). Volverla bloqueante solo cuando generar_contexto_competitivo.py este corregido y verificado.
3. validar_publicacion_autonoma.estado_congelacion: usa la MISMA prueba de identidad que congelar_bloques_sombra (guardar_snapshot_prediccion.snapshot_de_otra_jornada, snapshot contra la prediccion) y aplica DIAS_MAX_JORNADA_EN_JUEGO (10 dias) tambien con snapshot legible: pasado ese plazo avisa y deja de bloquear.
4. Extremo a extremo: en una copia temporal del repo, con el motor integrado del arbol, motor_prediccion_objetivo.py + alinear_boleto_con_analisis.py dan el mismo boleto (alinear no toca nada). Frente a lo publicado a las 11:20 UTC cambian P7 (12 -> X2), P10 (triple -> doble 1X) y P13 (doble 12 -> triple). 48 apuestas, 36,00 EUR. Invariantes: sin criticos ni avisos.
5. Importador: una jugada guardada sin temporada deducible se conserva tal cual (ya no se indexa con clave vacia); un duplicado ya guardado tampoco se pierde.
6. Pendiente de Marc: si la jornada en juego sin congelar debe bloquear (como ahora, maximo 10 dias) o solo avisar.
