# Registro de decisiones — Quiniela IA (1X2)

Por qué se tomaron las decisiones técnicas importantes de este proyecto. El objetivo
de este archivo es que el motivo quede en el propio repositorio, no solo en la
memoria de una sesión de IA concreta — para que si alguien (o alguna sesión futura)
lee el código y algo le parece raro o "mejorable", compruebe aquí primero si ya se
decidió así a propósito antes de cambiarlo.

Formato: fecha, qué se decidió, por qué. Entradas nuevas siempre al final.

---

### 2026-07-03/04 — Los scripts que "parcheaban" el motor por regex quedaron eliminados

Había ~7 scripts (`aplicar_patrones_motor.py`, `reforzar_patrones_motor.py`, etc.)
que reescribían con regex el código fuente de `motor_prediccion_quiniela.py` o de
`index.html` en cada ejecución del pipeline, en vez de tener el cambio ya
permanente en el archivo. Se verificó uno a uno que lo que aplicaban ya vivía de
forma permanente en el motor (por eso ya no hacían nada real) antes de borrarlos.
**Por qué importa:** si en el futuro un script vuelve a "auto-parchear" otro
archivo de código en cada run, es una señal de alarma — ese patrón ya causó
confusión y se decidió activamente evitarlo.

### 2026-07-04 — El `>` en `evaluar_descenso()` es correcto, no un bug

`generar_contexto_competitivo.py`: `salvado = equipo["puntos"] > equipo_descenso["maximo_puntos"]`.
Un script ya borrado proponía cambiarlo a `>=`. Se confirmó que `>` es correcto
por consistencia interna del propio archivo: la lógica de título de liga ya
distingue `>` (matemáticamente garantizado) de `>=` (depende de desempates, no
garantiza nada). Empatar a puntos con el equipo de descenso NO salva a nadie
automáticamente.
**Por qué importa:** parece "obviamente" un `>=` a primera vista. No lo cambies
sin releer esto.

### 2026-07-04 — Se quitaron las comprobaciones hardcodeadas de Oviedo/Racing/Deportivo

`control_calidad_actualizacion.py` tenía afirmaciones fijas sobre cómo terminó la
temporada 2025/26 (quién subió/bajó), sin guarda de fecha. Iban a marcar "crítico"
falso en cuanto arrancara la Liga 26/27 con esos mismos equipos ya en otra
categoría.
**Por qué importa:** cualquier comprobación que dé por hecho "quién juega dónde
esta temporada" caduca solo. Si se necesita algo así, debe llevar guarda de
fecha/temporada, no ser permanente.

### 2026-07-04 — El precio real de la Quiniela es 0.75€/apuesta (no 1.50€)

`motor_prediccion_quiniela.py` y `aplicar_elige8_seguro.py` tenían
`PRECIO_APUESTA = 1.50`, pero el precio real de La Quiniela LAE es 0.75€ por
apuesta/columna (mínimo 2 apuestas = 1.50€). `alinear_boleto_con_analisis.py` ya
tenía el valor correcto desde antes — como varios scripts escriben el coste en
distintos momentos del pipeline, el número final mostrado dependía de cuál
hubiera corrido último. Corregido en los 3 sitios + `index.html`, usando siempre
`max(apuestas * 0.75, 1.50)` (0.75€/apuesta con suelo de 1.50€ mínimo).
**Por qué importa:** si alguna vez el coste mostrado no cuadra con 0.75€/apuesta,
es un regreso de este mismo bug, no un cambio de precio real.

### 2026-07-04 — Al cambiar una constante con datos ya comprometidos en git, el pipeline se puede autobloquear

El workflow ejecuta "Ejecutar pruebas" ANTES de "Actualizar datos" en el mismo
job. Si un test empieza a exigir un valor nuevo (p. ej. el precio de arriba) pero
el dato ya guardado en el repo se generó con el valor viejo, el test falla en
cada ejecución programada — y como nunca llega al paso que regeneraría ese dato,
el pipeline queda bloqueado indefinidamente, no solo una vez.
**Regla:** antes de cambiar una constante usada en un test de calidad, comprobar
si el dato real ya en git pasaría el test nuevo. Si no, corregir el dato VIVO
(nunca el histórico/inmutable) en el mismo cambio que el código.

### 2026-07-04 — Los snapshots de `data/backtesting/pre_cierre/*.json` nunca se tocan a toro pasado

Están marcados `"inmutable": true` a propósito: sirven para comparar honestamente
qué predijo el motor ANTES de saber el resultado, tal cual pasó en su momento.
Cuando se corrigió el bug de precio de arriba, esos snapshots se quedaron con el
precio viejo (216€ en vez de 108€) — y se dejaron así aposta, en vez de
"corregirlos" con el precio nuevo.
**Por qué importa:** reescribir un snapshot inmutable para que cuadre con un fix
posterior sería revisionismo — perdería el sentido de tener snapshots honestos.
Si algún día hace falta re-evaluar backtesting con el precio correcto, se hace en
un cálculo aparte, sin tocar el archivo original.

### 2026-07-04 — El aprendizaje general del motor compara predicción vs realidad, no "lo jugado" vs realidad

`actualizar_aprendizaje_ia.py` (pesos dinámicos, patrones) siempre gradúa la
predicción CRUDA del motor contra el resultado real, no lo que el usuario haya
confirmado jugar. Esto es intencional, confirmado explícitamente por Marc: quiere
que el motor aprenda de sus propios aciertos/fallos/sorpresas para mejorar la
predicción en sí, independientemente de si alguna vez el usuario ajusta algo a
mano en modo Manual/Mixta.
**La única excepción real:** `ajustar_aprendizaje_elige8.py` sí usa
`data/quinielas_jugadas.json` (lo REALMENTE jugado) porque ahí se trata de dinero
real (premio cobrado/escapado), no de mejorar el modelo.
**Por qué importa:** no "arregles" esto para que use `quinielas_jugadas.json` en
todos los sitios — sería cambiar una decisión de diseño ya confirmada.

### 2026-07-04 — `data/quinielas_jugadas.json` es la pieza que faltaba para que todo el aprendizaje real funcionara

El botón "Confirmar quiniela jugada" llevaba tiempo sin guardar nada de verdad
(leía datos vía la API de GitHub, los reconstruía... y los tiraba). Se arregló
para que abra un Issue de GitHub prellenado con el payload exacto que ya procesa
`.github/workflows/importar-memoria-quinielas.yml` (guardado seguro, sin token en
el navegador). Esto desbloqueó una maquinaria de aprendizaje que ya estaba bien
construida (`construir_memoria_ia.py:analizar_nuestras_quinielas()` →
`construir_pesos_dinamicos()`) pero llevaba tiempo sin recibir datos reales.
**Por qué importa:** sin jugadas confirmadas de verdad en ese archivo, el
Elige 8 nunca aprende de lo realmente jugado, por muy bien construido que esté el
resto del sistema.

### 2026-07-04 — Los umbrales de muestra mínima (28 partidos, 100 partidos) son deliberados

`construir_pesos_dinamicos()` no ajusta pesos con menos de 28 partidos validados.
`calibrar_probabilidades.py` y `evaluar_valor_senales.py` no sacan conclusiones
con menos de 100 partidos evaluados. Son barreras a propósito para no
sobrerreaccionar a una sola jornada rara o a una racha corta.
**Por qué importa:** si un panel dice "sin muestra suficiente" no es un fallo del
sistema — es la protección funcionando. No bajar estos umbrales para "que salga
antes" un resultado.

### 2026-07-04 — El calendario de Liga 26/27 con resultados en vivo se aparcó a propósito

`data/calendario_1a_2627.json`/`calendario_2a_2627.json` es un snapshot estático
de un solo commit (1 jul 2026, cuando se publicó el sorteo oficial). No tiene
ningún campo de resultado ni script que lo actualice. Se investigó laliga.com
como posible fuente (JS-heavy, sin API pública gratuita conocida) y se descartó.
Decisión consciente de Marc: dejarlo así hasta que se acerque agosto 2026, ya que
hasta entonces no hay resultados reales que mostrar de todos modos.
**Por qué importa:** no es un bug sin arreglar, es una decisión de prioridad.

### 2026-07-04 — 2 scripts huérfanos y una referencia a rama muerta, eliminados

`actualizar_calendario.py` (parche manual de un resultado concreto, jornada 35
2025/26, ya superado) y `registrar_actualizacion_ok.py` (heartbeat de fin de
pipeline, nunca conectado) no tenían ninguna referencia externa en todo el repo
— confirmado con búsqueda exhaustiva antes de borrar. `ci-pr.yml` referenciaba la
rama `fix/invisible-stability`, ya borrada hace tiempo.

### 2026-07-04 — Comparativa con Rastipunk/Quiniela-Platform (Picks4All): no es código reutilizable

