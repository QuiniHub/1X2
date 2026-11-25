# Mezcla óptima de modelo estadístico + cuotas de cierre + porcentajes de la masa (1X2 / Quiniela)

Notas de investigación (2026-11-25). Alcance: cómo combinar las probabilidades 1X2 de un modelo propio con las cuotas de cierre (devigueadas) y con los porcentajes de apostantes del pool (masa LAE), para (a) probabilidades mejor calibradas y (b) mejores decisiones de apuesta en pool. Se omiten deliberadamente las bases de Shin, cierre-como-benchmark y sesgo favorito-longshot (ya implantadas en el proyecto).

Fuentes primarias leídas a texto completo (PDF extraído localmente): García-Pérez-Rodríguez 2016 (La Quiniela vs 9 bookies), Clair & Letscher 2007 (Operations Research), Egidi-Pauli-Torelli 2018 (Statistical Modelling), Hubáček & Šír 2020/2023 (arXiv/IJF), Brown & Reade 2018 (EJOR), Rosengren 2012 (Stryktipset, Univ. Estocolmo). El resto son abstracts/resúmenes verificados por búsqueda.

---

## Pregunta 1 — ¿Qué pesos modelo/mercado se reportan como óptimos y cómo se estiman sin sobreajuste?

### Takeaway
No existe un peso universal: la literatura converge en (i) combinar en escala log/logit, no en probabilidad lineal; (ii) estimar los pesos por regresión condicional (Benter) o por verosimilitud con validación hold-out/walk-forward; (iii) esperar que el mercado se lleve la mayor parte del peso y que el modelo aporte una ganancia pequeña pero medible (R² +0,009 en Benter; peso de mezcla ≈ 50/50 en Egidi, pero su mezcla sigue perdiendo contra Shin en Brier). La mezcla lineal de pronósticos calibrados está matemáticamente descalibrada (Ranjan & Gneiting) y necesita recalibración posterior.

