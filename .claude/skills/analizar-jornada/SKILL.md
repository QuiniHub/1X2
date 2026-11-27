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

Método vigente desde el 26/11/2026 (revisado el 27/11/2026). Si la memoria trae una
decisión posterior a esa fecha que contradiga algo de aquí, manda la memoria.

## Repositorio

Todo esto vive en `C:\Users\marcr\1X2` (repo QuiniHub/1X2, publicado en
https://quinihub.github.io/1X2/). Si no se está ya en ese directorio, situarse ahí
antes de leer nada -las rutas de abajo son relativas a esa raíz.

## Las siete reglas que no se discuten

1. **El mercado manda en la probabilidad.** El motor mezcla su número con el mercado
   de Losilla con un peso mínimo de 0,85 (`PESO_MERCADO_MANDA` en
   `motor_prediccion_quiniela.py`). No rebatir una probabilidad con narrativa: lo que
   se decide a mano es QUÉ SE CUBRE, no cuánto vale cada signo.
2. **La predicción se congela al cierre.** Desde el primer partido de la jornada, la
   foto buena es `data/backtesting/pre_cierre/jornada_N.json` (campo `prediccion`).
   `data/predicciones/jornada_N.json` y `ultima_prediccion.json` se regeneran después
   y solo se usan ANTES del primer partido.
3. **Una jornada no se identifica por su número.** La numeración se reinicia cada
   temporada (a mediados de agosto). Siempre se comprueba la fecha (Paso 2).
4. **La estructura del optimizador es la base del boleto** (`optimizador_boleto` en la
   predicción). Se parte de ahí y se ajusta con fútbol, no al revés.
5. **Lo que se nombra con señal, se cubre.** Prohibido "lo avisamos y no lo cubrimos".
6. **Fútbol primero.** A Marc se le habla de fútbol; los porcentajes son cuaderno
   interno y solo salen si él los pide, o en una línea al final.
7. **Nunca se ejecuta la apuesta.** Jugar dinero real lo hace siempre Marc.

## Paso 1: cargar lo ya aprendido (memoria)

Antes de mirar un solo partido, leer la memoria persistente en
`C:\Users\marcr\.claude\projects\C--Users-marcr-1X2\memory\`:

- `MEMORY.md` -el índice; dice qué hay y por qué importa cada archivo.
- `project_state.md` -estado del proyecto y jornada activa a fecha de la última sesión
  (lo más reciente está arriba).
- `feedback_metodo_prediccion_manual.md` -las reglas aprendidas con aciertos y fallos
  reales (incluye los compromisos de la última milla 12 -> 13 y dónde va el 4º doble).
- `feedback_cubrir_lo_que_se_nombra.md`, `feedback_sorpresa_nombrada.md`,
  `feedback_rachas_casa_fuera.md`, `feedback_futbol_primero.md`,
  `feedback_impacto_fallo_temprano.md` -las reglas de Marc que gobiernan los Pasos 3 a 5.
- `project_protocolo_bote.md` -presupuesto según el bote (Paso 4.5).
- `reference_jornadas_europeas.md` -solo si la jornada trae Champions o Europa League.
- `feedback_metodo_auditoria.md`, `feedback_no_pagar_mas.md`, `user_profile.md` -por
  si afectan a esta jornada concreta.

En el repo: `CUADERNO_OJEADOR.md` (la lectura futbolística de cada jornada) y
`DECISION_LOG.md` (el porqué técnico), por si hay algo reciente que la memoria no
haya resumido todavía.

## Paso 2: identificar la jornada POR FECHA y leer lo que dice el motor

**No abrir `data/jornadas/jornada_N.json` "con el número que toque" sin comprobar la
fecha.** En `data/jornadas/` conviven las J1-J27 de la temporada 26/27 con las J28-J76
de la 25/26; cuando la jornada real llegue a la 28, su fichero será todavía el de
diciembre de 2025 hasta que el pipeline lo sobrescriba. Es el error que más veces se
ha repetido en este proyecto.

Cómo hacerlo bien (módulo común `cronologia_jornadas.py`, solo lectura, sin red):

```
python -c "import cronologia_jornadas as cj; a=cj.jornada_en_curso_o_proxima(); c=cj.ultima_jornada_cerrada(); print('activa', a['numero'], a['fecha'], a['temporada']); print('ultima cerrada', c['numero'], c['fecha'], c['temporada'])"
```

- La jornada activa es la que devuelve `jornada_en_curso_o_proxima()`; la última
  jugada, `ultima_jornada_cerrada()`. Las dos por fecha real, nunca por número.
- Antes de usar cualquier `jornada_N.json`, mirar que la fecha de sus partidos es de
  ESTA semana y de la temporada actual. Si la fecha es de otra temporada, ese fichero
  no es la jornada que se está analizando: parar y decirlo.
- Para saber qué se dijo antes del cierre de una jornada ya empezada o cerrada:
  `cj.prediccion_del_cierre(N)` (devuelve la foto pre-cierre solo si es de la misma
  jornada real). No leer `data/predicciones/jornada_N.json` para eso.

Con la jornada confirmada, leer `data/predicciones/ultima_prediccion.json`:

- Comprobar que su `jornada` es la activa y que `generado_en` es reciente.
- **Si la jornada ya ha empezado**, la predicción está congelada (banda de candado en
  la web): es la foto del cierre y ya no se rehace el boleto. Losilla pasa a la
  jornada siguiente en cuanto arranca la actual; unas probabilidades planas (todo
  alrededor del 33%) significan que el motor se quedó sin mercado, no que los partidos
  estén igualados. En ese caso no analizar sobre esos números: avisar a Marc.
- Por partido: `probabilidades` (ya mezcladas con el mercado al 0,85),
  `mercado_losilla`, `signo_final`, `tipo`, `calidad_datos`.
- Bloques de decisión, todos en la misma predicción:
  - `optimizador_boleto` -**la base del boleto**: `signos` (los 14), `triples`,
    `dobles`, `columnas`, `coste_eur`, `alternativas_por_presupuesto` y
    `lectura_contra_masa`. Objetivo publicado: llegar a 13 o más.
  - `sorpresa_nombrada` -la sorpresa que el módulo nombra esta jornada (franja
    20-33%), con sus `senales` y si ya está `cubierta_por_boleto`.
  - `favoritos_en_riesgo`, `radar_tormenta`, `tercero_valor`, `valiente`,
    `columna_valiente` -módulos en sombra: son avisos para leer, no órdenes.
  - `elige8_ev` y `elige8_modos` -la calculadora del Elige 8 (Paso 4.6).
  - `boleto_ev_premio` -lectura del premio esperado; orienta, no decide.
- `data/memoria_ia/porcentajes_lae/<temporada>/jornada_N.json` -lo que juega la masa.
  La masa es el PRECIO de un acierto, nunca el motivo de un signo.

## Paso 3: cruzar contra la realidad de ahora mismo

El motor no tiene ojos fuera de su propio pipeline -el valor de este paso es traerle
lo que a él se le escapa.

**3.1 Tabla de rachas en casa y fuera (obligatoria, regla de Marc 26/11).** Para cada
partido de Primera y Segunda, con `data/calendario_primera.json` y
`data/calendario_segunda.json`: los últimos 5 partidos del local EN CASA y los
últimos 5 del visitante FUERA (puntos por partido y resultados). Cómo se lee:

- Favorito local claro (55% o más) que viene sumando 2,2 puntos o más por partido en
  casa: es el fijo más seguro de la jornada, más de lo que dice el mercado. **No se
  gasta cobertura en él.**
- Una gran racha FUERA del visitante NO es señal de sorpresa (medido: no añade nada
  sobre las cuotas; las rachas fuera regresan).
- Un favorito local en mala racha en casa no cae más de lo que ya dicen las cuotas:
  por sí solo no justifica un doble.

**3.2 Lo demás:**

- `data/clasificaciones_oficiales.json` y `data/memoria_ia/contexto_competitivo.json`
  -clasificación real y qué se juega cada equipo.
- `data/memoria_ia/ceses_actuales.json` (banquillos nuevos) y las fuentes de lesiones
  ya conectadas (LaLiga 1ª/2ª).
- WebSearch de noticias de los equipos de esta jornada: bajas de última hora,
  sanciones, convocatorias, rotaciones por partido europeo entre semana.
- En jornada europea, las señales previas de `reference_jornadas_europeas.md`
  (rotación y bajas, rival en racha, favorito que rinde mal en Europa, césped
  artificial). En Champions la X sale bastante menos que en Liga.
- Abrir la web en vivo con el Browser pane en https://quinihub.github.io/1X2/ y mirar
  qué está mostrando de verdad (Predicción, Historial, Quinielas Jugadas, Liga 26/27,
  Laboratorio). No es opcional: ya se han encontrado bugs donde el JSON era correcto
  y la web no. Usar siempre la URL completa con `/1X2/`, y si parece cacheada, forzar
  recarga con un parámetro nuevo (`?_cb=<numero>`).

## Paso 4: decidir el boleto

1. **Punto de partida: la estructura del optimizador** (`optimizador_boleto.signos`)
   para el presupuesto que diga Marc (ver `alternativas_por_presupuesto`). Si Marc no
   ha dado presupuesto, es el base (Paso 4.5).
2. **Nombrar las sorpresas ANTES de cerrar.** Dos o tres por jornada, siempre en la
   franja del 20 al 30% (el tercer signo de un doble o el signo descartado de un
   fijo), nunca la de postal al 8%. Cada una con su señal futbolística: rival
   empatador, visitante que solo gana fuera, H2H adverso reciente en ese campo,
   banquillo nuevo, favorito en semana de tres partidos. Partir de la que ya nombra
   el bloque `sorpresa_nombrada` y de `favoritos_en_riesgo`.
3. **Cubrir lo que se nombra.** Todo signo nombrado con señal entra en el boleto como
   doble ANTES de poner ningún triple en un partido sin dueño. Orden del dinero: 1X
   en un gigante con señal, y después el triple en el sin dueño. Con un cuarto doble,
   mejor el 2 de un visitante despreciado al 20-25% que una X sobrejugada.
4. **Si el presupuesto no llega para cubrirlo, se dice AL SELLAR** ("la X del Arsenal
   queda fuera por dinero") y se elige a conciencia. Nunca se descubre en la
   retrospectiva.
5. **No gastar cobertura** en los fijos de casa del punto 3.1.
6. **La hora cuenta.** Fallar un fijo que se juega pronto baja el techo a 13 para toda
   la jornada: a lecturas parecidas, la cobertura va antes al partido del sábado
   temprano que al del domingo. Es una lectura manual; como bono automático en el
   motor se probó y se rechazó.
7. **No pelear con narrativa un partido igualado** (`calidad_datos: "baja"`): ahí ni
   el motor ni el análisis tienen ventaja, y desviarse sin motivo es de donde vinieron
   la mayoría de los fallos de las retrospectivas.
8. **Un solo boleto.** Marc no quiere carteras de dos boletos: lo que no cabe en una
   única estructura, no se juega.

El listón de diseño es el 13 o más: lo que recupera dinero. El "entrar en premio" con
10 u 11 no se usa como argumento.

## Paso 4.5: presupuesto y protocolo de bote

Mirar primero el bote que publica LAE (la cifra "un único acertante puede ganar").

- Sin bote, presupuesto base: lo que Marc diga esa semana (la referencia acordada
  es de 27 a 40 EUR; hay semanas de 18).
- Bote de 2 millones o más: referencia de unos 108 EUR. Bote de 4 millones o más:
  referencia de unos 180 EUR.
- El dinero extra compra COBERTURA DE SEÑALES (las sorpresas nombradas, las X con
  señal, los partidos de caos), jamás más favoritos.
- Es una referencia para la conversación, no una regla que se imponga: se cita el
  dato y decide Marc. Y siempre dentro de UN boleto.

`boleto_millonario` sigue existiendo en la predicción como lectura "a por la
sorpresa" (señal solo de LaLiga y Segunda; con `total_cambios: 0` no hay nada que
contar). Ya no es la alternativa principal: se menciona solo si trae un cambio con
evidencia real que no esté ya entre las sorpresas nombradas.

## Paso 4.6: Elige 8, solo como calculadora

El Elige 8 no participa del bote y solo paga el 8 de 8; el jueves de jornada europea
ha pagado unos 2 EUR. Por eso:

- `elige8_ev` y `elige8_modos` son una CALCULADORA informativa: dicen cuánto cuesta y
  qué cabría esperar de cada regla. No son una recomendación de jugarlo. Si
  `bandera_recomendado_publicable` es falso o `alguna_recomendada` es falso, se dice
  tal cual y no se empuja.
- Jugarlo o no lo decide Marc. Si lo juega, siempre modesto, y antes de darlo por
  bueno se cruzan los 8 partidos elegidos con los avisos del Paso 3 y con las
  sorpresas nombradas: si un partido elegido tiene aviso, se le dice a Marc ANTES de
  confirmar (no se excluye en automático; se decide sabiéndolo). Si ninguno lo
  tiene, se dice también.
- Recordar que cada doble o triple DENTRO de los 8 elegidos multiplica el coste del
  Elige 8.

## Paso 4.7: pedir la corazonada de Marc

Antes de cerrar un partido igualado, o cualquier sorpresa nombrada, preguntar a Marc
qué ve él -primera pregunta: "¿qué viste?"-, sin esperar a que lo saque por su cuenta.
Si su corazonada choca con el dato, no se le rebate con un porcentaje: se discute como
fútbol y cuenta como una entrada real en la decisión. Caso fundacional (J76, 07/08):
Marc propuso dos veces un signo, se le convenció dos veces con datos de que no, y
salió su signo. Esto no autoriza a Claude a inventarse una narrativa sobre la marcha:
la corazonada de quien lleva décadas viendo fútbol es evidencia; la ocurrencia del
momento, no.

## Paso 5: presentar la recomendación (fútbol primero)

Sin tablas de porcentajes. El orden es este:

```
JORNADA <N> (<fechas>) -bote <cifra o "sin bote"> -cierra <día y hora>

Cómo viene la jornada: <3 o 4 frases de fútbol: qué partidos tienen dueño, cuáles
no, qué equipo llega tocado y por qué>

Las sorpresas que nombro:
1. P<n> <local>-<visitante>, <signo>: <la señal, en fútbol>  -> CUBIERTA con <1X / X2 / triple>
2. P<n> ...                                                   -> CUBIERTA con ...
3. P<n> ...                                                   -> FUERA POR DINERO (lo decido ahora, no después)

Los fijos de casa que no toco: P<n> <equipo> (<racha en casa en una frase>), ...

Boleto (<T> triples + <D> dobles, <columnas> columnas, <coste> EUR):
P1 <local>-<visitante>: <signos>
...
P14 ...
Pleno al 15: <marcador>

Respecto a la estructura del optimizador: <"igual" o qué cambio y por qué, en fútbol>

Elige 8: <"no lo aconsejo esta semana" / "si lo quieres jugar: P.., coste .., y
P<n> tiene este aviso">

¿Qué ves tú en <los 2 o 3 partidos abiertos>?
```

Los números (probabilidad de 13 o más, masa, premio esperado) se dan solo si Marc los
pide, o en una única línea final. La tabla de rachas del Paso 3.1 es trabajo interno:
se enseña si la pide; lo que se le cuenta es lo que significa.

## Regla dura: nunca ejecutar la apuesta de verdad

Esto es una recomendación para que Marc decida. Jugar dinero real es una acción que
SIEMPRE hace él manualmente -nunca ejecutarla ni dar a entender que ya está jugada.
Si Marc confirma después (normalmente con una captura del boleto real) que la jugó,
entonces sí: añadir la entrada a `data/quinielas_jugadas.json` con
`"origen": "confirmado_por_marc_en_chat"`, con el mismo formato que las anteriores, y
anotar en ella las sorpresas nombradas y cuáles quedaron cubiertas.

## Paso 6: cuando una jornada ya jugada cierra

- Confirmar por FECHA que el `jornada_N.json` que se lee es el de la jornada jugada
  (Paso 2), y comparar lo jugado (`data/quinielas_jugadas.json`) con `signo_oficial`.
- Lo que "dijo el sistema" es la foto pre-cierre (`cj.prediccion_del_cierre(N)`), no
  el fichero de `data/predicciones/`, que se reescribe después.
- La retrospectiva habla claro: si cayó algo nombrado y sin cubrir, es "vista y no
  pagada" y cuenta como error de método propio. Prohibido "ningún dato lo daba". Solo
  si todo lo nombrado estaba cubierto y cayó otra cosa fue una sorpresa de verdad.
- Tras una jornada loca no se toca nada del motor: se anota y se sigue.
- Apuntar `premio_eur` (0 si no hubo), los aciertos, y actualizar la memoria:
  `project_state.md`, `feedback_metodo_prediccion_manual.md` si se confirma o corrige
  una regla, `CUADERNO_OJEADOR.md` con el porqué futbolero, y
  `data/memoria_ia/memoria_socio.json` (alimenta el chat de la web; máximo 2.600
  caracteres en el bloque del chat).

## Nota sobre cómo se invoca esto

Este skill debe funcionar igual si Marc lo escribe a mano un sábado por la mañana en
un chat recién abierto que si lo dispara una tarea programada sin que él esté
delante. En ambos casos, empezar SIEMPRE por el Paso 1 -no asumir que se conoce el
contexto por una conversación anterior. En una ejecución sin Marc delante no se le
puede preguntar la corazonada: se deja escrita la pregunta al final del informe. Lo
único que nunca cambia: la decisión de jugar dinero real es siempre de Marc.
