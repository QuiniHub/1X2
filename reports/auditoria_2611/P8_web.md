# Auditoria 26/11 - Paquete P8_web (index.html)

Ficheros tocados: `index.html`, `tests/test_aud_P8_web_contratos.py` (nuevo) y este informe.
Sin commit ni push (lo hace el coordinador).

## Arreglado

| Indice | Que se hizo |
|---|---|
| 21 | Fuente unica del boleto. Los contadores arrancan con la estructura del boleto publicado (J25: 4 dobles + 1 triple) y "Generar quiniela" ensena EXACTAMENTE `tipo` + `signo_final` del JSON. Si se cambian los contadores, se PARTE del boleto publicado y solo se anaden o quitan coberturas (las casillas no tocadas no se mueven), con `prioridad_cobertura_triple/doble` del motor y respetando `cobertura_autor` (doble con X) y `x_de_autor` (fijo a X). Se CONSERVA la regla de los "sin dueno" del 16/11 al elegir el doble nuevo (ver "Pendiente de decision de Marc"). En "ver analisis" se quita la frase "Decision final: ..." cuando el signo en pantalla es otro y se avisa. |
| 22, 36, 134 | El contexto del chat ordena por FECHA real (`ordenarPorFechaReal`, con las fechas de `quinielas_jugadas`): historial, detalle de la ultima cerrada, diario, Elige 8 reciente y sorpresas de mercado. Antes salian las J69-J76 de 25/26. |
| 23 | El contexto se recorta por BLOQUES con prioridad: prediccion actual > estado y totales (mejor resultado, total cobrado) > memoria del socio > historial > lo jugado > resto. Un bloque que no cabe se corta en un salto de linea. La sugerencia "Cuanto llevamos ganado?" ya activa el modo local. |
| 95 | El reintento por 413 conserva las reglas criticas y la personalidad, cambia el manual largo (~7.000 caracteres, solo va en preguntas no locales) por el resumen esencial y recorta los datos a 1600 caracteres (empiezan por la prediccion). Medido: envio de 14.536 caracteres -> reintento de 6.560, con las reglas esenciales y los datos. |
| 24, 178 | `pendiente_reducida` cuenta como pendiente: la J23 sale como "pendiente (reducida)" resaltada, no como 0,00 EUR. |
| 91 | El interruptor Elige 8 y el cambio de modo refrescan el panel de coste. Los contadores recalculan el coste DESPUES de repintar el boleto. |
| 92 | Sin boleto generado, el coste del Elige 8 se calcula con el reparto que saldria al generar (J25: 0,50 EUR, igual que `coste.importe_elige8`), nunca con las apuestas de toda la quiniela. Elige 8 vaciado a mano = 0 EUR. |
| 93 | Con boleto en pantalla manda el recuento real aunque sea todo fijos. Al confirmar se guardan dobles/triples reales y se exige que el Elige 8 tenga 8 partidos. |
| 90 | En Mixta/Manual, avisos, bandas y tipo de apuesta leen lo marcado a mano (`state.jugadaManual`); cada clic repinta el boleto conservando lo marcado. |
| 96, 233 | Premios confirmados en localStorage con clave temporada+jornada (`2026/2027:23`). Una entrada antigua (solo numero) solo vale si se confirmo despues de jugarse esa jornada. Si el pipeline trae una fuente de premio que no sea "pendiente..." (`confirmado_usuario`, `multicolumna...`, `escrutinio_versionado` y las que vengan), manda el del pipeline. El chat se guarda por temporada+jornada. |
| 127 | Favoritos en riesgo lee `resumen.esperado ?? resumen.nombrado_esperados`. |
| 89 | La fila pasa a llamarse "Seleccion del motor (Elige 8 economico)". Ademas, con los contadores de la jornada la web usa ya esa misma seleccion. |
| 94, 130 | Las tarjetas dicen lo que son: "Precision global del motor" y "Jornadas evaluadas" (vuelven a "reciente"/"con IA" si el pipeline publica esos campos). |
| 194 | Cifras de backtest leidas del JSON (Elige 8, nota de la lectura contra la masa, X de la columna de la masa) y fuera el texto caducado de la J24. |
| 195, 198, 235 | `escapeHtml` en los valores citados (laboratorio, valiente, tercero, ranker, optimizador, historicos, revulsivo, goles del visitante, mensaje de error, confirmacion). |
| 196 | El enlace alternativo dice "Issue abierto: falta pulsar Submit new issue en GitHub". |
| 199 | La columna "Validado" usa `fechaValidadoMs` (entiende `13/5/2026, 13:18:27`). |
| 200 | Eliminados `totalInvertido` y `historyRowCost` (coste inventado que no se mostraba). |
| 229 (parte) | La tarjeta dice "538 SPI en Espana (2016-23)". |

## Segunda pasada (27/11), tras la revision independiente

- 95: el reintento por 413 ya no conserva el manual largo (fila de arriba).
- 96: `premioDelPipelineManda` = cualquier fuente no vacia que no empiece por "pendiente".
- 22/36/134: `ordenarPorFechaReal` compara por DIA y desempata por temporada y numero (las J59-J63 apuntadas en bloque el 13/5/2026 salen 59 60 61 62 63); una fila sin fecha se coloca junto a la jornada fechada de numero mas cercano, no al principio (la J22 del diario sale entre J21 y J23).
- 90: en Mixta/Manual, mover un contador no cambia el Elige 8 si el boleto en pantalla no cambia (antes pasaba a otros 8 partidos y a 3,00 EUR con el mismo boleto).
- Tests: son contratos de TEXTO sobre index.html (no ejecutan JavaScript); la verificacion funcional es manual, en navegador. `test_los_datos_traen_temporada_en_todas_las_filas` es un contrato CRUZADO con los JSON de otros paquetes y esta marcado como tal.

