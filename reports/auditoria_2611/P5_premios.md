# Auditoria 26/11 - paquete P5_premios

Tests: `python -m unittest tests.test_aud_P5_premios_auditoria` (50 tests) mas los ya existentes de
los modulos del paquete (220 tests en total, todos en verde).

## Arreglado

- **7 / 12 / 40 - recaudacion de J23 = 294 M EUR.** `_numero_es` decide el separador decimal por el ULTIMO
  separador ("2940306.75" ya no se multiplica por 100). `parsear_escrutinio_html` valida el rango 0,3-20 M y,
  si no cuadra, reconstruye desde la 3a categoria. `recaudacion_estimada` usa `recaudacion_de_escrutinio`
  (modelo_reparto_quiniela) y `optimizador_boleto.recaudacion_media_plausible` delega en ella: una sola
  implementacion. Dato reparado a mano: `porcentajes_lae/2026_2027/jornada_23.json` -> 2.940.306,75 EUR
  (28.917 x 7,63 / 7,5%). Media de la temporada: 14.774.663,87 -> 1.993.932,70 EUR (23 escrutinios: el placebo de la J14, todas las
  categorias a 0, ya no aporta su recaudacion declarada de 3.488.166 a la media).
- **11 / 25 / 97 - tablas de premios de otra jornada.** Se elimina la URL generica de loteriaanta, la pagina
  debe nombrar "Jornada N", la categoria va anclada a "N aciertos", se valida la monotonia de la tabla y el
  escrutinio versionado (porcentajes_lae/<temporada>/jornada_N.json) manda sobre las webs. Historial
  reparado: J8 3,93 -> 0; J15 6,82 -> 0; J19 3,41 -> 0 (fuente `escrutinio_versionado`); J4 y J10 con su
  tabla real; J59/J60/J62/J73/J74 sin tabla placebo.
- **72 / 129 - colision por numero de jornada.** `jugada_por_jornada` casa por temporada del fixture
  (cronologia_jornadas) y numero; `historial_premios` lleva `temporada`; ya no se siembran registros
  "0 aciertos confirmados" sin boleto y se han purgado J22 y J25-J58 (35 registros sin detalle).
  `quinielas_jugadas.json`: solo se anade `temporada` a cada jugada.
- **26 / 230 - memoria_socio.** J16 24,26; J18 13/14 con 0 EUR; J14 32,74 marcado "sin verificar".
  Bloque de 2.560 caracteres (< 2600) y `actualizado_en` al 27/11.
- **71 / 103 - Pleno al 15.** M = P(3 o mas goles); las cuatro casillas suman 100. El motivo de
  "sin_recomendacion" ya no dice que la prediccion este bloqueada (que el motor de probabilidades al
  partido 15 es de otro paquete).
- **124 / 175 - variante elegida a posteriori.** No se cambia la variante (P13plus). El bloque dice que la
  prerregistrada (premio_esperado sin contra_masa) NO supero el backtest: `aviso`, `aviso_seleccion`,
  `veredicto_variante_prerregistrada`, y el texto de `veredicto_variante_publicada` que pinta la web
  (el valor a secas queda en `veredicto_variante_publicada_bruto`). El backtest con `--rapido` ya no se
  contradice en sus criterios.
- **53 / 102 - escrutinio placebo.** No se guarda una plantilla a cero y la ya guardada (J14) se vuelve a
  pedir en el siguiente ciclo (el dato de J14 no se toca a mano).
- **136 / 243.** `temporada_etiqueta` usa cronologia_jornadas (corte real de agosto, con numero de jornada);
  no se hereda el escrutinio si los equipos no coinciden; el cierre aproximado convierte Madrid -> UTC.
- **145.** Tavily: "12.50" es 12,50 y no 1250.
- **218.** `aplicar_elige8_seguro.detectar_jornada_activa` elige por `generado_en`, no por numero.

## Efecto en la J25 (medido en local, sin escribir en data/)

