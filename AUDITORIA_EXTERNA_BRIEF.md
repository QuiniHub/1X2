# Brief para auditoría externa — Quiniela IA Pro (repo 1X2)

Este documento existe para que quien audite este repositorio desde fuera (sin el
historial de conversación entre Marc y Claude Code) no tenga que redescubrir de
cero cosas que ya se investigaron, verificaron y arreglaron con datos reales.
Léelo entero antes de tocar código. Donde se dice "verificado con datos reales"
es literal: se comprobó ejecutando el código contra datos reales, no se asumió.

## Qué es este proyecto

Motor de predicción + web + chat para La Quiniela de fútbol española (LAE/SELAE).
Marc lleva 42 años jugando la Quiniela (desde los 12, con su padre) y es quien
decide qué se juega de verdad cada semana con dinero real. El repo no apuesta
solo — genera una recomendación, Marc la juega manualmente en
loteriasyapuestas.es, y solo entonces se confirma en `data/quinielas_jugadas.json`
(campo `origen: "confirmado_por_marc_en_chat"`, normalmente tras una captura de
pantalla real del boleto). **El sistema nunca debe tener capacidad de apostar
dinero real de forma automática.**

Web pública: https://quinihub.github.io/1X2/ (GitHub Pages, repo `QuiniHub/1X2`).
Pipeline automático: GitHub Actions, `.github/workflows/main.yml`, corre
`actualizar_todo.py` cada 30 min-4h.

## El hallazgo más importante: 3 sistemas de memoria que NO se hablan entre sí

Esto es lo primero que hay que entender, porque cualquier "aprendizaje" del
proyecto puede vivir en cualquiera de los tres, y no hay ninguna garantía de
que se propague a los otros dos:

1. **La memoria de sesión de Claude Code** (fuera de este repo, en
   `C:\Users\marcr\.claude\projects\...\memory\feedback_metodo_prediccion_manual.md`
   y `project_state.md`) — reglas cualitativas validadas jornada a jornada
   (ver más abajo). Solo la lee Claude Code cuando Marc invoca el skill
   `/analizar-jornada`. **La web y el motor automático NUNCA la ven.**
2. **El motor/pipeline automático** (`aprender_patrones_competitivos.py`,
   `motor_prediccion_quiniela.py`, `aplicar_elige8_seguro.py`,
   `calcular_premios.py`...) — patrones cuantitativos derivados de datos reales
   (`data/memoria_ia/historico_ligas_espana.json`, 3 temporadas completas de
   Primera+Segunda). Esto SÍ alimenta las predicciones reales y, en parte, el
   contexto del chat.
3. **La memoria propia del chat de la web** (`data/memoria_ia/diario_aprendizaje.json`,
   mecanismo `[MEMO]` en `index.html`) — solo crece cuando un VISITANTE de la
   web le pide al chat que aprenda algo. No tiene nada que ver con lo que
   aprende el motor ni con las sesiones de Claude Code.

**Pregunta concreta para la auditoría**: ¿hay más piezas de conocimiento real
(como pasaba con `riesgos_no_cubiertos_por_presupuesto`, ver más abajo) que el
backend ya calcula correctamente pero que nunca llegan a `index.html` ni al
contexto del chat (`construirContextoIA()`)? Ese es el tipo de gap que más
vale la pena encontrar aquí.

## Reglas de método ya validadas con datos reales (no las repitas desde cero)

Viven en detalle en la memoria de Claude Code, resumidas aquí porque el código
debería (y en parte ya) reflejarlas:

- **Principio fundacional**: "en el fútbol 2+2 no siempre es 4" — la parte
  del boleto que decide un premio grande es precisamente la que no sigue la
  lógica esperada. El objetivo no es "eliminar la incertidumbre", es aprender
  a reconocer dónde es más probable que aparezca.
- **Regla 1 (Elige8)**: seleccionar por probabilidad real de acierto
  NORMALIZADA por el coste que añade (`eficiencia_elige8` en
  `aplicar_elige8_seguro.py`) — un doble/triple no es "más seguro" para Elige8
  solo por cubrir más signos, porque también multiplica el coste x2/x3.