## Pendiente de decision de Marc

- Regla de los "sin dueno" (16/11) al anadir un doble con los contadores: la web la conserva, pero el alineador del motor no la usa. Ejemplo J25 con 3D+1T: la web quita el doble de P7 (prioridad 238, "sin dueno") y deja el de P5 (352). Decidir si la web debe seguir aplicandola o repartir solo por prioridad del motor.

## Avisos para otros paquetes

- `data/premios/historial_premios.json` del arbol de trabajo trae J8, J15 y J19 de 26/27 como `escrutinio_versionado` con 0,00 EUR (antes `multicolumna_loteriaanta`: 3,93 + 6,82 + 3,41). El "Total cobrado" de la web baja de 335,06 a 320,90 EUR. No lo causa index.html; que lo confirme el responsable de premios. Ojo: con el criterio nuevo del 96, ese 0,00 manda tambien sobre un premio confirmado a mano en el navegador.

## No arreglado

- 229 (resto): el script que genero `benchmark_spi_538.json` y el "~0.207" del mercado no tienen dato medido en el repo. Fuera de este paquete.
- 232: versionar `data/jornadas` por temporada es del pipeline. La web hoy no cruza temporadas.
- 178 (segunda mitad): `premio_elige8` separado lo tiene que escribir `calcular_premios.py`.
- 21 (fuera de la web): P7 de la J25 trae `cobertura_autor.activo` y sin embargo `signo_final` = "12". La web ensena lo publicado; la X de autor la tiene que respetar el motor/alineador (indice 1).

## Cambia lo que se ve del boleto?

Si, y es el objetivo del 21. J25, con los contadores de la jornada (4D + 1T):
- antes (web): triple P13, dobles P5 P7 P10 P11, con P7 "X2" y P10 "1X";
- ahora (web = JSON): `1 2 2 1 1X 2 12 1 1 1X2 1X 1 12 1` (triple P10; dobles P5, P7, P11, P13).
Elige 8 con esos contadores: P1 2 3 4 6 9 12 14 (el del motor), 0,50 EUR; total 36,50 EUR.
La prediccion publicada (JSON) no cambia: solo cambia lo que monta el navegador.

## Verificacion

- Sintaxis y comportamiento: pagina cargada en navegador contra un servidor local de solo lectura, sin errores de consola.
- Medido en esa sesion: boleto generado = `signo_final` en los 14 partidos; coste 36,00 / 36,50 EUR con Elige 8; con 2 triples reparte por prioridades (P13 y P10 triples, P7 "X2"); Mixta: quitar la X de P5 pasa a 24 apuestas y "fijo"; todo fijos = 1 apuesta; Historial J23 "pendiente (reducida)"; contexto del chat con limite 2500 -> 2495 caracteres empezando por la prediccion y con el total cobrado; con 6800 -> historial J16..J24, detalle J24, Elige 8 J19..J24.
- `python -m unittest tests.test_aud_P8_web_contratos tests.test_frontend_compuerta tests.test_datos_web_validos`: 42 OK (30 del test nuevo). El test nuevo, contra el index.html de HEAD, falla en 28 de 30.
- Segunda pasada, medido en navegador: reintento 413 de 14.536 -> 6.560 caracteres; orden del historial 59..76 1..24; Mixta con contador 4D->5D: mismo boleto, mismo Elige 8 (P1 2 3 4 6 9 12 14) y 0,50 EUR; en Auto subir un doble cambia el boleto y bajarlo devuelve el del motor.

## Comprobaciones manuales para Marc (en la web publicada)

1. Abrir la web: los contadores salen en 4 dobles y 1 triple. Pulsar "Generar quiniela": el boleto es el del JSON.
2. Activar Elige 8: aparece la linea de 0,50 EUR y el total sube; desactivarlo la quita.
3. Subir un triple: cambia el reparto y el coste; bajarlo: vuelve el boleto del motor.
4. Mixta: quitar un signo de un doble; cambian apuestas, etiqueta "fijo/doble" y avisos.
5. Historial: la J23 sale como "pendiente (reducida)". Al pinchar pide el premio y lo guarda solo en ese navegador.
6. Chat: "Cuanto llevamos ganado?" y "Como fueron las ultimas jornadas?" deben hablar de J16-J24 y del total cobrado, no de J69-J76. La conversacion guardada de J59 en adelante con la clave antigua no se restaura.
7. Quinielas jugadas: fechas de J59-J70 en formato "13 may 2026".
8. Mixta con Elige 8 activo: subir un doble con el contador no debe cambiar los 8 partidos ni el precio si el boleto no se mueve.
9. Chat con una pregunta larga no local (si Groq devuelve 413): debe contestar en el reintento, no "Error 413".

## Decisiones tomadas que conviene conocer

- El interruptor Elige 8 sigue apagado al abrir (cuesta dinero); solo los contadores de dobles/triples arrancan con la estructura publicada.
- Limites del contexto del chat sin cambios (2500 / 6800): solo cambia el orden y la forma de recortar.