Es una plataforma social de quinielas entre amigos (pagos, multi-idioma, sin IA
predictiva) — un producto distinto al nuestro, no comparable directamente.
Licencia propietaria ("all rights reserved... educational purposes only"): nada
de su código puede copiarse. Se aprovechó solo una idea de formato (este mismo
archivo) y se verificó una lección suya (versionado de resultados / bloqueo de
fase ante correcciones) contra nuestro `aplicar_correcciones_resultados.py` — ya
estamos cubiertos (dejamos rastro con `corregido_en`/`correccion_motivo` y el
script corre antes que el aprendizaje en cada pasada del pipeline).

### 2026-07-06 -- El Historial llevaba semanas mostrando aciertos y premios equivocados

Marc reporto que la jornada 70 mostraba 9 aciertos/0e cuando en realidad fueron
12 aciertos/41,90e. La causa raiz: calcular_premios.py ya tenia la logica para
priorizar data/quinielas_jugadas.json (lo realmente jugado) sobre la
prediccion cruda del motor, pero main() nunca recalculaba un registro ya
existente si tenia los 14 partidos completos, sin importar de que fuente
habia salido. Si un registro se calculo ANTES de que la jugada real llegara a
quinielas_jugadas.json (el orden temporal real en casi todas las jornadas
59-70), se quedaba protegido para siempre con el dato equivocado. Este mismo
bug ya se habia arreglado una vez a mano el 29 de junio (commit e76264eba) y
habia regresado silenciosamente.
Fix: nuevo campo origen_prediccion en cada registro + funcion
puede_mejorarse_con_jugada_real() que fuerza el recalculo cuando el registro
existente no viene de la jugada real aunque esta ya exista. Autocurativo: si
vuelve a pasar, se corrige solo en la siguiente ejecucion.

### 2026-07-06 -- El calculo multicolumna necesita limites de plausibilidad, y el Pleno al 15 necesita uno distinto al resto

Al arreglar lo anterior, la jornada 70 paso a mostrar un premio de
244.034,14e (disparate). Causa: buscar_tabla_premios_loteriaanta() considera
"premio de la categoria 12" a cualquier fila de tabla que contuviera el
digito "12" en cualquier parte de una pagina con muchas tablas no
relacionadas. La combinatoria multicolumna (correcta) multiplicaba ese numero
erroneo por el numero de columnas ganadoras, amplificando el error.

Verificacion real: Marc mostro el escrutinio oficial de eduardolosilla.es
para la jornada 70 (15:17.119,56e 14:3.043,48e 13:63,17e 12:8,77e 11:2,03e
10:0,00e). Con la distribucion real del boleto (30 columnas a 10 aciertos, 12
a 11, 2 a 12): 30x0 + 12x2,03 + 2x8,77 = 41,90e exacto -- confirma que la
matematica combinatoria multicolumna siempre fue correcta; el problema era
solo la fuente de precios.

Fixes: buscar_premio_losilla() usaba una URL equivocada desde siempre (le
faltaba /ayudas/); nueva buscar_tabla_premios_losilla() como fuente principal
(loteriaanta.com de respaldo); fila_contiene_categoria() comparaba etiquetas
numericas ("11") como simple subcadena sin limites de palabra -"11" coincidia
dentro de "17.119,56"- (detectado porque los tests nuevos fallaron en CI
contra la tabla real); limite de plausibilidad por categoria (5.000e)
separado para la categoria 15 (3.000.000e, es un bote acumulable que puede
ser legitimamente mucho mayor). Limite del total subido de 20.000e a 500.000e
por la misma razon.
Por que importa: cualquier limite de plausibilidad sobre datos scrapeados
debe revisarse contra casos reales conocidos antes de darlo por bueno -un
limite "razonable" a ojo puede rechazar un premio legitimo tan facil como
aceptar uno absurdo.

### 2026-07-06 -- Jornada 71: sin jugada real confirmada, Marc la dio directamente en el chat

A diferencia de las jornadas 59-70 (ya en quinielas_jugadas.json), la 71
nunca se confirmo (ni boton ni Issue de GitHub). Marc dio los 14 signos de
memoria en el chat; se verificaron a mano contra data/jornadas/jornada_71.json
antes de guardarlos (10 aciertos, coincide con lo que recordaba) y se
anadieron directamente a data/quinielas_jugadas.json con origen
"confirmado_por_marc_en_chat" para distinguirlo del origen normal via Issue.

### 2026-07-06 -- Tercera colision en la extraccion de precios: la parte decimal de OTRA fila

Con los aciertos ya en 10, la jornada 71 seguia mostrando un premio de
8.132,10e en vez de 0,00e. Causa nueva y distinta a las dos anteriores:
extraer_premio_html() buscaba la categoria "10" con una regex de limites de
palabra sobre el TEXTO COMPLETO de cada fila. Esa regex evita que "10"
coincida dentro de un numero mayor como "110", pero no evita que coincida con
la parte decimal de un importe de OTRA fila: "8.132,10 e" (el premio real de
la categoria 14) tiene una coma antes del "10" y un espacio despues, asi que
el limite de palabra se cumple igual.

Verificacion real: escrutinio oficial de eduardolosilla.es para la jornada 71
(15:24.777,51e 14:8.132,10e 13:158,32e 12:17,09e 11:3,08e 10:0,00e
elige8:28,82e). Marc confirmo por chat: "en la 71 hemos hecho 10, 0 euros".

Fix: nueva primera_celda_es_categoria(celdas, aciertos), que compara SOLO la
primera celda <td>/<th> de la fila (la columna "Aciertos" de una tabla de
escrutinio bien formada) contra la categoria buscada, sin mirar el resto de
la fila. extraer_premio_html() la prueba primero, y solo si ninguna fila
cumple ese criterio estricto cae a los metodos antiguos (mas laxos, por
compatibilidad con tablas peor formadas). Esto evita de raiz cualquier
colision con importes de otras filas, sean subcadenas o partes decimales.

El registro ya guardado de la jornada 71 (con el 8.132,10e erroneo) no se
autocorrige solo: aciertos_confirmados=true y origen_prediccion ya apuntaba a
quinielas_jugadas.json, asi que el bucle principal lo trata como "protegido"
y "no mejorable" (el mecanismo de auto-sanado existente solo recalcula por
aciertos desactualizados o premios en estado "pendiente"/implausible-
multicolumna, no por un premio ya "resuelto" con una fuente que en su momento
parecia valida). Se corrigio el valor a mano en
data/premios/historial_premios.json (premio_eur: 0.0, fuente_premio:
"confirmado_usuario"), el mismo mecanismo ya usado en las jornadas 66 y 67
para bloquear un valor verificado y evitar que se vuelva a tocar.
Por que importa: un mecanismo de "proteccion contra recalculo" que solo mira
si el dato esta "completo" o "confirmado" puede proteger igual de bien un
valor correcto que uno incorrecto congelado antes de arreglar el bug que lo
genero -por eso siempre hay que revisar a mano los datos ya guardados tras
corregir un bug de extraccion, no solo confiar en que el proximo run los
arregle solo.

### 2026-07-06 -- Cuarta capa: el limite de plausibilidad de la categoria 14 tambien era demasiado bajo

Al desplegar el fix anterior, el propio test nuevo lo detecto en CI: con la
tabla real de la jornada 71, extraer_premio_html() encontraba bien el premio
real de la categoria 14 (8.132,10e, solo 13 acertantes a nivel nacional) pero
buscar_tabla_premios_losilla() lo descartaba por superar
PREMIO_CATEGORIA_MAXIMO_PLAUSIBLE (5.000e) -el mismo tipo de problema que ya
habiamos resuelto para la categoria 15, sin darnos cuenta de que tambien
afecta a la 14.

Motivo real: a diferencia del Pleno al 15 (que es un bote acumulable), la
categoria 14 no acumula, pero su premio tambien es el fondo semanal de esa
categoria repartido entre los acertantes -si una jornada tiene muy pocos
acertantes de 14 (13 en este caso), el premio por acertante puede dispararse
muy por encima de lo habitual sin que haya ningun error de extraccion.

Fix: nueva PREMIO_CATEGORIA_14_MAXIMO_PLAUSIBLE = 50.000e (10x el valor real
observado, con margen, y muy por debajo del limite de la categoria 15 y del
incidente original de 244.034e), gestionada junto con la de la categoria 15
en un diccionario LIMITES_POR_CATEGORIA en vez de un if/else especial.
Por que importa: un limite de plausibilidad "generico para todas menos la
15" asumia sin comprobarlo que solo el Pleno al 15 podia dispersarse por
pocos acertantes; los datos reales de la jornada 71 demuestran que esa
suposicion era incorrecta tambien para la categoria 14 -de nuevo, cualquier
limite heuristico necesita contrastarse con casos reales, no solo con la
intuicion de "esta categoria no deberia crecer tanto".

### 2026-07-06 -- Quinta capa: dos scripts distintos bloqueaban un premio "verificado a mano" con dos etiquetas distintas