### Cited Findings
- **Fórmula de Benter (segunda etapa):** `c_i = exp(α·ln f_i + β·ln π_i) / Σ_j exp(α·ln f_j + β·ln π_j)`, con f = probabilidad del modelo (out-of-sample) y π = probabilidad implícita del mercado; se usa logaritmo "porque la transformación ajusta mejor" (un salto 2%→4% pesa más que 50%→52%). Interpretación: α y β reflejan la corrección relativa de modelo y público; "cuanto mayor α, mejor el modelo". — [OddsPapi: Combine Your Model With Market Odds: Benter's Second-Stage Test](https://oddspapi.io/blog/?p=3174)
- **Magnitud de la ganancia (Benter, 2.313 carreras Hong Kong 1988-93):** R² público solo 0,1237; modelo fundamental solo 0,1016; combinado 0,1327 (ganancia +0,0090); 48 tipsters de periódico solo 0,1014 → combinado 0,1239 (ganancia +0,0002). Dos predictores con igual precisión aislada aportan información completamente distinta sobre el mercado; una ganancia de 0,0178 se consideró suficiente para beneficios significativos. — [OddsPapi](https://oddspapi.io/blog/?p=3174)
- **Diagnóstico anti-sobreajuste con α/β:** pesos positivos y estables entre folds → el modelo aporta información; pesos que cambian de signo entre folds con ganancia ≈0 → el modelo "reempaqueta" el precio; α grande con β≈0 → sospechar fuga de datos. Ajustar α,β en un subconjunto y puntuar en hold-out (5-fold); cuando el modelo duplica al mercado, α y β no están identificados por separado (su suma es estable, cada uno oscila); refitar mensualmente, un α decreciente indica que el mercado alcanza al modelo. — [OddsPapi](https://oddspapi.io/blog/?p=3174)
- **Potencia del test de Benter:** en 176 partidos MLB, el test detectó un edge simulado del 2% pero no del 1%; bootstrap de la ganancia sobre predicciones hold-out, no sobre filas antes de la CV. — [OddsPapi](https://oddspapi.io/blog/?p=3174)
- **Egidi, Pauli & Torelli (2018, Statistical Modelling 18(5-6):436-459):** modelo Poisson bayesiano jerárquico cuyas tasas de gol son combinación convexa `p_m·θ_datos + (1−p_m)·θ_bookies`, con `p_m ~ Beta(a,b)` no informativa; 9 temporadas de entrenamiento, 10ª de test (Bundesliga, EPL, Liga, Serie A 2016-17, 7 bookies). Posterior de p_m (EPL): "la cantidad de información que viene de los bookmakers es comparable a la de la información histórica" (mezcla ≈ mitad y mitad). — [arXiv 1802.08848](https://arxiv.org/abs/1802.08848); PDF del autor: [combining_egidi.pdf](https://leoegidi.github.io/paper/combining_egidi.pdf)
- **Pero la mezcla de Egidi NO bate a las cuotas devigueadas en precisión.** Tabla 4 (Brier 3-vías, menor = mejor; "p̄" = probabilidad media asignada al resultado correcto): Bundesliga modelo 0,6132 vs Shin 0,5978 vs básico 0,5983; Premier 0,5534 vs 0,5335 vs 0,5325; La Liga 0,5395 vs 0,5328 vs 0,5333; Serie A 0,5430 vs 0,5285 vs 0,5277. p̄: Liga modelo 0,4497 vs Shin 0,4584. — [Egidi et al. 2018](https://leoegidi.github.io/paper/combining_egidi.pdf)
- Egidi reporta "beneficio esperado" positivo apostando con su modelo frente a pérdidas esperadas apostando con las probabilidades de los bookies, pero el beneficio esperado se calcula con las propias probabilidades del modelo (`X_m = p_jm·o_jm − Σ p_im`), es decir, es circular y los autores advierten que "beneficios esperados positivos no aseguran retornos positivos". — [Egidi et al. 2018](https://leoegidi.github.io/paper/combining_egidi.pdf)
- **Mezcla lineal ≠ calibrada:** "cualquier promedio no trivial de dos o más pronósticos calibrados distintos resulta descalibrado y falto de nitidez (sharpness)"; propuesta: beta-transformed linear opinion pool (recalibrar la mezcla con una transformación Beta). — [Ranjan & Gneiting 2010, JRSS-B 72(1):71-91](https://econpapers.repec.org/RePEc:bla:jorssb:v:72:y:2010:i:1:p:71-91); extensión: la mezcla lineal solo funciona bien cuando los componentes están sub-dispersos. — [Gneiting & Ranjan 2013, EJS](https://projecteuclid.org/journals/electronic-journal-of-statistics/volume-7/issue-none/Combining-predictive-distributions/10.1214/13-EJS823.pdf)
- **Promedio de logits entre bookmakers** es la práctica estándar para el "consenso de mercado": quitar margen → log-odds → promediar → volver a probabilidad. — [Modeling and Prediction of the UEFA EURO 2024 (arXiv 2410.09068)](https://arxiv.org/pdf/2410.09068)
- **Las cuotas como input mejoran al Elo:** Wunderlich & Memmert 2018 (PLOS ONE), ~15.000 partidos 2007/08-2016/17, el Elo basado en cuotas supera al Elo clásico; interpretación: las cuotas pre-partido contienen más información que el propio resultado. — [Wunderlich & Memmert 2018](https://ideas.repec.org/a/plo/pone00/0198668.html)
- **Datapoint 2026:** un ensemble de pesos iguales de predictores (benchmark LLM-SoccerArena) obtuvo log-loss 0,857 y Brier skill −1,7% frente al mercado de cierre: promediar sin aprender pesos no bate al cierre. — [arXiv 2607.24573](https://arxiv.org/pdf/2607.24573)
- **Alternativa a mezclar: decorrelar.** Hubáček, Šourek & Železný (IJF 2019, 35(2):783-796) entrenan el modelo para reducir su correlación con las cuotas del bookie, no para maximizar precisión; con CNN + teoría de carteras obtienen beneficios acumulados positivos en NBA 2007-2014. — [econpapers](https://econpapers.repec.org/RePEc:eee:intfor:v:35:y:2019:i:2:p:783-796); [página de autores](https://ida.fel.cvut.cz/papers/hubacek2019exploiting.html)
- Hubáček & Šír ("Beating the market with a bad predictive model", IJF 2023 / arXiv 2010.12508): pérdida `MSE* = (1/|Ω|) Σ [(t_i − r_i)² + γ·(t_i − r_i)(m_i − r_i)]` (ec. 59), con t = estimación del modelo, m = mercado, r = valor real, γ>0 hiperparámetro; "hay un sweet spot al ajustar γ"; "con la estrategia sharpe generamos retornos positivos estadísticamente significativos a pesar de la precisión claramente inferior del modelo" (NBA, dos vías). — [arXiv 2010.12508](https://arxiv.org/abs/2010.12508)

### Inferences
- Para 1X2 el equivalente directo de Benter es una regresión logística multinomial con dos regresores por signo (`ln p_modelo`, `ln q_mercado_Shin`), coeficientes α,β compartidos entre signos, ajustada walk-forward por jornada/temporada. Si β≈1 y α≈0 el modelo no aporta nada; el valor típico esperado según Benter es una ganancia de R² de ~0,01 sobre el mercado.
- Los resultados de Egidi son una advertencia concreta: aun con 9 temporadas de datos y una mezcla bayesiana 50/50, la probabilidad combinada fue peor que Shin en las cuatro ligas (≈ +0,007 a +0,02 de Brier). Un peso 50/50 fijado a priori es casi con seguridad demasiado alto para el modelo; conviene dejar que los datos (regresión de Benter) lo fijen y aceptar β ≫ α.
- Si se opta por promedio lineal (más simple), hay que recalibrar después (Platt/beta/temperature) porque la mezcla lineal queda sistemáticamente sub-confiada. El promedio en logits (pool logarítmico/Benter) tiende a producir mezclas más nítidas y evita parte de ese defecto.
- La vía Hubáček (decorrelar) es la más interesante para pools: en una Quiniela lo que paga no es acertar más que el mercado sino acertar donde la masa (y el mercado) no están; un término de decorrelación respecto a la masa es formalmente el mismo truco.

### Gaps
- No he encontrado ningún estudio de fútbol que publique los valores α/β óptimos de una mezcla modelo+cierre 1X2 con validación walk-forward (los de Benter son de hípica). Habrá que estimarlos en casa.
- El artículo de Pinnacle/Buchdahl específico sobre "combinar modelo y mercado con shrinkage" no apareció en las búsquedas; la referencia a mezcla Beta-binomial (walrusquant.github.io) devolvió 404 y no se pudo verificar.
- Hubáček 2019 y Hubáček-Šír están validados en NBA (dos vías); no hay réplica publicada en fútbol 1X2 con cuotas de cierre salvo una tesis de máster (Aalborg 2025, XGBoost con pérdida decorrelada en Betfair) no revisada por pares. — [Aalborg thesis](https://projekter.aau.dk/projekter/files/784199250/MastersThesisGroup24.pdf)

---

## Pregunta 2 — ¿Es el porcentaje de la masa (pools) peor o mejor predictor que las cuotas? ¿Cuánto y dónde falla?

### Takeaway
En el único estudio académico sobre La Quiniela (2.280 partidos de Primera 2005/06-2010/11), la masa es claramente peor que los nueve bookmakers: Brier modificado ~10% peor en el 1, ~8% peor en la X y ~20% peor en el 2; pseudo-R² 0,058 vs 0,066-0,071. El fallo sistemático está en los visitantes (la masa infravalora el 2) y en la concentración excesiva en favoritos; en pools americanos "más de la mitad de los partidos tenían un favorito con >80% de los participantes". La masa sí puede contener algo de información adicional (Brown & Reade: +1,8 pp de probabilidad cuando la mayoría coincide, controlado por cuotas), pero el efecto es pequeño.

### Cited Findings
- **García, Pérez & Rodríguez (2016, MPRA 69687), La Quiniela vs 9 bookies, 2.280 partidos Primera 2005/06-2010/11; LQ = frecuencias de boletos por signo (no de apuestas).** Abstract: "los expertos parecen ser mejores pronosticando resultados de fútbol que la 'multitud'". — [MPRA 69687](https://mpra.ub.uni-muenchen.de/69687/1/MPRA_paper_69687.pdf)
- Brier modificado (ponderado por `1/(p(1−p))`, menor = mejor) de La Quiniela vs bookies por temporada 2005/06→2010/11:
  - **Local (1):** LQ 1,102 / 1,132 / 1,074 / 1,034 / 1,043 / 1,048 frente a bookies ≈ 0,955-0,969 / 1,008-1,031 / 0,986-1,024 / 0,949-0,973 / 0,933-0,941 / 0,946-0,953.
  - **Empate (X):** LQ 1,122 / 1,016 / 0,948 / 0,896 / 1,086 / 0,949 frente a bookies ≈ 0,993-1,015 / 0,947-0,975 / 0,866-0,887 / 0,856-0,876 / 0,968-0,985 / 0,858-0,878.
  - **Visitante (2):** LQ 1,328 / 1,264 / 1,276 / 1,169 / 0,904 / 1,249 frente a bookies ≈ 1,026-1,068 / 1,007-1,047 / 1,069-1,106 / 0,984-1,036 / 0,759-0,778 / 0,973-1,048. "Los pronósticos de los bookmakers funcionan mejor que las frecuencias observadas de La Quiniela, en particular para el evento visitante." — [MPRA 69687](https://mpra.ub.uni-muenchen.de/69687/1/MPRA_paper_69687.pdf)
- Logit ordenado (resultado ~ prob. 1 y prob. X): log-verosimilitud LQ −2104,66 (pseudo-R² 0,058) frente a B365 −2077,54 (0,070), VC −2076,85 (0,071), peor bookie LB −2087,07 (0,066); con dummies de temporada LQ 0,061 vs 0,069-0,073. — [MPRA 69687](https://mpra.ub.uni-muenchen.de/69687/1/MPRA_paper_69687.pdf)
- Correlación de las "cuotas" implícitas LQ con las de los bookies: 0,9075-0,9323 en el 1 (bookies entre sí 0,975-0,993); en la X, bookies entre sí 0,924-0,982 (fila LQ no legible en la extracción). — [MPRA 69687](https://mpra.ub.uni-muenchen.de/69687/1/MPRA_paper_69687.pdf)
- Advertencia de los autores: "la información de La Quiniela corresponde a boletos, no a apuestas, y esto podría estar empeorando el poder predictivo" (nota 20). — [MPRA 69687](https://mpra.ub.uni-muenchen.de/69687/1/MPRA_paper_69687.pdf)
- **Pools NFL (Clair & Letscher 2007, Op. Res. 55(6):1163-1177), ESPN Pigskin Pick'em 170.000 participantes, temporada 2004-05, 256 partidos:** "los competidores de ESPN tuvieron un historial global ligeramente mejor que el modelo informático Massey, pero lo más llamativo de la Tabla 1 es que más de la mitad de los partidos tenían un favorito que atraía a más del 80% de los competidores"; "los participantes sobre-apuestan favoritos, dejando mucho margen para mejoras estratégicas". En el tramo 50-55% de probabilidad real había 53 partidos, pero en el tramo 50-55% de porcentaje de masa había 0: la masa casi nunca reparte un partido parejo. — [Clair & Letscher 2007 (PDF)](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf); [DOI 10.1287/opre.1070.0448](https://pubsonline.informs.org/doi/fpi/10.1287/opre.1070.0448)
- NCAA 2003 (ESPN Tournament Challenge, ~1M entradas): en los cuatro cruces 8-9, históricamente a cara o cruz, la masa ungió favorito a uno de los dos por al menos 2 a 1. Metrick (1996) ya concluyó que los #1 seeds estaban sobre-apostados en pools. — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- **Tipsters amateurs (Brown & Reade 2018, EJOR; Oddsportal, 310.127 observaciones, 2012-2017):** regresión de acierto sobre probabilidad implícita (coef. 0,983) + proporción de tipsters que eligen el resultado (coef. 0,0193, p<0,01): la cuota de la masa aporta información más allá de las cuotas, pero el MSFE out-of-sample solo mejora de 0,2050588 a 0,205004. Un resultado es 1,8% más probable si la mayoría lo pronosticó, controlando por cuotas. Estrategia "apostar cuando hay mayoría (>1 tip)": +1,317% en 68.339 apuestas, frente a −2,278% apostando todo. Los tipsters eligen más favoritos que el mercado (prob. implícita media de sus picks 0,545 vs 0,477 del conjunto de apuestas). Filtrar por tipsters experimentados/hábiles NO mejora (+0,824% / +1,117%). — [Brown & Reade 2018, accepted manuscript](https://ueaeprints.uea.ac.uk/67529/4/Accepted_manuscript.pdf)
- **Crowd de pronósticos de goles (PLOS ONE 2025, Madsen):** la multitud predice xG bien en promedio pero sobreestima a los "big-6" y subestima al resto; rentabilidad limitada contra cuotas; recomendado como complemento, no sustituto. — [PLOS ONE 2025 vía RePEc](https://econpapers.repec.org/RePEc:plo:pone00:0312487)
- **Stryktipset (Rosengren 2012, Univ. Estocolmo):** regresión logística multinomial sobre partidos del Stryktipset; el modelo final usa la inversa de la cuota local de Svenska Spel y el número de periódicos que pronostican X; conclusión: "es mejor basar el modelo en medidas de expertos (variables 1-9) que en otras medidas (10-21)"; los autores no consiguieron una estrategia óptima de apuesta. — [report.pdf](https://www2.math.su.se/matstat/reports/seriec/2012/rep6/report.pdf); [abstract rep7](https://www2.math.su.se/matstat/reports/seriec/2012/rep7/abstract.pdf)
- Sesgo favorito-longshot en las cuotas españolas (mismo paper): take-out del grupo "alta probabilidad" en el 1 es negativo (−0,018 total) frente a +0,031 en "baja"; en la X 0,085 (baja) vs 0,059 (alta); en el 2 el patrón se invierte (0,017 baja vs 0,043 alta). — [MPRA 69687](https://mpra.ub.uni-muenchen.de/69687/1/MPRA_paper_69687.pdf)

### Inferences
- Magnitud: en La Quiniela la masa pierde frente al mercado del orden de 0,10-0,25 unidades de Brier modificado (8-20% relativo), con el mayor agujero en el signo 2. Para el motor esto significa que la masa NO debe entrar como estimador de probabilidad (no está calibrada) sino como variable de *reparto del premio*.
- La masa es más extrema que las cuotas (concentra >80% en favoritos; casi nunca reparte 50/50) y eso es exactamente lo que explota el pool: la brecha `q_mercado − s_masa` es grande y sistemáticamente negativa en el 2 del visitante y en X de partidos parejos.
- Brown & Reade muestran que la "información extra" de la masa existe pero vale ~1-2 pp de probabilidad: como señal de calibración es marginal; como señal de *dónde no está el dinero* es mucho más valiosa.
- La advertencia de García et al. (boletos ≠ apuestas) aplica igual a los % LAE actuales: incluyen reducidas/Elige 8, y se publican antes del cierre; parte del "error" de la masa es ruido de medición, no sesgo.

### Gaps
- No encontré ningún estudio académico sobre Totocalcio, Toto alemán, Norsk Tipping o Vakioveikkaus que compare porcentajes públicos con resultados; la única pieza con datos de pool europeo es la española (2005-2011) y la sueca (tesis de grado, sin medir el sesgo de la masa directamente).
- El paper español no desglosa el sesgo de la masa por tramo de probabilidad (p. ej. si sobre-apuesta la X en partidos parejos o solo el 1 de los grandes); solo da el agregado por signo.
- No hay datos públicos sobre si el sesgo de la masa LAE ha cambiado desde 2011 (post-Elige 8, post-apuestas online).

---

## Pregunta 3 — Dadas p (modelo), q (cuotas) y s (masa): ¿qué regla de decisión maximiza el retorno esperado en el pool?

### Takeaway
Clair & Letscher dan la fórmula exacta del retorno esperado de una columna en un pool con N rivales y demuestran que, cuando N→∞, la columna óptima elige en cada partido el signo con mayor ratio `probabilidad real / cuota de masa` (la "ventaja" o *edge*), y que con N pequeño se interpola hacia el favorito. Las picks óptimas fueron 3,4-28 veces mejores que el azar en pools de 170.000 participantes; "elegir todos los favoritos es una de las pocas apuestas perdedoras". La probabilidad "real" que entra en la fórmula debe ser la mejor estimación disponible (mezcla modelo+mercado de la Pregunta 1), nunca la masa.

### Cited Findings
- **Teorema 3.3 (pool de fútbol con N competidores, pago estándar):** `E(y) = Σ_{x∈O} A(x) · [ (L(x,x∧y) + E(x,x∧y))^{N+1} − L(x,x∧y)^{N+1} ] / [ (N+1) · E(x,x∧y) ]`, donde A(x) = probabilidad real del resultado conjunto x, `P(x) = Π_i [p_i si x elige favorito en i, (1−p_i) si no]` = probabilidad de que un rival elija x, x∧y = nº de partidos en que x e y coinciden, L = prob. de que un rival puntúe menos que tú dado x, E = prob. de empate. Coste O(4^g) términos, reducible a O(2^g) (Apéndice A.1). — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- **Proposición 3.4 (límite de pool grande):** para g partidos, la columna `e` que en cada partido elige el favorito si `a_i ≥ p_i` (prob. real ≥ cuota de la masa) y el no-favorito si `a_i < p_i` maximiza `lim_{N→∞} E(y) = A(y)/P(y)` (probabilidad de pleno dividida por la fracción de rivales que también lo tienen). — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- "Para un pool de un partido la estrategia óptima interpola entre apostar al favorito real y apostar al edge según N va de 1 a ∞" (Ejemplo 3.1, Figura 1: el umbral de probabilidad real a partir del cual se elige al favorito sube con N). — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Resultados NFL 2004-05 (N = 170.000): picks aleatorias tenían retorno semanal esperado medio de 23,4; las picks óptimas fueron 3,4-28× mejores que el azar en las 17 semanas; "una vez que los pools se hacen grandes, evitar a la multitud es crucial: incluso elegir al azar es mejor que elegir muchos favoritos". En la práctica un gráfico (p_masa, a_real) separa casi limpiamente una zona "favorito" y una zona "no-favorito", así que se puede decidir partido a partido. — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Sensibilidad al tamaño del pool: "elegir de forma más conservadora en pools pequeños y más sorpresas en pools grandes"; en torneos, "elegir conservador en rondas tempranas y sorpresas en rondas tardías". — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Pools multi-entrada (brackets): "aumentar la entropía de las predicciones a medida que crece el número de columnas n y a medida que los rivales aumentan su entropía". — [Entropy-Based Strategies for Multi-Bracket Pools, arXiv 2308.14339](https://arxiv.org/pdf/2308.14339)
- Regla de decorrelación (Hubáček-Šír) como regla de apuesta: el beneficio del tomador de mercado crece al reducir la correlación parcial entre su estimador y el del mercado; "la proporción de oportunidades detectadas es en todos los casos mayor cuando las predicciones del bookie y del apostante están menos correlacionadas". — [arXiv 2010.12508](https://arxiv.org/abs/2010.12508)
- Clair & Letscher usaron como "probabilidad real" un modelo externo (Massey) y como "probabilidad de la masa" los % publicados por el pool; recomiendan explícitamente usar ambos y validan que los picks simulados por el modelo se comportan como los humanos (§5.5). — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)

### Inferences
- Traducción directa a La Quiniela (15 partidos, pago por 10-14 aciertos + pleno al 15, bote): la fórmula exacta de Clair-Letscher es computable (2^15 = 32.768 columnas) si se modela a los rivales como independientes con probabilidades `s` (masa) por signo y se usa `a = p_mezcla` (modelo+Shin). La aproximación N→∞ es muy razonable para ~1-2 millones de boletos: **elegir el signo que maximiza `p_mezcla / s_masa`**, con dos correcciones: (i) la regla es por columna, no por signo, porque el premio depende del nº total de aciertos (probabilidad de ≥10 aciertos vs. nº de rivales con ≥10); (ii) para premios de 10-13 aciertos, que se reparten entre muchos, lo que importa es `A(≥k aciertos)/E[rivales con ≥k]`, lo que empuja hacia *más* favoritos que la regla de pleno.
- Fórmula operativa por signo para una columna sencilla: `EV_signo ∝ p_mezcla(signo) / s_masa(signo)`; un signo con ratio > 1 está "infra-apostado" por la masa. Con los números de García et al. (masa peor sobre todo en el 2) y Clair-Letscher (masa >80% en favoritos), los ratios > 1 se concentrarán en el 2 del visitante y en la X de partidos parejos, coherente con la regla 10 y el protocolo de bote del proyecto.
- Nunca usar `s` como `a`: la masa no está calibrada (Pregunta 2); si se usa la masa como probabilidad real, el ratio es 1 en todos los signos y la fórmula degenera en "copiar a la masa".
- El tamaño de pool N (boletos de la jornada) y el bote cambian el óptimo: con bote alto, el valor del pleno domina y se justifica desviarse más de la masa (más entropía, à la Entropy-Based Strategies); sin bote, los premios de 10-12 aciertos dominan y conviene acercarse al favorito. Esto es lo que ya recoge el protocolo de bote del proyecto; Clair-Letscher le pone fórmula.

### Gaps
- Clair & Letscher resuelven pools de "ganador se lo lleva todo" y torneos NCAA; no hay en la literatura una derivación publicada para el esquema de premios escalonado de la Quiniela (10/11/12/13/14/15 con % de recaudación), ni para la dependencia entre boletos reducidos. Hay que derivarlo en casa a partir del Teorema 3.3.
- No encontré el paper de Kaplan & Garstka 2001 ni Niemi et al. (estrategias contrarias NCAA) a texto completo; cito solo vía Clair & Letscher.

---

## Pregunta 4 — ¿Cuántos partidos hacen falta para validar una mejora de 0,002 en RPS? Métricas y calibración

### Takeaway
Con la desviación típica empírica de la diferencia emparejada de RPS entre dos predictores razonables (≈0,06-0,09 por partido, según mi simulación), detectar Δ=0,002 con potencia 80% y α=0,05 exige del orden de 7.000-17.000 partidos; Δ=0,005 exige 1.200-2.700. Para La Quiniela (≈700 partidos/temporada) eso son 10-25 temporadas para Δ=0,002. La literatura reciente (Wheatcroft) recomienda además usar el log-score (ignorance) en lugar del RPS para comparar modelos 1X2; para calibrar probabilidades multiclase, Dirichlet calibration generaliza temperature scaling y Platt.

### Cited Findings
- **Simulación propia (no es fuente externa; script `rps_power.py`, 20.000 partidos sintéticos con reparto 45/26/29 y ruido logit):** RPS medio ≈0,209-0,218; sd(RPS por partido) ≈0,13; sd(diferencia emparejada de RPS entre dos predictores) 0,061 (predictores muy parecidos) a 0,093 (bastante distintos). Tamaño muestral para test emparejado bilateral, α=0,05, potencia 80%: Δ=0,001 → 29.000-68.000 partidos; **Δ=0,002 → 7.200-17.000**; Δ=0,003 → 3.200-7.600; Δ=0,005 → 1.200-2.700. Fórmula: `n = ((1,96+0,84)·sd_diff/Δ)²`.
- Diferencias de RPS típicas entre modelos de fútbol publicados son de ese orden: 0,2054 a 0,2087 entre modelos, precisión 51,5-53,9% (sin test de significación). — [arXiv 2408.08331](https://www.arxiv.org/pdf/2408.08331)
- Wheatcroft (2021, JQAS 17(4):273-287, DOI 10.1515/jqas-2019-0089): la sensibilidad a la distancia del RPS "no es una propiedad útil"; en dos experimentos de simulación "el ignorance score (log-score) supera tanto al RPS como al Brier"; recomienda el log-score para evaluar pronósticos de fútbol. — [LSE eprints](https://eprints.lse.ac.uk/111494); [arXiv 1908.08980](https://ar5iv.labs.arxiv.org/html/1908.08980)
- El log-loss es la métrica alineada con la rentabilidad en apuestas porque deriva del payout. — [Forecast Sports Outcomes under EMH, arXiv 2604.17194](https://arxiv.org/pdf/2604.17194)
- Benter/OddsPapi: con 176 partidos MLB el test de segunda etapa detecta un edge del 2% pero no del 1%; usar bootstrap sobre predicciones hold-out. — [OddsPapi](https://oddspapi.io/blog/?p=3174)
- Buchdahl: demostrar un edge por resultados puede exigir "varios miles de apuestas", mientras que batir consistentemente la línea de cierre con ~5% de edge puede probarse con "tan pocas como 50 apuestas". — [Buchdahl, CLV demystified](https://pod-d614f9k2t-pod-team.vercel.app/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl)
- **Calibración multiclase:** Kull et al. (NeurIPS 2019) "Dirichlet calibration": método nativo multiclase que generaliza la beta-calibration binaria; en redes se reduce a log-transformar las probabilidades, una capa lineal y softmax; temperature scaling es un caso particular (matriz = identidad escalada, sesgo 0); mejora confidence-ECE, classwise-ECE, log-loss y Brier en muchos datasets. — [NeurIPS 2019](https://proceedings.neurips.cc/paper/2019/hash/8ca01ea920679a0fe3728441494041b9-Abstract.html); [arXiv 1910.12656](https://arxiv.org/pdf/1910.12656)
- Mezcla lineal de pronósticos calibrados → descalibrada; recalibrar con transformación Beta (beta-transformed linear pool). — [Ranjan & Gneiting 2010](https://econpapers.repec.org/RePEc:bla:jorssb:v:72:y:2010:i:1:p:71-91)
- Brier modificado ponderado por `1/(p(1−p))` (García et al., siguiendo Forrest et al. 2005) como variante para 1X2 que da más peso a los errores en pronósticos extremos. — [MPRA 69687](https://mpra.ub.uni-muenchen.de/69687/1/MPRA_paper_69687.pdf)
- Herramientas Python: `penaltyblog.implied.calculate_implied()` (multiplicativo, aditivo, power, Shin, differential margin weighting, odds ratio) y modelos Dixon-Coles / Rue-Salvesen con salida 1X2; la librería no incluye función de mezcla modelo+mercado. — [penaltyblog docs](https://penaltyblog.readthedocs.io/en/master/implied/implied.html)

### Inferences
- Una mejora de 0,002 RPS es indetectable a escala de una o dos temporadas de Quiniela; cualquier "mejora" de ese tamaño observada en 1-2 temporadas es ruido (p>0,3 típico). El backtest del proyecto (3 temporadas ≈ 2.000 partidos) solo puede detectar Δ ≥ ~0,004-0,006 RPS. Esto refuerza la regla de memoria "tras jornada loca no tocar nada".
- Métrica recomendada para el cuaderno: log-score por partido (y su diferencia emparejada frente a Shin) con test t emparejado / bootstrap por jornada (los partidos de una jornada no son independientes para el pool). RPS puede seguir reportándose por continuidad.
- Para calibrar la mezcla 1X2 con pocos datos: temperature scaling (1 parámetro) o Dirichlet/beta-calibration con regularización fuerte (≤ 6 parámetros); isotonic por signo necesita miles de partidos y rompe la suma a 1.

### Receta Python sugerida (inferencia, no fuente)
```python
import numpy as np
from scipy.optimize import minimize

def benter_blend(P_model, Q_market, alpha, beta):
    # P_model, Q_market: (n,3) probabilidades 1X2; mezcla en log-escala (Benter)
    L = alpha*np.log(P_model) + beta*np.log(Q_market)
    L -= L.max(1, keepdims=True); E = np.exp(L)
    return E / E.sum(1, keepdims=True)

def fit_alpha_beta(P_model, Q_market, y, train_idx):
    # y: índice 0/1/2 del resultado; minimiza log-loss en train
    def nll(ab):
        C = benter_blend(P_model[train_idx], Q_market[train_idx], *ab)
        return -np.log(C[np.arange(len(train_idx)), y[train_idx]]+1e-12).mean()
    return minimize(nll, x0=[0.2, 0.9], bounds=[(0,2),(0,2)]).x
# walk-forward: refit cada temporada; vigilar que alpha>0 estable entre folds (si no, modelo = mercado)

def rps(P, y):
    cum = np.cumsum(P,1); O = np.eye(3)[y]; oc = np.cumsum(O,1)
    return ((cum-oc)**2).sum(1)/2

def ev_ratio(P_blend, S_masa):
    # regla Clair-Letscher (N→inf): signo infra-apostado si ratio > 1
    return P_blend / S_masa
```

### Gaps
- No encontré ningún paper que publique explícitamente el tamaño muestral necesario para detectar una diferencia de RPS en fútbol; los números anteriores son de simulación propia y deben contrastarse con la sd real de la diferencia de RPS en el histórico del proyecto.
- No encontré una aplicación publicada de Dirichlet calibration a probabilidades 1X2 de fútbol; la evidencia es de clasificadores ML generales.

---

## Referencias clave (orden de utilidad para el proyecto)
1. Clair & Letscher 2007, Optimal Strategies for Sports Betting Pools, Operations Research 55(6) — fórmula exacta y regla edge = p_real/s_masa. https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf
2. García, Pérez & Rodríguez 2016, Forecasting football match results: are the many smarter than the few? (La Quiniela vs bookies) — MPRA 69687. https://mpra.ub.uni-muenchen.de/69687/1/MPRA_paper_69687.pdf
3. Benter second-stage test (OddsPapi) — α/β en log-escala, R² +0,009. https://oddspapi.io/blog/?p=3174
4. Egidi, Pauli & Torelli 2018, Statistical Modelling — mezcla convexa bayesiana; pierde contra Shin en Brier. https://arxiv.org/abs/1802.08848
5. Hubáček & Šír 2020/2023, Beating the market with a bad predictive model — pérdida con término de decorrelación. https://arxiv.org/abs/2010.12508
6. Brown & Reade 2018, EJOR — la masa (tipsters) aporta +1,8 pp controlando por cuotas; +1,317% ROI. https://ueaeprints.uea.ac.uk/67529/4/Accepted_manuscript.pdf
7. Ranjan & Gneiting 2010, JRSS-B — mezcla lineal descalibrada; beta-transformed pool. https://econpapers.repec.org/RePEc:bla:jorssb:v:72:y:2010:i:1:p:71-91
8. Wheatcroft 2021, JQAS — caso contra el RPS, usar log-score. https://eprints.lse.ac.uk/111494
9. Kull et al. 2019, NeurIPS — Dirichlet calibration. https://arxiv.org/pdf/1910.12656
10. Wunderlich & Memmert 2018, PLOS ONE — Elo basado en cuotas > Elo clásico (15.000 partidos). https://ideas.repec.org/a/plo/pone00/0198668.html
11. Hubáček, Šourek & Železný 2019, IJF — decorrelación + CNN + cartera, NBA. https://econpapers.repec.org/RePEc:eee:intfor:v:35:y:2019:i:2:p:783-796
12. Rosengren 2012 (Stryktipset, Univ. Estocolmo) — logit multinomial con cuotas + periódicos. https://www2.math.su.se/matstat/reports/seriec/2012/rep6/report.pdf