| Bloque | Publicado | Con los arreglos |
|---|---|---|
| boleto_ev_premio: recaudacion | 14.774.663,87 EUR | 1.993.932,70 EUR |
| boleto_ev_premio: EV | 51,61 EUR | 42,91 EUR (solo por la recaudacion) |
| optimizador_boleto: signos (18 col.) | 1 2 2 1 1 2 1X2 1 1 1X 1 1 1X2 1 | los mismos |
| optimizador_boleto: P(>=13) | 3,85% | 3,85% |
| optimizador_boleto: premio esperado | 6,34 EUR | 6,34 EUR |

Los dos bloques son informativos / modo sombra: no cambian los signos de la prediccion ni el boleto base.

## Pendiente de decision de Marc

- **150 - segunda mezcla con Losilla (NO aplicado; interruptor apagado).** El motor ya publica 0,15 motor +
  0,85 mercado y los optimizadores lo vuelven a mezclar al 50% con Losilla: el mercado pesa ~0,925. Quitar
  esa mezcla es una decision de pesos, asi que queda en `optimizador_ev_premio.EVITAR_SEGUNDA_MEZCLA = False`
  (mezcla de siempre). Los bloques solo informan: `fuente_probabilidad` (con el aviso),
  `partidos_con_mercado_ya_integrado` (J25: 14), `partidos_sin_segunda_mezcla` (0) y
  `partidos_con_traza_mercado_sin_peso` (0; sube si el motor cambia el texto de la traza).
  Numeros para decidir (J25, medidos con el interruptor encendido): P7 1X2 -> 12, P10 1X -> 1X2,
  P(>=13) 3,85% -> 3,91%, premio esperado 6,34 -> 6,75 EUR, EV del boleto_ev_premio +0,85 EUR.
  Si se enciende: alinear `elige8_ev.probs_mix` (otro paquete) y repetir el backtest con la fuente nueva.
  Conviene ademas que el motor escriba `ajuste_mercado_losilla["peso"]` numerico (hoy el peso se lee de la
  frase "integrado con peso 0.85").
- **75** umbral de 1,5 EUR y traspaso de fondo a la categoria superior en el modelo de reparto (cambia el EV).
- **147** tipo de jornada de Elige 8 y premio tipico domestico (578,70 EUR es de la 25/26; mediana 26/27 ~94).
  El orden del pipeline es de otro paquete.
- **99** premio_eur de J19 y J23 en quinielas_jugadas (hace falta el escrutinio de la operacion en Losilla).
- **179** J21: importe_total 4,5 EUR sin Elige 8 (7,5 si se jugo).

## No tocado

- **67** aprendizaje_modulos.py no es de este paquete (el dato de J23 ya esta reparado; el placebo de J14
  sigue contando alli). `elige8_ev.probs_mix` (hallazgo 150) tampoco es de este paquete y sigue con 50/50.
- **177** y **180** aplazados (bajos): redistribucion LAE en el C1 del backtest y Pleno al 15 en el
  calculo multicolumna.

## Segunda pasada (revision independiente)

- **72** `main()` separa el historial por temporada al cargarlo: con dos registros del mismo numero, el que
  no es de la temporada del fixture se reescribe siempre tal cual (antes se perdia en el segundo guardado).
  Test que ejecuta `main()` varias veces.
- **150** revertido a interruptor apagado (ver arriba).
- **Tests de datos vivos** suavizados para que no paren el pipeline: memoria_socio solo con aserciones
  negativas y limite 2600; historial solo J8/J15/J19; jugadas solo si la temporada contradice la fecha.
- **Elige 8 con tabla versionada.** Si se acerto el Elige 8 y la tabla no trae su premio, el registro no se
  cierra a 0 `escrutinio_versionado` y el multicolumna queda marcado `elige8_premio_pendiente` (sigue
  pendiente hasta que la web lo de o Marc declare el premio). La etiqueta `multicolumna_loteriaanta` no se
  renombra (la leen otros modulos).
- **loteriaanta.** `html_es_de_jornada`: se ignoran select/option/nav; si los titulares nombran jornada debe
  ser solo la pedida; sin titulares, debe ser la unica nombrada. No verificado contra la web real (sin red).
- **--rapido.** Si el backtest no midio la variante prerregistrada, el bloque dice "no se calculo", no
  "NO supero".
- **Aviso para index.html (otro paquete):** `backtest.veredicto_variante_publicada` es una frase, el valor
  corto esta en `veredicto_variante_publicada_bruto`.
