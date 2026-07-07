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