- **Regla 6**: cuando el motor marca un partido como toss-up real (probs
  <6 puntos entre sí, o `calidad_datos: "baja"`), no pelearlo con narrativa —
  confiar en el motor. Verificado: en J71-73, 8 de 11 fallos fueron por
  desviarse manualmente del motor en partidos así.
- **Regla 8**: la posición en tabla NO basta para simplificar un doble a
  fijo — hay que mirar también el margen real (`indice_sorpresa_quinielistica`,
  y el patrón `brecha_tabla_margen_estrecho_mercado` /
  `brecha_tabla_margen_amplio_mercado` en `aprender_patrones_competitivos.py`).
- **Regla 9**: en LaLiga/Segunda, ~48-49% de los partidos terminan siendo
  sorpresa respecto al favorito de mercado (verificado con 3 temporadas
  completas) — la pregunta útil es "¿cuál partido es más candidato esta
  semana?", no "¿habrá sorpresa?".
- **Regla 10**: cuando `indice_sorpresa_quinielistica` > 75-80, ningún doble
  da cobertura real suficiente — hace falta triple. Validado (y vuelto a
  validar, con un fallo real evitable en J75-P8 por soltar cobertura del
  motor por presupuesto).
- **Regla 11**: "el equipo con racha de derrotas está más necesitado y por
  eso rebota" es un MITO — verificado con 2.526 partidos reales (visitante
  con 0 puntos en últimos 3: gana solo 15,6% vs 27,2% base; local: 34,1% vs
  45,8% base). Ya conectado al motor real: `racha_perdedora_visitante_no_rebota`
  / `racha_perdedora_local_no_rebota` en `aprender_patrones_competitivos.py`,
  restando riesgo (no sumando) en `motor_prediccion_quiniela.py`. Tiene además
  un matiz real: el "rebote" es aún más raro si el rival sigue teniendo algo
  en juego (`racha_perdedora_*_rival_motivado` vs `_rival_sin_objetivo`,
  verificado con el caso real del Barcelona campeón de LaLiga 25/26 en la
  jornada 35, que rotó y perdió 2 de sus últimos 3 partidos sin nada en
  juego) — aunque los casos "rival sin objetivo" son raros (2-4% del total,
  concentrados en las últimas 1-2 semanas de cada temporada, verificado: los
  8 casos reales de 3 temporadas caen TODOS entre el 17 de mayo y el 1 de
  junio).

## Bugs reales encontrados y arreglados en la sesión más reciente (agosto 2026)

No son hipótesis — cada uno se verificó ejecutando el código contra datos
reales antes y después del fix. Vale la pena que la auditoría CONFIRME que
siguen arreglados (no que los "redescubra" desde cero), y que busque
variantes del mismo tipo de error en otras partes del código:

1. **`aplicar_elige8_seguro.py` — selección de Elige8 favorecía triples/dobles
   sin descontar su coste.** `probabilidad_acierto_elige8()` daba 100%
   automático a cualquier triple. Arreglado con `eficiencia_elige8()`
   (probabilidad / multiplicador), usado solo para el ranking — la
   probabilidad mostrada al usuario no cambia.
2. **Mismo archivo — nuevo modo `maxima_seguridad` + aviso con valor esperado
   en euros.** Antes solo existía "económico" (por coste); "rentable" era un
   stub idéntico, nunca implementado de verdad. Ahora se ofrecen los dos
   (mismo patrón que `boleto_millonario`: se presentan ambos, decide el
   usuario). El aviso usa el premio TÍPICO real según si la jornada es
   doméstica (Primera+Segunda, mediana real 578,70€, 13 jornadas de la
   2025/26) o internacional (Champions/selecciones/ligas extranjeras,
   mediana real 32,62€, 5 jornadas) — investigado con datos reales de
   escrutinios de toda la temporada 2025/26. Ojo: "Primera pura" (14/14
   partidos de Primera) NO EXISTE nunca — Primera solo tiene 20 equipos =
   10 partidos por jornada, siempre se rellena con Segunda.
3. **`aprender_patrones_competitivos.py` + `motor_prediccion_quiniela.py` —
   Regla 11 conectada de verdad** (ver arriba).