Al desplegar los fixes anteriores y comprobar el resultado real en produccion,
la jornada 71 volvio a aparecer con fuente_premio="eduardolosilla" en vez de
"confirmado_usuario" (aunque, por suerte, con el importe correcto: 0,00e).
Causa: actualizar_aprendizaje_ia.py tambien escribe en
data/premios/historial_premios.json (con su propia estimacion, mucho mas
simple, basada en TABLA_PREMIOS_ESTIMADOS) y solo respetaba su propio
bloqueo, fuente_premio=="manual" -no reconocia "confirmado_usuario", el
bloqueo que usa calcular_premios.py para premios verificados a mano contra el
escrutinio oficial. Al ejecutarse en la misma tanda de automatizacion, este
script reemplazo el registro bloqueado por su propia estimacion (pendiente,
por tener dobles/triples), y calcular_premios.py, al ejecutarse despues,
volvio a recalcularlo el mismo dia -esta vez bien, porque el bug ya estaba
arreglado, pero sin la proteccion "no lo vuelvas a tocar nunca" que se le
habia puesto adrede.

Fix: nueva constante compartida FUENTES_PREMIO_PROTEGIDAS = ("manual",
"confirmado_usuario") en actualizar_aprendizaje_ia.py; debe_reemplazar_registro_premios()
y actualizar_historial_premios() ahora reconocen ambas etiquetas y conservan
la etiqueta original (no la fuerzan siempre a "manual").
Por que importa: dos scripts que escriben el mismo archivo de datos con dos
convenciones de "esto esta verificado, no lo toques" distintas es una trampa
silenciosa -funciona mientras la causa raiz este arreglada, pero en cuanto
vuelva a haber un bug de extraccion (o un valor que no se pueda re-derivar
automaticamente), el bloqueo manual desaparece sin ningun aviso. Cualquier
"flag de proteccion" nuevo debe revisarse en TODOS los sitios que escriben
ese mismo archivo, no solo en el script donde se origino la idea.

### 2026-07-07 -- Sexta capa: el mismo problema, pero con los ACIERTOS, no el premio

