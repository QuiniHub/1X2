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
