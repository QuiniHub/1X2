---
name: analizar-jornada
description: >
  Analiza la jornada activa de La Quiniela LAE (fútbol español) antes de que cierre
  el plazo de apuestas: lee la memoria del proyecto, cruza la predicción automática
  del motor (data/predicciones/ultima_prediccion.json) contra datos reales de HOY
  (clasificaciones, lesiones, contexto competitivo, noticias) y prepara una
  recomendación de boleto siguiendo el método que Marc y Claude ya han validado en
  jornadas anteriores. Úsala SIEMPRE que Marc escriba /analizar-jornada, o pida cosas
  como "analiza la jornada", "prepara la quiniela de esta semana", "qué jugamos",
  "mira los partidos de esta semana", "vamos a decidir el boleto" -incluso si no da
  rutas de archivo ni explica contexto, porque este skill ya sabe dónde está todo.
  También se dispara si una tarea programada (cron/schedule) pide "ejecuta el
  análisis pre-cierre de la quiniela".
---

# Analizar la jornada de La Quiniela IA

Este skill existe para que no haga falta explicar desde cero, cada vez que se abre
un chat nuevo, qué es este proyecto y cómo se decide una quiniela. Todo lo necesario
ya está guardado -el trabajo aquí es leerlo, no adivinarlo ni reconstruirlo de memoria.

## Repositorio