El fix anterior (FUENTES_PREMIO_PROTEGIDAS) solo protegia premio_eur/
fuente_premio/notas. En la siguiente tanda de automatizacion, la jornada 71
volvio a mostrar 13 aciertos en vez de 10 en la web (Marc lo vio directamente
en la pestaña Historial, con captura). Causa: actualizar_aprendizaje_ia.py
SIEMPRE reconstruye aciertos/fallos/boleto/detalle_partidos comparando la
prediccion CRUDA del motor contra el resultado real (13 aciertos, boleto
"1X1XX11X1111X1X21X1X21") -esto es intencional para el aprendizaje general
(ver la entrada del 2026-07-04 sobre "prediccion vs realidad, no lo jugado
vs realidad")-, pero lo escribe en el MISMO archivo y las MISMAS claves
(aciertos/boleto) que calcular_premios.py usa para los aciertos de la
quiniela REALMENTE jugada (10, boleto "1X21X22111X2X2112221"). El bloqueo de
premio protegia el importe pero dejaba pisar por completo los aciertos y el
boleto reales con los del motor.

Fix: nueva aciertos_verificados_con_jugada_real(actual), que devuelve True
si el registro ya tiene aciertos_confirmados=true o
fuente_aciertos=="quinielas_jugadas" (las mismas marcas que ya usa
calcular_premios.py). debe_reemplazar_registro_premios() ahora devuelve
False de entrada si esto es cierto -se salta el registro entero, ni premio
ni aciertos ni boleto-, tomando prioridad sobre el bloqueo de premio
"manual"/"confirmado_usuario" (que solo protege el importe, no los
aciertos). Se corrigio tambien el dato ya corrompido en
data/premios/historial_premios.json (jornada 71: aciertos 13->10, boleto y
detalle_partidos restaurados a los de la quiniela realmente jugada).
Por que importa: un "flag de proteccion" que protege un campo (premio) no
protege automaticamente los demas campos relacionados (aciertos, boleto) si
otro script los reconstruye por una via completamente distinta. Cada campo
compartido entre dos scripts con semanticas distintas necesita su propia
comprobacion explicita, revisada campo por campo -no basta con "ya arregle
el archivo la vez pasada".

### 2026-07-08 -- seleccionar_pleno15.py sustituia el Pleno al 15 por otro partido del boleto

Detectado al comparar a mano un pronostico de la jornada 72 con el que genero
el propio motor: el bloque `pleno15` de `data/predicciones/jornada_72.json`
tenia `num: 8, local: "Fredrikstad", visitante: "Lillestrøm"` -el partido 8
real- en vez del partido 15 (Sarpsborg 08 - Viking). Revisando jornadas
anteriores, el mismo patron aparecia en la 70 (num: 2) y la 71 (num: 9); solo
"acerto" por casualidad en la 65 y la 68.

Causa: `candidatos_prediccion()` metia los 14 partidos normales de la jornada
MAS el partido 15 real en una misma lista de "candidatos", los puntuaba a
todos por seguridad (probabilidad, margen, incertidumbre, calidad de datos,
riesgo de sorpresa) y `actualizar_pleno15()` sustituia num/local/visitante
enteros por los del candidato que ganara esa puntuacion -aunque fuera un
partido normal del boleto, no el 15. El Pleno al 15 en la Quiniela real
SIEMPRE es el partido 15 del boleto oficial -no se puede jugar el marcador
exacto de otro partido en esa casilla-, asi que esto no es una cuestion de
gustos: cualquier resultado distinto de num=15 es, por definicion,
imposible de apostar de verdad.

El frontend (`extractPleno15()` en index.html) ya tenia un fallback
defensivo que buscaba `num===15` dentro de `candidatos_evaluados`, asi que
los NOMBRES de equipo mostrados en la web probablemente seguian siendo
correctos (Sarpsborg-Viking) -pero el SIGNO recomendado
(`pleno15Sign()` lee `pleno15Recommendation().signo_recomendado`, que es la
recomendacion cruda sin filtrar por num) si quedaba mal: el de otro
partido, no el del 15.

Fix: `candidatos_prediccion()` ahora devuelve UNICAMENTE el partido 15 (desde
`data.pleno15` si existe con equipos, si no desde `partidos` buscando
`num==15`), nunca los partidos 1-14. Con un solo candidato posible,
`evaluar_partido()` solo puede decidir que signo/marcador recomendar PARA el
15, no sustituir su identidad. Test nuevo (`tests/test_seleccionar_pleno15.py`)
reproduce el bug real: un partido normal con probabilidades mucho mas
seguras que el 15 (igual que paso en la 70/71/72) y confirma que la
recomendacion final sigue siendo siempre el partido 15.

No hizo falta corregir a mano las jornadas 70/71 (ya cerradas, sin impacto
en dinero real -el premio ya se calcula desde quinielas_jugadas.json, no
desde este archivo de prediccion). La jornada 72 (abierta) se autosana sola
en la siguiente ejecucion del pipeline, porque `seleccionar_pleno15.py`
corre sin ningun flag de "protegido" que bloquee su recalculo.
Por que importa: una funcion de "elegir el candidato mas seguro" es
peligrosa en cuanto se generaliza a una lista con partidos de naturaleza
distinta (un partido normal 1X2 y el marcador exacto del Pleno al 15 no son
intercambiables, aunque ambos tengan forma de "partido con probabilidades").
Cualquier funcion de seleccion/ranking debe preguntarse primero si TODOS
los candidatos son realmente sustituibles entre si antes de puntuarlos
juntos.

### 2026-07-13 -- Nuevo archivo: comparativa manual de % de mercado vs resultado real (jornada 72)

Marc y yo armamos a mano una quiniela para la jornada 72 usando los
porcentajes reales de eduardolosilla.es (jugados/LAE/probables) en vez de
fiarnos del motor -precisamente porque ya sabiamos que el motor no tiene
datos reales para ligas nordicas/Mundial esta temporada baja. Acerto 12 de
14 (fallando solo en dos empates, partidos 9 y 13, que ningun indicador de
mercado anticipo). Se guardo como jugada real en `data/quinielas_jugadas.json`
(confirmado por Marc, incluido el Elige 8: 1,2,7,8,10,11,12,14, los 8
aciertos).

Ademas, a peticion explicita de Marc ("por si le sirve de aprendizaje"), se
creo `data/memoria_ia/comparativa_mercado_vs_resultado.json`: guarda, partido
a partido, los 3 porcentajes de mercado capturados ANTES del partido junto
al resultado real y si cada indicador acerto. Primera conclusion real:
jugados/probables acertaron 10/14 (71.4%), el modelo propio de LAE 9/14
(64.3%) -pero en el partido 6 el modelo de LAE acerto CONTRA el consenso
del publico, asi que no es simplemente "peor que la gente" en todos los
casos.

Este archivo NO esta conectado a ningun script todavia -es un punto de
partida manual, no un pipeline automatico-. Si con mas jornadas se confirma
que el consenso de mercado es una señal fiable, seria la base para decidir
si merece la pena integrar datos de mercado en vivo como señal real del
motor (la fuente `QUINIHUB_PRO_DATA_URL` de cuotas profesionales sigue sin
configurarse, ver pendientes).
Por que importa: antes de automatizar una señal nueva, conviene acumular
varios casos reales confirmados a mano (como este) para saber si de verdad
aporta antes de invertir en conectarla al pipeline.

### 2026-07-14 -- Se decidio conectar fuente_losilla.json de verdad, con peso real en las probabilidades

Se investigo primero (sin tocar codigo) que haria falta para dar mas peso
real al consenso de mercado en el motor. Hallazgos clave:
- El pipeline de `datos_profesionales.py` (API-Football) ya esta completo,
  probado y conectado de punta a punta -pero los secrets SI estan
  configurados (desde el 12 de julio) y aun asi todas las peticiones fallan
  con 403 Forbidden (token invalido/plan que no cubre temporada 2026 o
  estas ligas), y ademas `QUINIHUB_PRO_DATA_LEAGUES` sigue con los valores
  por defecto (La Liga/Segunda/Mundial) mientras se juegan ligas nordicas
  de verano -asi que aunque se arreglara el 403, tampoco encontraria los
  partidos correctos. Arreglar esto requiere que Marc revise su cuenta de
  API-Football; queda pendiente, fuera del alcance de este cambio.
- En cambio, `actualizar_fuente_losilla.py` YA scrapea automaticamente los
  mismos % de jugados/probables/cuotas de eduardolosilla.es que usamos a
  mano para la jornada 72, y el motor YA carga ese archivo
  (`FUENTE_LOSILLA`, motor_prediccion_quiniela.py) -pero solo lo usaba para
  un disparador estrecho (`calcular_ajuste_motivacion`: si el consenso
  supera 80% Y ya hay una alerta motivacional, fuerza doble/triple). Nunca
  se mezclaba con las probabilidades 1X2 en si, a diferencia de las cuotas
  de API-Football (que si se integran con `ajustar_por_datos_profesionales`,
  peso 0.14-0.30 segun el overround).

Fix: nueva `ajustar_por_mercado_losilla(probs, mercado)`, mismo patron que
`ajustar_por_datos_profesionales` pero para el consenso publico de Losilla:
mezcla las probabilidades del motor con las de mercado con peso fijo 0.18
(entre el nivel bajo y medio de las cuotas de bookmaker), y suma riesgo
extra si el favorito de mercado no coincide con el del motor. Se llama en
el bucle principal de `predecir()` justo despues de
`ajustar_por_datos_profesionales` y antes de `calcular_ajuste_motivacion`
(que sigue haciendo, ademas, su disparador de cobertura ya existente sobre
las probs ya mezcladas). El riesgo extra se suma a la incertidumbre total
del partido, y se guarda un bloque `mercado_losilla`/`ajuste_mercado_losilla`
en cada partido evaluado, igual que ya se hace con `datos_profesionales`.

Peso de 0.18 elegido por analogia con las cuotas de bookmaker (0.14-0.30
segun calidad), no por un calculo estadistico formal -es un punto de
partida razonable dado el 71.4% de acierto verificado en la jornada 72, se
puede recalibrar con mas jornadas de datos reales (ver el archivo de
comparativa de la entrada anterior).
Por que importa: es la via barata y ya verificada (sin depender de una
cuenta externa rota) para que el motor aproveche una señal que ya
demostro ser mejor que sus propias probabilidades en ligas sin datos
propios -en vez de dejarla usada solo para un disparador de cobertura.

### 2026-07-14 -- El fix anterior no se veia en produccion: segundo dict de salida con lista fija de campos

Al desplegar el fix de `ajustar_por_mercado_losilla` y comprobar el
resultado real en `data/predicciones/ultima_prediccion.json`, los campos
nuevos (`mercado_losilla`, `ajuste_mercado_losilla`) no aparecian en
absoluto, aunque el codigo estaba bien subido, los tests pasaban, y el
campo hermano `ajuste_datos_profesionales` (añadido junto al mio) si
aparecia con contenido real.

Causa: dentro de la misma `predecir()`, hay DOS diccionarios distintos por
partido. El primero (`evaluado`, donde añadi mis campos) solo se usa para
calculos internos (cobertura automatica, prioridad de dobles/triples,
etc.) -nunca se guarda en disco tal cual-. Un SEGUNDO bucle mas adelante
reconstruye el objeto que de verdad se serializa a `partidos[i]` copiando
campo a campo, uno a uno, con una lista fija de ~45 claves escritas a
mano. Cualquier campo nuevo que no se añada tambien en esa segunda lista
se descarta en silencio, sin error ni aviso.

Fix: añadidas las mismas dos claves (`partido["mercado_losilla"]`,
`partido["ajuste_mercado_losilla"]`) en esa segunda lista, justo donde ya
estaba `ajuste_datos_profesionales`.
Por que importa: en este archivo, un campo nuevo en el diccionario de
trabajo NO llega automaticamente a la prediccion final -hay que añadirlo
tambien en la lista de salida de la segunda pasada-. Cualquier campo
nuevo que se añada a `evaluado` en el futuro debe revisarse contra esta
segunda lista antes de darlo por conectado, y conviene verificar contra el
archivo real generado en produccion, no solo contra el codigo o los tests
unitarios (que no ejercitan `predecir()` de punta a punta).

### 2026-07-15 -- Por que `fuente_losilla.json` estaba vacio: eduardolosilla.es paso a ser una SPA de Angular

Con el blend de mercado ya conectado, `data/memoria_ia/fuente_losilla.json`
seguia con `"probabilidades": {}` en produccion real. Investigado a fondo
(sin tocar codigo primero): `actualizar_fuente_losilla.py` descarga HTML
estatico con `requests.get()`, pero la parrilla de partidos y porcentajes
de la pagina de boletos ahora se pinta enteramente en el cliente
(Angular) -el HTML que devuelve el servidor no contiene esas filas en
absoluto, asi que ningun scraper de HTML estatico puede verlas. Confirmado
descargando la pagina real con curl (mismos headers que el scraper) y
comparando contra el HTML real.

Buena noticia encontrada en la misma investigacion: tanto la pagina de
boletos como la de cuotas incrustan el estado inicial completo (equipos,
jornada, y los porcentajes jugados/LAE/probables de los 14 partidos + Pleno
al 15) en un `<script id="eduardo-losilla-state" type="application/json">`
server-renderizado, con un escapado propio no estandar (`&q;` -> `"`,
`&l;` -> `<`, `&g;` -> `>`, `&a;` -> `&`) en vez de entidades HTML
normales. Leer este bloque es mas fiable que raspar el DOM.

Tambien se confirmo la causa exacta del desfase "jornada 76 en vez de 73"
que ya habiamos visto: `extraer_jornada()` hace `max()` sobre TODAS las
apariciones de "JORNADA N" en el texto entero de la pagina, incluido el
selector de temporada (que lista las jornadas 1-76 de toda la temporada) -
siempre devuelve el numero total de jornadas de la temporada, no la que se
esta mostrando. El propio JSON embebido trae `datosGeneralesQuiniela.jornada`
sin ninguna ambiguedad.

Fix: nueva `extraer_estado_embebido()` (decodifica y parsea el JSON
incrustado) + `extraer_probabilidades_desde_estado()` (construye los
partidos 1X2 y el Pleno al 15 directamente desde ahi). `extraer_probabilidades()`
la intenta primero y solo cae al scraping de HTML antiguo si el bloque
no esta disponible -mismo espiritu defensivo que ya tenia el archivo.
`extraer_cuotas()` usa la misma jornada fiable (aunque las cuotas de
bookmaker en si siguen sin publicarse para esta jornada -confirmado en la
propia web, "Todavia no se dispone de las cuotas de los partidos"- eso no
es un bug, es que Winvictus.com aun no las tiene).

Bug secundario corregido de paso: los valores del JSON embebido son
numeros nativos (no texto con "%"), y la funcion `numero()` existente trata
un 0 legitimo como vacio (`str(0 or "") == ""`) y lo convierte en None -se
usa `float()` directo en vez de `numero()` para estos valores, para no
perder un porcentaje real de 0%.

Bug secundario mas: `fusionar_con_anterior()` reemplazaba TODO el bloque de
`cuotas` en cuanto el scrape nuevo devolvia cualquier cosa truthy (aunque
fueran solo nombres de equipo sin ninguna cuota real), pudiendo borrar
datos buenos de una semana anterior. Nueva `fusionar_cuotas()`, con el
mismo patron partido-a-partido que ya usaba `fusionar_probabilidades()`.

Tests nuevos en `tests/test_actualizar_fuente_losilla.py` (antes esta parte
del scraper no tenia ningun test) con HTML sintetico que reproduce el
escapado real y el bug del "JORNADA 76", verificando que la jornada activa
se lee del JSON y no del texto de la pagina.
Por que importa: cuando una fuente externa deja de funcionar, la primera
pregunta no es "como reparo el scraper de HTML" sino "esta pagina sigue
siendo HTML renderizado en servidor de verdad, o ha cambiado de
arquitectura". Aqui cambiar a SPA no rompio el dato -lo escondio del
scraper- pero dejo un atajo mucho mas fiable (el estado embebido) que ni
siquiera existia cuando se escribio el scraper original.

### 2026-07-15 -- Auditoria de todas las fuentes externas: resultados de liga sin respaldo real

Marc pidio que ninguna fuente de datos (memoria del motor, chat, web
predictiva) dependa de un solo sitio sin alternativa. Auditoria completa de
las ~22 fuentes externas que usa el pipeline: la mayoria de categorias ya
tienen un fallback real (calendario, clasificacion domestica, contexto/
lesiones via Google News->Bing News, premios con hasta 5 fuentes), pero se
encontraron 2 huecos reales:

1. **Resultados de liga**: en la practica dependen solo de quiniela15.com
   (`actualizar_boleto_vivo.py`, `FUENTES` con una unica entrada). La fuente
   "oficial" (`actualizar_fuente_lae.py`, loteriasyapuestas.es), aunque
   corre primero y esta etiquetada como prioritaria, no tiene ni un solo
   resultado marcado como `lae_oficial` en todo el historico -no hay
   evidencia de que funcione nunca-.
2. Descubrimiento colateral: `actualizar_resultados_libres.py` ya descarga
   resultados de ESPN + TheSportsDB + OpenFootball cada ciclo
   (`data/resultados_libres.json`), pero **nada en el resto del sistema lee
   ese archivo** -pura redundancia ya pagada en tiempo de ejecucion y nunca
   aprovechada-.

Fix: nuevo respaldo en `actualizar_boleto_vivo.py` -
`aplicar_resultados_libres_a_jornada()`- que, tras la pasada normal de
quiniela15.com, revisa las casillas que sigan sin `signo_oficial` valido y
las completa con `data/resultados_libres.json` si encuentra el partido por
nombre de equipo (`coincide_equipo()`: coincidencia por token, exige >=60%
de cobertura del nombre MAS CORTO para no penalizar sufijos genericos como
"CF"/"FC", y descarta un solo token compartido si es una palabra ambigua de
club -"real", "athletic", "united"...-, para no aplicar nunca un resultado
por una coincidencia de nombre falsa). Solo toca casillas ya resueltas por
quiniela15 si estas quedan en "Pendiente"; nunca sobrescribe un resultado ya
bueno.

Se reordeno `SCRIPTS_ACTIVOS` en `actualizar_todo.py`: `actualizar_resultados_libres.py`
corria muy despues de `actualizar_boleto_vivo.py` en el pipeline (con datos
del ciclo anterior, no del actual). Se movio justo antes.

Tests nuevos en `tests/test_actualizar_boleto_vivo.py`: coincidencia de
nombres (con sufijo, con token ambiguo, sin relacion), busqueda del
resultado correcto entre varios candidatos, y el caso completo -una casilla
pendiente se completa con el respaldo, una ya resuelta por quiniela15 NO se
sobrescribe aunque el respaldo traiga un marcador distinto, y un placeholder
sin equipos reales se ignora-.
Por que importa: una fuente de respaldo que ya se descarga pero no se usa
da una falsa sensacion de redundancia -parece que hay 2 fuentes, pero solo
una esta conectada de verdad-. Antes de dar por bueno "esto tiene
fallback", hay que comprobar que el dato de respaldo realmente llega a
alguna parte que lo consuma.

### 2026-07-15 -- El chat no encontraba los horarios de LaLiga porque no tenia query propia para ella

Marc pregunto en el chat "YA HAY LOS HORARIOS DE LA 1A JORNADA DE LIGA DE 1A
Y 2A DE ESPAÑA?" (LaLiga ya los habia publicado, confirmado con busqueda
real) y la IA contesto que no habia informacion, remitiendo a Marca/AS en
vez de mirarlo ella misma.