4. **`calcular_premios.py` — bug real de dinero, el más serio de todos.** Un
   boleto con dobles/triples (varias columnas reales) se quedaba cobrando el
   premio de UNA SOLA columna para siempre, en cuanto ese valor dejaba de
   ser 0,0 — porque `pendiente_premio()` solo consideraba "pendiente" un
   premio en 0. La tabla de premios por categoría de eduardolosilla.es no
   estaba publicada la primera vez que se calculó la jornada, así que caía a
   `obtener_premio_real()` (precio de una sola columna) y nunca se
   reintentaba el cálculo multicolumna real, aunque la tabla de premios
   completa estuviera disponible después. Caso real detectado por Marc
   mirando la propia web: jornada 75 mostraba 4,60€ cuando el premio real
   (verificado contra el escrutinio oficial) era 11,92€ (1 columna a 12
   aciertos + 6 columnas a 11). Arreglado con `premio_multicolumna_pendiente()`.
   **Pregunta para la auditoría: ¿hay otras jornadas pasadas con el mismo
   patrón (premio no-cero pero `fuente_premio` distinto de
   `multicolumna_loteriaanta` en un boleto con dobles/triples) que necesiten
   recalcularse igual? Ejecutar `python calcular_premios.py` con
   `beautifulsoup4` instalado y revisar el log.**
5. **`index.html` — `riesgos_no_cubiertos_por_presupuesto` calculado en el
   backend desde hace tiempo (motor_prediccion_quiniela.py, detecta
   partidos que el motor quería doblar/triplicar pero se quedaron en fijo
   por límite de presupuesto) pero NUNCA llegaba a la web ni al chat.**
   Conectado ahora en `construirContextoIA()`. Este es el patrón de bug más
   valioso a buscar: dato correcto en el backend, invisible para el
   usuario/chat por simple desconexión, no por error de cálculo.

## Código muerto conocido (no lo trates como bug activo)

`prioridad_elige8()` dentro de `motor_prediccion_quiniela.py` tiene un sesgo
real (bono artificial por tipo de cobertura, ya documentado y parcheado por
higiene) **pero está confirmado que nunca se ejecuta en producción** —
`motor_prediccion_objetivo.py` llama a `predecir()` sin `elige8=True`, y
ningún otro script activo lo hace tampoco. La selección de Elige8 que de
verdad se publica siempre viene de `aplicar_elige8_seguro.py`, que corre
después en el pipeline y sobreescribe cualquier cosa que haga `predecir()`.
Ver `DECISION_LOG.md`, entrada "2026-07-18 — prioridad_elige8 en el motor:
bug real pero código muerto en producción" para el detalle completo. **Antes
de reportar cualquier hallazgo sobre `prioridad_elige8`, comprobar primero si
de verdad se llama con `elige8=True` en algún sitio activo del pipeline
-si no, es ruido, no un hallazgo nuevo.**

## Decisiones deliberadas — no son bugs, no las "arregles"

- `boleto_millonario` sale siempre con `total_cambios: 0` mientras las
  jornadas activas sean de ligas nórdicas (Noruega/Suecia/Finlandia) —
  la señal (patrones de necesidad, historial de enfrentamientos, clase por
  posición) es 100% LaLiga/Segunda a propósito. Se activará sola cuando
  LaLiga 26/27 arranque (16/08/2026).
- API-Football sigue en plan Free a propósito — Marc no quiere pagar nada
  más hasta ver la web funcionando bien con LaLiga en marcha. No proponer
  pagos.
- Gemini como fallback de IA está desactivado a propósito (exige vincular
  tarjeta de facturación incluso en el nivel gratuito real) — el chat queda
  con Groq + OpenRouter, 2 de 3 niveles, sin Gemini. No es un fallo a
  arreglar.

## Pendiente conocido, sin arreglar todavía

**Bug del scraper de nombres de equipo**: en la jornada 74,
`actualizar_boleto_vivo.py` dejó el resultado de "Malmoe"/"Malmö" sin
`fuente_resultado` (nunca se resolvió vía el scraper en vivo, probable fallo
de `coincide_equipo()`/`CANONICOS` al no reconocer que son el mismo equipo).
Se corrigió el dato a mano esa vez, pero el bug de fondo en el scraper sigue
sin arreglar. Revisar `CANONICOS` en `actualizar_boleto_vivo.py`.