Todo esto vive en `C:\Users\marcr\1X2` (repo QuiniHub/1X2, publicado en
https://quinihub.github.io/1X2/). Si no se está ya en ese directorio, situarse ahí
antes de leer nada -las rutas de abajo son relativas a esa raíz.

## Paso 1: cargar lo ya aprendido (memoria)

Antes de mirar un solo partido, leer la memoria persistente en
`C:\Users\marcr\.claude\projects\C--Users-marcr-1X2\memory\`:

- `MEMORY.md` -el índice; dice qué hay y por qué importa cada archivo.
- `project_state.md` -estado del proyecto y jornada activa a fecha de la última sesión.
- `feedback_metodo_prediccion_manual.md` -las reglas ya aprendidas a base de aciertos
  y fallos reales: no pelear con narrativa un toss-up real cuando el motor marca
  `calidad_datos: "baja"` (el análisis retrospectivo de J71-73 mostró que 8 de 11
  fallos vinieron de desviarse ahí sin motivo), el Elige8 paga mal en la práctica
  (revisar los números reales antes de incluirlo), usar clasificaciones reales para
  AJUSTAR el motor, no para inventar una historia por encima de él.
- `feedback_metodo_auditoria.md`, `feedback_no_pagar_mas.md`, `user_profile.md` -por
  si afectan a esta jornada concreta.

Si `DECISION_LOG.md` (en la raíz del repo) tiene algo reciente sobre el motor o el
pipeline que la memoria no haya resumido todavía, revisarlo también.

## Paso 2: identificar la jornada y lo que dice el motor

- `data/predicciones/ultima_prediccion.json` -la predicción automática vigente:
  probabilidades, `signo_final`, `tipo` (FIJO/DOBLE/TRIPLE), `incertidumbre` y
  `calidad_datos` por partido. Este es el punto de partida, no el resultado final:
  el motor no tiene presupuesto real ni cruza datos externos, solo estadística.
- `data/jornadas/jornada_N.json` (con el número que toque) -equipos, fechas y cierre
  de plazo real. Si no está claro qué jornada es la activa, este archivo y
  `project_state.md` lo confirman.

## Paso 3: cruzar contra la realidad de ahora mismo

El motor automático no tiene ojos fuera de su propio pipeline -el valor de este paso
es traerle lo que a él se le escapa:

- `data/clasificaciones_oficiales.json` y `data/memoria_ia/contexto_competitivo.json`
  -clasificación real y qué se juega cada equipo (título, descenso, ascenso, playoff...).
- Las fuentes de lesiones ya conectadas (scraper de LaLiga 1ª/2ª).
- WebSearch de noticias recientes de los equipos de esta jornada concreta: lesiones
  de última hora, sanciones, rachas, bajas -lo que el motor no puede ver porque no
  navega por su cuenta.
- Abrir la web en vivo con el Browser pane en https://quinihub.github.io/1X2/ y mirar
  qué está mostrando de verdad: la pestaña de Predicción (lo que dice el motor ahora
  mismo), Historial y Quinielas Jugadas (resultados reales ya cerrados), y Liga 26/27
  (clasificación). Esto no es un paso opcional de más: en la sesión del 2026-07-22 se
  encontraron 4 bugs reales donde el archivo de datos era correcto pero lo que se
  veía en la web estaba mal o desactualizado -leer solo el JSON no los habría
  detectado. Ojo: la raíz `https://quinihub.github.io/` sin `/1X2/` puede dar 404 o
  servir caché vieja -usar siempre la URL completa con `/1X2/`, y si la respuesta
  parece cacheada, forzar una recarga con un parámetro nuevo en la URL
  (`?_cb=<numero>`).

## Paso 4: aplicar el método y decidir

Con la predicción del motor + los datos reales + las reglas de memoria, decidir
signo por partido, si el Elige8 compensa esta vez, y cómo repartir el presupuesto
que dé Marc entre fijos/dobles/triples. Si Marc da un presupuesto máximo, la
distribución la decide quien ejecuta este skill -es parte de lo que ya se sabe hacer.

## Paso 4.5: ofrecer también la versión "millonaria" (a por el bote)

`data/predicciones/ultima_prediccion.json` ya trae un campo `boleto_millonario`
(generado por `construir_boleto_millonario()` en `motor_prediccion_quiniela.py`)
con la alternativa "a por la sorpresa" a la recomendación conservadora de siempre.
La diferencia con simplemente "jugar el partido más incierto al revés": cada
partido ahí marcado (`riesgo_millonario.candidato = true`) tiene evidencia
contextual real detrás, no solo ruido estadístico -un partido reñido sin motivo de
fondo NO se marca como candidato, precisamente para no confundir "ir a por el bote"
con "tirar un dado". Esa evidencia viene de 3 fuentes reales, ampliadas el
2026-07-24 a petición de Marc:
- `patrones_competitivos.json` -objetivos de clasificación (descenso, necesidad,
  objetivo cerrado), sacados de las 3 temporadas completas en
  `data/memoria_ia/historico_ligas_espana.json` (2023/24, 2024/25, 2025/26).
- `historial_enfrentamientos.json` -historial de enfrentamientos directos entre
  cada par exacto de equipos en esas 3 temporadas, usando las cuotas de mercado de
  cada partido histórico para saber quién era favorito.
- Clase pura por posición en la tabla (top 10 contra la segunda mitad), sin mirar
  objetivos -el motor ya sabe, por ejemplo, que un equipo del top 10 falla en ganar
  fuera de casa contra uno de la segunda mitad más de 6 de cada 10 veces.

**IMPORTANTE**: toda esta señal es 100% LaLiga/Segunda -Marc decidió explícitamente
que no quiere esto para las quinielas de ligas nórdicas (Noruega/Suecia) que se
juegan mientras LaLiga está de vacaciones. Con partidos no españoles, `boleto_millonario`
saldrá siempre con `total_cambios: 0` -eso es lo esperado, no un fallo. Se activará
de verdad en cuanto La Quiniela vuelva a tener partidos de LaLiga -arranque real
verificado el 15/08/2026 (no 16, corregido), con la jornada 1 repartida de forma
asimétrica hasta el 27/08 por el Mundial 2026 recién acabado, así que puede que la
primera Quiniela con partidos de LaLiga no tenga los 14 partidos españoles de golpe.

Al presentar la recomendación, mencionar si `boleto_millonario.total_cambios > 0`:
qué partidos cambiarían, por qué (`justificacion` de cada cambio), y dejar que Marc
decida si quiere jugar la conservadora, la millonaria, o combinar ambas -no decidir
esto por él. Si `total_cambios == 0` esa jornada, decirlo también: significa que no
hay ningún partido con evidencia real suficiente, así que las dos recomendaciones
coinciden esta vez.

## Paso 4.6: cruzar el Elige8 con los avisos cualitativos de esta jornada (si se juega Elige8)

**Gap real detectado en la jornada 75 (2026-08-02), sigue sin código que lo cubra a
propósito -es un paso manual, no automático.** `aplicar_elige8_seguro.py` rankea los
partidos para el Elige8 solo por margen de mercado/`eficiencia_elige8()` (probabilidad
entre coste) -no sabe nada de las señales cualitativas que se investigan aparte en el
Paso 3 (WebSearch, `historial_enfrentamientos.json`, racha perdedora, contexto
competitivo). En J75 esto costó un fallo evitable: P8 (Molde-Sarpsborg) entró en el
Elige8 por su margen de mercado (58,75%) pese a que el propio análisis ya había
encontrado un aviso real sobre ese partido (Sarpsborg ya le había ganado a Molde esa
temporada, mejor forma reciente) -el aviso nunca se cruzó con la selección antes de
confirmarla.

Si esta jornada se va a jugar Elige8, antes de darlo por definitivo:

1. Repasar la lista de partidos que recibieron algún aviso cualitativo real durante
   el Paso 3 (H2H desfavorable al favorito, racha perdedora del rival sin rebote,
   lesión de un titular clave, rival con objetivo ya cerrado sin nada en juego, etc.)
   -no hace falta un archivo nuevo, es lo que ya se comentó/decidió en la
   conversación de esta misma jornada.
2. Comparar esa lista contra los 8 partidos elegidos para el Elige8 (los que
   proponga `aplicar_elige8_seguro.py`, o los que decida Marc a mano).
3. Si hay coincidencia, decirlo explícitamente a Marc ANTES de confirmar -no excluir
   el partido en automático, el margen de mercado puede seguir siendo el más alto de
   la jornada y justificar incluirlo igualmente, pero la decisión debe tomarse
   sabiendo que existe ese aviso, no ignorándolo por mirar solo el número.
4. Si no hay ningún partido del Elige8 con aviso pendiente, decirlo también -confirma
   que la selección está limpia, no es un paso que se pueda omitir en silencio.

Ver `feedback_metodo_prediccion_manual.md` (memoria persistente, Paso 1) para el caso
real de J75 completo.

## Paso 5: presentar la recomendación así

```
JORNADA <N> -recomendación pre-cierre
P1: <equipo> - <equipo>  ->  <signo>  (motor decía: <signo_final>, calidad_datos: <valor>)
...
Pleno 15: <marcador>
Coste total: <X>€ (<Y> combinaciones)
Por qué: <2-3 frases citando el dato real concreto que justifica cada desviación
respecto al motor, y confirmando explícitamente en qué partidos NO se cambia nada
aunque tiente hacerlo, porque calidad_datos baja significa que ahí ni el motor ni
el análisis manual tienen ventaja real>

Si hay alternativa millonaria (boleto_millonario.total_cambios > 0):
Versión "a por el bote" -cambia <N> partido(s):
P<num>: <signo conservador> -> <signo millonario>  (<justificación real, no ruido>)
...

Si se juega Elige8 (Paso 4.6):
Elige8: P<a>, P<b>, ... P<h>
Cruce con avisos cualitativos: <"limpio, ningún partido elegido tiene aviso pendiente"
  o "P<num> tiene un aviso (<motivo>) pese a estar elegido por margen de mercado -
  se mantiene/se cambia por <decisión y motivo>">
```

## Regla dura: nunca ejecutar la apuesta de verdad

Esto es una recomendación para que Marc decida. Jugar dinero real es una acción que
SIEMPRE hace él manualmente en loteriasyapuestas.es -nunca ejecutarla ni dar a
entender que ya está jugada. Si Marc confirma después (normalmente con una captura
de pantalla del boleto real) que la jugó tal cual, entonces sí: añadir la entrada a
`data/quinielas_jugadas.json` con `"origen": "confirmado_por_marc_en_chat"`, siguiendo
el mismo formato que las entradas anteriores en ese archivo.

## Paso 6: cuando una jornada ya jugada cierra con resultados reales

Comparar `signo`/`pleno15` jugados contra `signo_oficial`/resultado real en
`data/jornadas/jornada_N.json`, calcular aciertos/fallos, y **actualizar la memoria**
(`feedback_metodo_prediccion_manual.md` o `project_state.md`, según corresponda) con
lo que se confirma o lo que se corrige. Esto es lo que hace que la próxima vez que
alguien invoque este skill -en otra sesión, o el cron de la red de seguridad- arranque
sabiendo más que hoy. Sin este paso, el ciclo de aprendizaje se rompe.

## Nota sobre cómo se invoca esto

Este skill debe funcionar igual de bien si Marc lo escribe a mano un sábado por la
mañana en un chat recién abierto, que si lo dispara un cron/schedule automático sin
que él esté delante. En ambos casos, empezar SIEMPRE por el Paso 1 -no asumir que ya
se conoce el contexto por una conversación anterior, porque técnicamente no se
recuerda. Lo único que nunca cambia pase lo que pase: la decisión de jugar dinero
real es siempre de Marc.