Causa: `necesitaBusquedaWeb()` SI detectaba la intencion de busqueda
(matchea "horario"), pero `construirQueryBusqueda()` (index.html) tiene
casos especiales para Mundial, Allsvenskan, Veikkausliiga, Eliteserien,
Superligaen, Premier, Bundesliga, Serie A, Ligue 1 y Champions -pero NINGUNO
para La Liga/Segunda de España, la competicion principal de esta app-. Sin
un caso propio, la consulta caia al fallback generico
(`futbol {texto} {fecha}`), una query demasiado debil y ruidosa para que
Tavily encontrara algo tan especifico como unos horarios recien publicados.

Fix: nuevo caso especial `esLigaEspanola` en `construirQueryBusqueda()`,
detectado por marca (laliga/hypermotion/"ea sports"/"1a division"/"2a
division") o por la combinacion generica liga+division+jornada+calendario+
horario junto con "españa" (porque el usuario no siempre nombra la marca
oficial). Genera `LaLiga EA Sports Hypermotion España calendario horarios
{texto} {fecha}`, mucho mas especifico. Verificado en el navegador real
(sin servidor, funcion pura): la consulta de Marc ahora genera esa query
especifica; consultas de equipos concretos (Real Madrid) y de otras ligas
(Veikkausliiga) siguen sin verse afectadas, sin falsos positivos.
Por que importa: la competicion mas importante de la app (La Liga/Segunda)
era la unica sin ruta de busqueda dedicada -un descuido facil de cometer
cuando se van añadiendo ligas extranjeras una a una y se da por hecho que
"la de casa" ya esta cubierta-.

### 2026-07-15 -- clasificaciones_mundial_2026.json: confirmado inerte y sin riesgo, no se toca

`motor_prediccion_quiniela.py` espera `data/memoria_ia/clasificaciones_mundial_2026.json`
pero ningun script lo genera nunca. Comprobado que esto NO es un bug activo:
`buscar_equipo_mundial()`/`es_ya_clasificada()`/`es_eliminada()` degradan
con total seguridad a `{}`/`None`/`False` sin excepciones, asi que el unico
efecto es que los ajustes de motivacion especificos del Mundial (casos A y
C de `calcular_ajuste_motivacion`) nunca se disparan.

Comprobado tambien que ya no hace falta: las jornadas 73 y 74 (las unicas
con partidos reales pendientes) son 100% ligas nordicas, sin ningun partido
de Mundial real -las menciones a "Mundial" que aparecen en esos JSON son
solo texto fijo del clasificador de competicion ("No encaja en
Primera/Segunda ni en Mundial..."), no partidos reales-. Ademas
`data/estado_temporada_2026_2027.json` ya tiene `modo_pretemporada_activo:
true`, confirmando que el sistema ya esta en modo de transicion a Liga
26/27.

Decision: no invertir en construir un scraper de clasificaciones del
Mundial para una funcionalidad que ya no tiene partidos reales que cubrir.
Tampoco se retira el codigo que la usa -esta inerte, no roto, y quitarlo
significaria tocar varias funciones de motor_prediccion_quiniela.py sin
ningun beneficio real ahora mismo-.
Por que importa: no toda referencia a un archivo que "nunca se genera" es
un bug que arreglar -a veces es una funcionalidad que ya cumplio su
proposito y esperar a que la temporada real la haga irrelevante es mas
seguro que tocar codigo sin necesidad.

### 2026-07-15 -- auditar_fuentes_profesionales.py: dos diagnosticos desactualizados corregidos

Ultimo punto de la auditoria de fuentes: `auditar_fuentes_profesionales.py`
(el propio panel de diagnostico del sistema) tenia dos inexactitudes:

1. `porcentajes_publicos_quiniela` seguia marcada a mano como
   "pendiente_fuente" sin comprobar nunca el estado real de
   `fuente_losilla.json` -que ya lleva desde el 2026-07-08 scrapeando datos
   reales y desde el 2026-07-14 integrada de verdad en el motor
   (`ajustar_por_mercado_losilla`)-. El diagnostico decia "pendiente" de
   algo que ya estaba en produccion.
2. Cuando API-Football falla con 403 (token configurado pero rechazado,
   ver entrada de "conectar Losilla" mas arriba), `cuotas_mercado`,
   `lesiones_sanciones` y `alineaciones_probables` se quedaban en su estado
   por defecto ("pendiente_api"/"pendiente_fuente") -identico a como se ven
   cuando nunca se configuro nada-. Un token roto y un token nunca puesto
   eran indistinguibles en este diagnostico.

Fix: `aplicar_estado_conector()` ahora recibe tambien `fuente_losilla` y
marca `porcentajes_publicos_quiniela` como "conectado_scraper" si hay al
menos 10 partidos reales. Nuevo estado `error_conexion` (token/URL
configurados pero la API no entrega ni un partido, con el error real de
API-Football en el mensaje) para las 3 fuentes que dependen de ella,
distinto de "pendiente_secret" (nunca configurado).

Bug de paso, encontrado al escribir el test: `criticas_pendientes` en
`main()` solo miraba si el estado empezaba por "pendiente" -con el nuevo
`error_conexion`, una fuente critica rota (token invalido) desaparecia de
esa lista sin estar resuelta, y `estado_global` podia decir
"base_critica_cubierta" con API-Football completamente caida. Corregido
para que `error_conexion` tambien cuente como pendiente.

Tests nuevos en `tests/test_auditar_fuentes_profesionales.py` (antes sin
ningun test): estado correcto con/sin datos reales de Losilla, distincion
error_conexion vs pendiente_secret vs conectado, y el caso que reproduce
el bug de `criticas_pendientes` encontrado de paso.
Por que importa: un panel de diagnostico que dice "todo pendiente" cuando
en realidad ya funciona (o dice "todo cubierto" cuando en realidad esta
roto) es peor que no tener panel -genera confianza falsa en cualquier
direccion. Cualquier cambio en como una fuente se marca como
resuelta/rota debe revisarse tambien contra los resumenes agregados que
dependen de ese estado, no solo contra el campo individual.

### 2026-07-15 -- El fix de La Liga en el chat se quedaba corto: Marc reprodujo el mismo bug con otra frase

Justo despues de desplegar el fix de `esLigaEspanola`, Marc probo en la web
real con una frase ligeramente distinta ("sabes los horarios de los
partidos de 1a y 2a de la 1a jornada?") y volvio a fallar igual -sin decir
"España" ni "LaLiga" en ningun momento, solo "1a"/"2a"/"jornada"/"horarios".

Causa: la primera version de `esLigaEspanola` exigia o bien el nombre de
marca, o bien la palabra "España" junto a un termino de calendario. No
cubria el caso, muy real, de preguntar por "1a y 2a" sin mencionar el pais
-logico en una app que ya es enteramente sobre fútbol español-.

Fix: nueva condicion `mencionaDivisionEspanola` (frase completa "primera/
segunda división" o "1a/2a división", inequivoca por si sola) + condicion
mas laxa "1a"/"2a"/"primera"/"segunda" sueltos junto a un termino de
calendario (liga/jornada/calendario/horario/clasificacion/tabla/posicion).
Verificado en el navegador real, con recarga forzada tras cada cambio (el
primer intento de verificacion dio un falso positivo de bug por cache del
navegador, no del codigo -lo confirme ejecutando el mismo regex aislado
antes de tocar nada, y solo tras un reload real coincidio con el resultado
de la funcion completa-), contra las dos frases reales de Marc y contra
todos los casos ya cubiertos antes (Real Madrid, Veikkausliiga, Champions,
bajas/lesionados, generico).

Efecto secundario detectado y corregido en el mismo pase: la version
anterior de esta condicion (con "españa" obligatorio) SI cubria
"clasificacion de segunda division" gracias a un patron de marca que
luego quite al reescribirla -sin querer, deje de cubrir ese caso al
endurecer el fix. Se recupero con la nueva `mencionaDivisionEspanola`,
que no depende de ningun otro termino.
Por que importa: verificar con UNA frase real no es suficiente cuando el
usuario puede reformular la misma pregunta de varias formas -y cualquier
endurecimiento de una condicion de deteccion debe re-probarse contra TODOS
los casos ya cubiertos antes, no solo contra el caso nuevo que se esta
arreglando.

### 2026-07-16 -- El Pleno al 15 no se autorellenaba al generar quiniela (España-Argentina, jornada 73)

Marc genero la quiniela con "Automática IA" y las 14 casillas normales se
rellenaron bien, pero el Pleno al 15 (partido 15, España vs Argentina -un
amistoso de selecciones, no una liga) se quedo sin ningun 0/1/2/M
seleccionado en ninguno de los dos lados.

Dos causas distintas, encontradas y arregladas juntas:

1. `pleno15Sign()` (la funcion que decidia que casilla marcar) buscaba un
   signo generico 1/X/2 -pensado para partidos normales de liga-, pero este
   partido es una "seleccion" fuera del pipeline habitual y nunca llega a
   tener probabilidades 1/X/2 calculadas por el motor (confirmado en
   `data/predicciones/pleno15_jornada_actual.json`: `"recomendacion": null`,
   `"candidatos_evaluados": []`). El pronostico real SI existia, pero en
   otro campo que nadie leia:
   `marcador_probable_losilla: {local:"1", visitante:"1"}` (estimacion via
   eduardolosilla.es) y `pronostico_marcador: "1-1"`.
2. Al arreglar el punto 1 y seguir sin funcionar en el navegador real, se
   encontro una segunda causa: `extractPleno15()` prioriza
   `state.jornadaActual` (el fixture crudo: equipos/fecha/resultado) sobre
   `state.prediccion`, y como el primero YA tiene un pleno15 valido (aunque
   incompleto, sin `marcador_probable_losilla`), el operador `||` nunca
   llegaba a mirar la prediccion, que es donde vive el pronostico real.

Fix: nueva `pleno15AutoCategoria(pleno, teamKey, probsTeam)` -POR LADO, no
un signo compartido-, con prioridad probabilidades_goles ya calculadas >
marcador_probable_losilla > pronostico_marcador "X-Y" > pleno15Sign() como
ultimo recurso. Y en `renderPleno15()`, un `plenoCompleto` que rellena
`marcador_probable_losilla`/`pronostico_marcador`/`probabilidades_goles`
desde `state.prediccion` si el pleno15 resuelto por `jornadaActual` no los
trae, sin perder los datos (equipos/fecha) que si trae ese primero.

Verificado en navegador real con los datos reales de la jornada 73: antes
del fix, ninguna celda se marcaba tras generar; despues, ambos lados
(España y Argentina) marcan correctamente "1", igual que el pronostico real
de la predicción.
Por que importa: cuando un mismo dato (aqui, el pleno15 de un partido)
vive en mas de un objeto de estado con contenido parcialmente distinto, un
`||` que se queda con el "primero que encuentre" puede devolver
silenciosamente una version incompleta -verificar solo con datos de
prueba en consola (que usan un solo objeto plano) no habria detectado
este segundo bug; hizo falta reproducir el flujo completo en el
navegador real con el estado real cargado.

### 2026-07-17 — El scraper de Losilla solo leia 1 de 4 fuentes, y el peso al mercado era fijo (0.18) sin importar la calidad del prior propio

Marc noto que el boleto publicado de la jornada 73 no se parecia a los
porcentajes de eduardolosilla.es y pregunto si no convendria promediar
directamente los indicadores de Losilla (tecnicos/jugados/LAE/probables).
Se investigo con una peticion real a la web (no solo lectura de codigo):

1. El bloque de estado embebido de eduardolosilla.es trae 4 tablas
   independientes por partido: `tecnicos`, `quinielista`, `lae`, `real`.
   Verificado en vivo para la jornada 73, partido 1 (Bodø/Glimt-
   Fredrikstad): tecnicos 78/16/6, quinielista 93/6/1, LAE 77/13/10, real
   83/10/7 -los 4 coinciden en algo contundente (77-93% para el "1").
2. `actualizar_fuente_losilla.py` (`extraer_probabilidades_desde_estado()`)
   solo leia `quinielista` y tiraba las otras 3 tablas, pese a venir en la
   misma respuesta.
3. `motor_prediccion_quiniela.py` (`ajustar_por_mercado_losilla()`)
   mezclaba ese unico indicador con el prior propio del motor a un peso
   FIJO de 0.18, sin importar si el prior propio era bueno o puro
   "fallback". Para la jornada 73 (ligas noruega/sueca, casi sin
   historico), el motor marcaba `calidad_datos: "baja"` en casi todos los
   partidos, y con esa base tan floja el 18% de mercado real no bastaba
   para corregir nada: el boleto publicado daba 43.0/29.6/27.4 para el
   partido 1, muy lejos de los 4 indicadores reales de Losilla (todos
   sobre 77% para el "1").

Fix en dos partes:
- `actualizar_fuente_losilla.py`: `extraer_probabilidades_desde_estado()`
  ahora lee las 4 tablas y promedia aritmeticamente las que traigan dato
  para cada partido concreto (no todas cubren siempre los 14 partidos),
  tanto para el 1X2 como para el Pleno al 15. Se guarda ademas
  `fuentes_detalle` por partido con los valores crudos de cada fuente, sin
  consumirse todavia por nadie mas, por transparencia.
- `motor_prediccion_quiniela.py`: `ajustar_por_mercado_losilla(probs,
  mercado, calidad_datos=None)` ahora busca el peso en
  `PESO_MERCADO_LOSILLA_POR_CALIDAD` (profesional=0.15, alta=0.20,
  media=0.35, media_baja=0.45, baja=0.65), con 0.18 como valor de
  seguridad si no se reconoce `calidad_datos`. El calculo de
  `trazabilidad_datos_partido()` (que produce `calidad_datos`) se adelanto
  en el bucle de `predecir()` para estar listo antes de la llamada a
  `ajustar_por_mercado_losilla`, en vez de despues como estaba.

Por que importa: un peso fijo de mercado tiene sentido si el prior propio
del motor es siempre igual de bueno, pero no lo es -para ligas con poco
historico (fallback puro) el mercado deberia pesar mucho mas que para
LaLiga con datos ricos. Y usar solo 1 de 4 fuentes de Losilla tira
señal real a la basura cuando las 4 suelen coincidir en lo esencial,
como en este caso.

### 2026-07-18 — Nueva fuente real de lesionados de LaLiga (FutbolFantasy), tras descartar Sofascore y aparcar BeSoccer

Marc compartio capturas de varias webs candidatas a nuevas fuentes de datos
(Sofascore, FotMob, BeSoccer, FutbolFantasy) y pidio analizarlas a fondo
antes de tocar nada ("no hagas nada hasta que te diga"). Se investigo con
peticiones HTTP reales, no solo lectura de las paginas:

- **Sofascore**: `robots.txt` devuelve 403 Forbidden incluso para esa
  peticion basica -proteccion anti-bot activa. Descartado para scraping de
  backend; solo tendria sentido como widget visual embebido (tarea de
  interfaz, no de datos), fuera de alcance.
- **BeSoccer**: `robots.txt` permite `Allow: /` y responde 200 con el mismo
  patron de cabeceras que ya usa `actualizar_fuente_losilla.py`
  (`User-Agent` + `Accept-Language`). Tecnicamente viable, pero su valor
  añadido es menor porque ya hay cobertura de calendario/resultados -se
  deja aparcado como fuente redundante futura, no se construyo.
- **FutbolFantasy** (`futbolfantasy.com/laliga/lesionados`): `robots.txt`
  permite todo, responde 200 con cabeceras minimas, y cubre exactamente el
  hueco que `lesiones_sanciones` tenia roto desde hace sesiones porque
  API-Football (de pago) no da datos en el plan Free para la temporada
  configurada. Estructura HTML verificada byte a byte via `curl`.

Se construyo solo esta ultima, siguiendo la disciplina de "un cambio a la
vez":
- `actualizar_fuente_lesiones_laliga.py` (nuevo): scraper que extrae, por
  equipo, cada jugador lesionado/duda/disponible (categoria leida del
  icono, no del texto -el texto varia mas que el icono-), con gravedad,
  probabilidad de disponibilidad, tipo de lesion y dias de baja. Mismo
  patron de resiliencia que Losilla: si la web falla, conserva el ultimo
  dato local valido y nunca detiene el pipeline.
- `motor_prediccion_quiniela.py`: `buscar_lesiones_equipo()` (reutiliza el
  matcher difuso `puntuacion_nombre_equipo` ya usado por Losilla) y
  `ajustar_por_lesiones_laliga()`, un ajuste pequeño y acotado (maximo
  ±6 puntos, tope de riesgo 8) que cuenta bajas en categoria "lesionado"
  por equipo y favorece ligeramente al que tiene menos -declarado a
  proposito como señal gruesa, porque no hay forma de pesar por
  titularidad/importancia real del jugador sin datos de alineaciones
  probables.
- `auditar_fuentes_profesionales.py`: `lesiones_sanciones` pasa a
  `conectado_scraper` en cuanto `fuente_lesiones_laliga.json` tiene al
  menos 10 equipos, independientemente de si API-Football sigue en
  `error_conexion` -resuelve de verdad una de las 3 `criticas_pendientes`
  sin depender de pagar el plan de API-Football.
- `index.html`: el chat recibe un bloque de lesionados solo de los equipos
  que aparecen en la prediccion actual o en la ultima jornada jugada (no
  las 20 plantillas completas), mismo criterio de contexto selectivo ya
  usado para "lo jugado".

Por que importa: es la unica de las 4 fuentes candidatas con alcance
tecnico viable, valor real confirmado (llena un hueco que llevaba tiempo
roto) y sin depender de un plan de pago -Sofascore esta bloqueado de raiz
y BeSoccer es redundante con lo que ya funciona.

Bug real detectado tras el primer run en produccion: `actualizar_fuente_
lesiones_laliga.py` se habia colocado en `SCRIPTS_ACTIVOS` justo antes de
`motor_prediccion_objetivo.py` (seccion "Motor predictivo"), pero
`auditar_fuentes_profesionales.py` corre bastante antes, en la seccion de
"datos profesionales". Resultado verificado en el primer
`fuentes_profesionales.json` generado: 19 equipos reales ya en
`fuente_lesiones_laliga.json`, pero `lesiones_sanciones` seguia en
`error_conexion` porque el diagnostico habia leido el archivo ANTES de
que el scraper lo escribiera en ese mismo ciclo. Fix: mover el scraper
junto a `actualizar_fuente_losilla.py` (seccion "Datos base"), antes de
`auditar_fuentes_profesionales.py` y por supuesto antes tambien de
`motor_prediccion_objetivo.py` -mismo principio que Losilla: si otro
script depende de tu salida en el mismo ciclo, tu posicion en
`SCRIPTS_ACTIVOS` importa, no solo estar "antes del motor".

### 2026-07-18 (mismo dia) — El scraper de lesiones solo cubria 1a division, y el chat mezclaba datos reales con alucinaciones

Marc probo el chat en produccion con dos preguntas reales ("que bajas
tiene el Athletic" y "que lesionados tiene el Espanyol ahora mismo") y
encontro dos fallos:

1. Para el Athletic, la respuesta mezclaba nombres reales de
   `fuente_lesiones_laliga.json` (Egiluz, Maroan) con nombres que NO
   aparecen ahi (Nico Williams, Paredes, Beñat Prados) -verificado
   comparando linea a linea con una captura real de
   futbolfantasy.com/laliga/lesionados que Marc envio.
2. Para el Espanyol, el chat dijo directamente "no tengo informacion
   actualizada", pese a que Espanyol SI esta en `fuente_lesiones_laliga.json`.

Causa raiz real (no la que se penso al principio): el bloque de
lesionados que se añadio en `construirContextoIA()` solo incluia equipos
que aparecieran en la prediccion ACTIVA del motor (ahora mismo Noruega/
Suecia, jornada 74) o en la ultima jornada REALMENTE jugada (el Mundial,
jornada 73). Con LaLiga sin empezar, ese filtro nunca incluye NINGUN
equipo de LaLiga -el bloque llevaba siendo un no-op completo desde que se
construyo, y la verificacion en vivo de esa misma tarde con el Athletic
"parecio" funcionar solo porque la busqueda web generica encontro por
suerte un par de nombres reales, mezclados con alucinaciones del modelo.
Leccion: una respuesta que "suena bien" no prueba que el mecanismo
disenado se este usando de verdad -habia que comprobar que el bloque de
contexto realmente se poblaba, no solo leer la respuesta final.

Fix (`index.html`): nuevo bloque `bloqueLesionesEquipo`, construido en
`enviarMensajeChat()` con el texto real de la pregunta (no dentro de
`construirContextoIA()`, que no lo conoce), buscando por nombre de equipo
mencionado en el mensaje -mismo patron que `bloqueCalendario`. Se añadio
tambien la regla critica #7 al system prompt: si aparece el bloque de
lesionados, citar EXCLUSIVAMENTE esos nombres, nunca mezclar con la
busqueda web o con "conocimiento previo" del modelo.

Aprovechando esta investigacion, Marc pidio ademas cobertura completa de
1a y 2a division y comparto 4 webs candidatas mas
(jornadaperfecta.com/lesionados y /sancionados, comuniazo.com,
futbolfantasy.com/laliga2/lesionados). Verificado en vivo con `curl` que
`futbolfantasy.com/laliga2/lesionados` es la pagina de Hypermotion (2a)
del mismo sitio, con el mismo HTML/CSS exacto -el scraper original solo
pedia la URL de 1a. Decision (con Marc, eligiendo entre opciones): ampliar
`actualizar_fuente_lesiones_laliga.py` para pedir tambien esa URL
(cobertura real 1a+2a con el mismo codigo de extraccion), y añadir
`actualizar_fuente_lesiones_jornadaperfecta.py` como fuente de RESPALDO
(estructura HTML distinta, verificada por separado) -se consulta solo
cuando la fuente principal no tiene datos de un equipo concreto
(encadenado con `or` en `buscar_lesiones_equipo`, tanto en el motor como
en el chat). jornadaperfecta.com/sancionados (dato nuevo: sanciones, no
lesiones) y comuniazo.com quedaron fuera de esta ronda, documentados como
opcion futura si hace falta.

Verificacion en vivo tras el deploy (probando varios equipos, no solo
Athletic/Espanyol, a peticion explicita de Marc) encontro 2 bugs reales
mas de contaminacion cruzada, cada uno arreglado y reverificado antes de
dar la tarea por cerrada:

1. **La busqueda web generica pisaba la fuente estructurada.** Pregunta
   real sobre el Girona: con el bloque de FutbolFantasy en el contexto Y
   la busqueda web (Tavily) tambien disparada en paralelo, el modelo
   ignoraba la instruccion "cita exclusivamente" y mezclaba nombres reales
   de prensa (Reinier, Borja Garcia...) que no estan en nuestra fuente.
   Fix: cuando se encuentra el equipo en la fuente estructurada, se vacia
   el bloque de busqueda web del todo para esa pregunta -mas fiable que
   confiar solo en una instruccion de "ignora la otra fuente" cuando
   ambas conviven en el mismo prompt.
2. **Un equipo del turno anterior "ganaba" al de la pregunta actual.**
   El buscador de equipo miraba `textoTotal` (pregunta + historial
   reciente de chat), quedandose con el nombre de equipo normalizado MAS
   LARGO encontrado. Preguntar por el Espanyol justo despues del Real
   Oviedo citaba al Real Oviedo ("real oviedo", con espacio, es mas largo
   que "espanyol"). Peor aun: preguntar por el "Barça" (apodo que no es
   substring de "Barcelona", el nombre oficial en FutbolFantasy) no
   encontraba equipo en el mensaje actual y caia al historial, rescatando
   por error el equipo de la pregunta ANTERIOR. Fix: se elimino el
   fallback a historial por completo -es mas seguro que la IA admita "no
   tengo datos de este equipo" a que cite el equipo equivocado con
   confianza- y se añadio un mapa pequeño de apodos comunes (Barça/Barsa
   -> Barcelona, Atleti -> Atletico) para que esos casos frecuentes si
   encuentren el equipo correcto en el mensaje actual.

Por que importa: una respuesta que "suena bien" no prueba que los datos
sean correctos -los 3 bugs de esta tarea (el original de contexto vacio,
la contaminacion con la busqueda web, y la contaminacion con el turno
anterior) solo salieron a la luz probando varios equipos reales en
secuencia en el navegador, no leyendo el codigo ni probando un unico caso
suelto.

## 2026-07-18 (mismo dia) — `prioridad_elige8` en el motor: bug real pero codigo muerto en produccion

Una auditoria externa (otra sesion de Claude Code, desde cero) encontro
que `prioridad_elige8()` en `motor_prediccion_quiniela.py` sumaba un
valor artificial gigante segun el tipo de cobertura del partido
(`10000/20000/30000` para fijo/doble/triple) que hacia ganar SIEMPRE al
tipo de cobertura sobre la probabilidad real (`probabilidad_cubierta`,
que solo contribuia hasta ~300 puntos). Verificado en el propio codigo:
cierto, y contradice directamente la regla que Marc valido a mano en la
jornada 73 (`feedback_metodo_prediccion_manual.md`, regla 1: "sumar el %
real de los signos marcados y ordenar por ese numero, no asumir que
'tiene doble' = 'es mas seguro'").

Pero antes de arreglarlo a ciegas, se rastreo la cadena completa del
pipeline y aparecio un hecho que cambia la urgencia real:
`motor_prediccion_objetivo.py` (el script que de verdad corre en el
pipeline automatico) llama a `predecir(jornada=objetivo)` **sin pasar
`elige8=True`** -y el valor por defecto de ese parametro en `predecir()`
es `False`. El bloque que usa `prioridad_elige8()` esta dentro de un
`if elige8:` que, con ese default, **nunca se ejecuta en produccion
real** (confirmado que ningun otro script en `SCRIPTS_ACTIVOS` llama a
`predecir(..., elige8=True)`). La seleccion de Elige8 que de verdad se
publica siempre vino de `aplicar_elige8_seguro.py`, que corre despues
en la seccion "Cierre final" y SOBRESCRIBE por completo la seleccion del
motor con su propio ranking -uno que ya estaba bien hecho desde el
principio (`probabilidad_acierto_elige8()`, sin ningun bono artificial
por tipo de cobertura).

Conclusion: el bug era real como defecto de codigo, pero no afectaba (ni
ha afectado nunca) al Elige8 realmente jugado -de ahi que a Marc "le
fuera perfecto" pese a que el otro informe lo describiera como el
hallazgo mas urgente por dinero real en juego. Se arreglo igual
(`prioridad_elige8()` ahora usa solo `probabilidad_cubierta -
penalizacion`, sin el bono artificial, con test de regresion nuevo para
el caso "doble flojo cubriendo una sorpresa contra un gran favorito vs
fijo solido en otro partido") por higiene y para proteger cualquier uso
futuro de ese parametro, pero sin la urgencia que se le atribuyo al
principio.

Leccion: antes de calificar un bug de codigo como "activo en produccion
con dinero real en juego", rastrear si el camino de codigo donde vive
realmente se ejecuta con los parametros que usa el pipeline automatico
-no basta con encontrar la funcion y ver que su logica esta mal.

### 2026-07-19 — Auditoria externa: 3 bugs reales en el chat, encontrados solo probando en vivo (pendientes de revision)

Otra sesion de Claude Code (auditoria completa del repo y de la web
pestaña por pestaña, a peticion de Marc, sin tocar codigo) encontro 3
bugs reales en produccion, verificados en el navegador real -no solo
leyendo codigo. Se documentan aqui para que la sesion principal los
revise con su propio criterio antes de decidir como y cuando
arreglarlos, mismo patron que ya funciono con el hallazgo de
`prioridad_elige8()` de la entrada anterior.

1. **El chat inventa partidos y equipos completos al preguntar por el
   Elige 8.** Pregunta real probada: "De los 14 partidos de esta
   jornada, ¿cuales elegirias para el Elige 8?" (jornada 74, solo
   equipos nordicos: Kristiansund-Start, Brann-Valerenga, etc.).
   Respuesta real del chat: recomendo los partidos "8, 9, 13 y 14"
   describiendolos como "Celta vs Barcelona", "Huesca vs Andorra",
   "Granada vs Real Zaragoza", "Cadiz vs Valladolid" -ninguno de estos
   partidos existe en la jornada real, son equipos españoles inventados
   con razonamiento plausible pero ficticio. Causa no confirmada (no se
   toco codigo), pero encaja con el mismo patron ya documentado el
   18/07: cuando el contexto estructurado no cubre lo preguntado, el
   modelo rellena el hueco con conocimiento general en vez de admitir
   que no lo tiene.

2. **Esa invencion queda guardada como "memoria aprendida" permanente,
   y el mecanismo que decide guardarla tiene un bug real.**
   `esIntencionAprender(textoTotal)` (index.html) decide si el usuario
   "quiere que la IA aprenda algo" buscando palabras como
   "aprende"/"recuerda"/"memoriza" -pero `textoTotal` incluye el
   historial reciente de la conversacion, incluidas las respuestas
   ANTERIORES del propio chat. Verificado en vivo: una respuesta previa
   del chat uso la palabra "aprender" de forma normal ("...para poder
   aprender de ellos..."), y eso basto para autoactivar el guardado de
   memoria en el turno siguiente, sin que Marc pidiera memorizar nada.
   Confirmado en `localStorage['quinihub_ia_memoria']`: el Elige8
   inventado del punto 1 quedo guardado como entrada real, tipo
   "web+usuario". Esa memoria se reinyecta literal en el prompt de
   TODAS las conversaciones futuras (`construirContextoIA()`, bloque
   "MEMORIAS QUE HAS APRENDIDO (persistentes entre sesiones)") -la
   fabricacion ya esta contaminando el contexto de cualquier chat
   futuro en ese navegador.

3. **Dos "jornada 73" distintas comparten el mismo numero, y el chat
   las confunde.** `data/predicciones/ultima_prediccion.json` real:
   `jornada: 74`, `estado: "bloqueada"`, `motivo_bloqueo: "...la
   jornada 73 solo tiene 10 de 14 resultados oficiales..."` -esto es
   correcto y esperado (el motor no debe predecir la jornada siguiente
   sin cerrar y aprender de la anterior con la clasificacion ya
   actualizada; confirmado con Marc que es diseño intencional, no bug).
   Pero `data/jornadas/jornada_73.json` (la "jornada 73" que bloquea el
   ciclo automatico) son partidos NORDICOS (Bodo/Glimt-Fredrikstad,
   Ham-Kam-Tromsø...) -completamente distintos de la "jornada 73" que
   Marc jugo de verdad y esta en `quinielas_jugadas.json`
   (España-Argentina, final del Mundial, 10 partidos, ya cerrada, 7
   aciertos/3 fallos). Son dos eventos reales distintos con el mismo
   numero de jornada. Probado en vivo: preguntar "¿cuantos aciertos y
   fallos llevamos en la jornada 73?" devolvio "10 aciertos y 4
   fallos" -numero que no corresponde a ninguna de las dos jornadas
   reales (la jugada por Marc es 7/3; la automatica es "10 conocidos,
   4 pendientes", no "10 aciertos, 4 fallos"). El chat mezcla ambas
   fuentes sin avisar de que hay ambiguedad.

4. **"Analisis IA" (el boton que cruza ESPN/TheSportsDB/Losilla/
   noticias y pide a la IA un analisis cualitativo partido a partido)
   se cuelga sin avisar.** Probado en vivo: mas de 90 segundos en
   "Analizando los 15 partidos..." sin resolver ni mostrar error. Cada
   pieza individual probada por separado desde la propia pagina (fetch
   directo) responde rapido: TheSportsDB 0.2s, el Worker de futbol
   1.9s, Tavily 0.4s, y hasta la llamada real a Groq (70B, prompt
   grande, 3500 tokens) responde en 3.6s -ninguna pieza individual es
   lenta, asi que el problema esta en como se combinan las ~11 llamadas
   en paralelo (`Promise.all` en `analizarJornada()`, index.html), no
   en ningun proveedor externo. No se investigo la causa exacta linea a
   linea (no se toco codigo).

Por que importa: los 3 primeros bugs solo salieron a la luz probando la
interfaz real con preguntas reales, no leyendo el codigo -mismo patron
ya confirmado el 18/07 con los bugs de contaminacion cruzada del chat.
El punto 2 es el mas urgente de los cuatro: la fabricacion del Elige8
ya esta persistida y reinyectandose en conversaciones futuras,
empeorando activamente con cada uso hasta que se corrija.