## Mapa rápido del código

- `motor_prediccion_quiniela.py` — motor de predicción principal
  (`indice_sorpresa_quinielistica`, `cobertura_automatica`,
  `construir_boleto_millonario`, etc.).
- `aprender_patrones_competitivos.py` — aprendizaje de patrones desde
  `data/memoria_ia/historico_ligas_espana.json` (3 temporadas reales,
  Primera+Segunda) → `data/memoria_ia/patrones_competitivos.json` +
  `historial_enfrentamientos.json`.
- `generar_contexto_competitivo.py` — clasificación real por equipo
  (título/Champions/Europa League/Conference/descenso, con estados
  `asegurado_matematicamente`/`salvado_matematicamente`/
  `descendido_matematicamente`) — verificado en vivo contra la temporada
  2025/26 real, funciona bien (detecta el cambio de estado del Barcelona
  exactamente en la jornada 35 real).
- `aplicar_elige8_seguro.py` — selección REAL de Elige8 (la que se publica).
- `calcular_premios.py` — cálculo de premios reales desde escrutinios
  oficiales (eduardolosilla.es, loteriaanta.com).
- `index.html` — web completa + chat (`construirContextoIA()`,
  `systemPrompt`, lógica de fetch/render de todas las pestañas).
- `cloudflare-worker/worker.js` — proxy de IA (Groq/Gemini/OpenRouter) +
  Tavily + datos de fútbol en vivo (ESPN/TheSportsDB). Las claves reales
  viven como secretos de Cloudflare, nunca en este archivo.
- `data/quinielas_jugadas.json` — verdad real de lo jugado con dinero real
  (solo `origen: "confirmado_por_marc_en_chat"` cuenta como confirmado).
- `data/jornadas/jornada_N.json` — resultados oficiales reales por jornada.
- `data/backtesting/pre_cierre/jornada_N.json` — snapshots INMUTABLES de la
  predicción del motor en el momento del cierre real (para retrospectivas
  honestas — no las mismas que la predicción "en vivo", que cambia cada
  30min-4h. **Ojo con esto**: comparar una decisión tomada en un momento
  contra el índice de OTRO momento posterior no es una retrospectiva
  honesta — ya se cometió este error una vez en esta sesión).
- `DECISION_LOG.md` — historial de decisiones técnicas y bugs ya resueltos.
  Consultar SIEMPRE antes de reportar algo como "nuevo".
- `tests/` — `python -m unittest discover -s tests` (requiere
  `beautifulsoup4` instalado localmente — sin él, 5 tests fallan por
  `ModuleNotFoundError`, no por lógica rota).

## Qué se espera de una auditoría útil aquí

No genérica ("mejora el código", "añade type hints"). Preguntas concretas
que sí aportan valor real:

1. ¿Hay más datos calculados correctamente en el backend que nunca llegan a
   la web/chat (como pasaba con `riesgos_no_cubiertos_por_presupuesto`)?
2. ¿Hay más sitios donde se asume "1 columna" cuando el boleto real tiene
   dobles/triples (como pasaba en `calcular_premios.py`)?
3. ¿El chat de la web (`index.html`) puede llegar a inventar números o
   contradecir los datos reales en algún escenario no cubierto por las
   reglas ya existentes en `systemPrompt`?
4. ¿Hay riesgo de XSS o inyección en cómo se renderiza la respuesta del
   chat o los resultados de búsqueda web en `index.html`?
5. ¿Las claves de API (Groq/Gemini/OpenRouter/Tavily) están genuinamente
   fuera del repo en todos los sitios, o hay algún log/commit antiguo que
   las exponga?
6. ¿Hay jornadas anteriores con el mismo bug de premio multicolumna sin
   corregir?
7. ¿El código muerto (`prioridad_elige8`) debería eliminarse del todo en vez
   de mantenerse "arreglado pero sin usar"?

Cualquier hallazgo debe venir con evidencia concreta (archivo + línea +
por qué importa), no con una afirmación abstracta de "esto podría mejorarse".
