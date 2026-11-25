# Reparto de presupuesto entre dobles y triples en quinielas de 14 partidos (La Quiniela / Totocalcio / Stryktipset / Tipping)

Notas de investigación (2026-11-25). Convención: cada partido i tiene vector de probabilidades (p_i1, p_iX, p_i2) ordenado de mayor a menor como p_i(1) ≥ p_i(2) ≥ p_i(3). Un "sistema producto" = elegir por partido 1, 2 o 3 signos (fijo/doble/triple); coste = ∏ c_i columnas. Un "sistema libre" = cualquier conjunto de N columnas (lo que permiten las reducidas y las apuestas múltiples en varios boletos).

Scripts de comprobación usados para los números de estas notas: `calc.py` y `calc2.py` (reproducidos abajo en cada sección).

---

## Pregunta 1 — Dadas 14 distribuciones 1X2 y un presupuesto de N columnas, ¿cuál es el conjunto óptimo de columnas para maximizar P(14) o P(≥13)? ¿Exacto vs greedy? ¿Es óptimo el greedy por entropía?

### Takeaway
Para P(14) el óptimo exacto es trivial: las N columnas más probables (las columnas son sucesos disjuntos, P(14) = Σ p(columna)); el "greedy por probabilidad" es exacto y un sistema de dobles/triples sólo es óptimo si coincide con ese top-N, cosa que rara vez ocurre. Para P(≥13) (o cualquier P(≥k)) el objetivo es una función de conjunto monótona submodular (cobertura ponderada de bolas de Hamming), de modo que no hay fórmula cerrada pero el greedy tiene garantía (1−1/e) y en la práctica supera a los sistemas producto con el mismo coste; "greedy por entropía" no es el criterio correcto, el criterio marginal correcto es log(masa cubierta)/log(coste).

### Cited Findings
- Clair & Letscher (Operations Research 2007) formulan el problema como "find picks b that maximize expected return E(b)" y dan fórmula exacta para pools de g partidos (Teorema 3.3): E(y) = Σ_x A(x)·[α_x(s) + β_x(s)^(N+1) − α_x(s)^(N+1)] / β_x(s) con s = x∧y (aciertos), α_x(s) = P(un rival saca exactamente s | resultado x), β_x(s) = P(un rival saca < s | x). La evaluación cuesta O(4^g) términos, reducible a O(2^g); "In our experiments, a hill-climbing search terminating at a point maximal among its 2-neighbors has never failed to find the best picks" — [Clair & Letscher 2007, PDF](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Clair & Letscher, Proposición 3.4: cuando N→∞ (muchos rivales) la columna óptima es la que maximiza A(y)/P(y) (probabilidad real / probabilidad de que la masa la juegue), es decir, "betting the edge" partido a partido: favorito si a_i ≥ p_i, no favorito si a_i < p_i — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Clair & Letscher, Ejemplo 3.2: el óptimo NO se descompone partido a partido en general (efectos de paridad: a veces conviene jugar el no-favorito real aunque toda la masa también lo juegue); pero la Figura 4 (256 partidos NFL 2004-05) muestra una separación casi limpia en zonas favorito/no-favorito en el plano (p_masa, a_real), por lo que "one could make a decent set of picks ... on a game-by-game basis" — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Brill, Wyner & Barnett (Entropy 2024, "Entropy-Based Strategies for Multi-Bracket Pools"): el problema general de elegir n tuplas para maximizar P(al menos una acierta todo) o E[max score] es "extremely difficult"; proponen muestrear n tuplas i.i.d. de una distribución Q de entropía ajustada; lecciones: "Increase entropy of submitted brackets as n increases", "Increase entropy as opponents' entropy increases", "Tune entropy to the field, not in isolation". Con n=1 lo óptimo es "pure chalk" (todo favoritos); al crecer n la entropía óptima sube hacia la real — [arXiv 2308.14339v3](https://arxiv.org/html/2308.14339v3)
- Brill et al.: fundamento AEP — las tuplas se dividen en "chalky" (individualmente probables, pocas), "typical" (≈2^{mH}, individualmente improbables pero concentran la masa) y "rare"; "Small n favors chalk; large n favors typical entropy" — [arXiv 2308.14339v3](https://arxiv.org/html/2308.14339v3)
- Trabajo previo citado por Brill et al.: Zaman (programación entera) genera greedy una secuencia de brackets "óptimos" bajo restricciones de diversidad; el paquete R mRchmadness usa simulación; Brill et al. afirman no conocer trabajo previo que optimice max-score o P(ganar) para múltiples brackets — [arXiv 2308.14339v3](https://arxiv.org/html/2308.14339v3)
- Regla LAE: el premio de 14 (1ª categoría) es el 16% de la recaudación repartido entre las apuestas con 14 aciertos; cada apuesta simple cuesta 0,75 € y en una múltiple normal hay máximos de dobles y triples (UC3M: máx. 5 dobles y 5 triples en el ejercicio clásico; la combinatoria real de LAE permite más) — [UC3M PR-F-001](https://ocw.uc3m.es/pluginfile.php/5303/mod_page/content/12/PR-F-001.pdf); [Loterías y Apuestas: quinielas reducidas](https://www.loteriasyapuestas.es/es/paginas-informativas/quinielas-reducidas-maximiza-tus-posibilidades)
- La tesis sueca "Jakten på den optimala Stryktipsstrategin" (Ytterberg Thornlund, Stockholms universitet 2012:7, dir. T. Höglund) concluye: "Vi misslyckades dock i vårt sökande efter den optimala Stryktipsstrategin. Vi lyckades inte hitta något Stryktipssystem där väntevärdet överstiger insatsen" (no encontraron ningún sistema de Stryktipset con valor esperado > apuesta), aunque sí lo encontraron en el mercado de cuotas con sus 3 modelos de regresión sobre el "streck" del público — [Abstract PDF](https://www2.math.su.se/matstat/reports/seriec/2012/rep7/abstract.pdf)
- Nämnaren (Berglund 2022, Göteborg): simulación Geogebra con probabilidades 36/32/32; un sistema de 3 triples + 4 dobles + 6 fijos = 3³·2⁴ = 432 filas; jugado 156 veces (3 años, 67.392 kr) dio sólo dos 12 y dos 11; el máximo permitido por Svenska Spel es 41.472 filas (3^m·2^n) — [Nämnaren 2022:4 PDF](https://ncm.gu.se/wp-content/uploads/2023/11/4348_22_4.pdf)

### Inferences
- **P(14) con N columnas libres — exacto y cerrado.** Las columnas son sucesos mutuamente excluyentes, luego P(14 | conjunto S) = Σ_{c∈S} ∏_i p_i(c_i). Maximizar sobre |S| = N es elegir las N columnas de mayor producto, obtenibles sin enumerar 3^14 con un "beam" por partidos ordenando por log-probabilidad (ver código). Esto es greedy exacto. Un sistema producto (dobles/triples) es un rectángulo en el espacio de columnas; su P(14) = ∏_i (masa cubierta en i). Ejemplo en 5 partidos con N = 12: top-12 columnas → 0,2914; mejor sistema producto con coste ≤ 12 (1,3,2,2,1) → 0,2669 (−8,4 %). (calc.py)
- **Sistema producto óptimo para P(14) = knapsack en logaritmos.** maximizar Σ_i log M_i(c_i) sujeto a Σ_i log c_i ≤ log N, con M_i(1)=p_i(1), M_i(2)=p_i(1)+p_i(2), M_i(3)=1. El ratio marginal que decide es: doble en i vale log((p_i(1)+p_i(2))/p_i(1)) por log 2 de coste; triple vale log(1/p_i(1)) por log 3; pasar de doble a triple vale log(1/(p_i(1)+p_i(2))) por log 1,5. No es "entropía" (la entropía de Shannon pesa los tres signos; aquí sólo cuentan los signos que se cubren vs. los que se dejan fuera). Greedy por ese ratio es una heurística de knapsack (no exacta en general), pero con 14 ítems y c_i ∈ {1,2,3} la enumeración exacta de 3^14 = 4,78 M coberturas es instantánea en Python, así que no hace falta heurística.
- **P(≥13) — submodular.** P(≥13 | S) = Σ_{w ∈ ∪_{c∈S} B(c,1)} p(w), donde B(c,1) es la bola de Hamming de radio 1 (c y sus 28 vecinas a distancia 1 en 14 partidos). Esto es cobertura ponderada: monótona y submodular, luego el greedy (añadir la columna que más masa nueva cubre) garantiza ≥ (1−1/e) ≈ 63 % del óptimo (teorema clásico de Nemhauser–Wolsey–Fisher 1978; no verificado en esta sesión vía fetch, cita de memoria: Math. Programming 14, 265–294). En el ejemplo de 14 partidos con N = 16 (calc2.py): greedy libre P(≥13) = 0,00576 y P(14) = 0,00034, frente al mejor sistema de 4 dobles (coste 16) P(≥13) = 0,00487 y P(14) = 0,00040. Es decir, el greedy libre da +18 % de P(≥13) a costa de −15 % de P(14): las dos funciones objetivo NO tienen el mismo óptimo; hay que elegir qué se maximiza (en La Quiniela el 13 lleva el 7,5 % frente al 16 % del 14, ver memoria de reparto, así que el objetivo correcto es el premio esperado ponderado, no uno de los dos).
- **Hill-climbing de Clair & Letscher** (vecinos a distancia 2) es la receta práctica que ellos verifican contra búsqueda exhaustiva en 14-16 partidos; es directamente portable a 1X2 (vecinos: cambiar 1 o 2 signos).
- **Por qué la gente "pone dobles en los partidos de más entropía" funciona aproximadamente**: cuando las probabilidades son cercanas a 1/3 cada una, la masa ganada al añadir el 2º signo (p(2)/p(1) ≈ 1) es máxima; cuando el favorito es claro, (p(1)+p(2))/p(1) es pequeño. La regla exacta es el ratio de masas, no la entropía, y ambas coinciden sólo en el caso simétrico.

Código Python (replicable):

```python
import itertools, math

def dist_hits(cover):                     # cover[i] = masa cubierta en partido i
    d=[1.0]
    for c in cover:
        nd=[0.0]*(len(d)+1)
        for j,v in enumerate(d): nd[j]+=v*(1-c); nd[j+1]+=v*c
        d=nd
    return d                               # d[j] = P(exactamente j aciertos)

def best_product_system(probs, budget, weights={14:1.0}):
    """probs: lista de 14 tuplas (p1,pX,p2). Enumera todos los sistemas dobles/triples
    de coste <= budget y maximiza sum_k weights[k]*P(k aciertos)."""
    M=len(probs); best=None
    srt=[sorted(p,reverse=True) for p in probs]
    for cov in itertools.product([1,2,3],repeat=M):
        cost=math.prod(cov)
        if cost>budget: continue
        d=dist_hits([sum(srt[i][:cov[i]]) for i in range(M)])
        val=sum(w*d[k] for k,w in weights.items())
        if best is None or val>best[0]: best=(val,cov,cost)
    return best

def top_columns(probs, N, beam=5000):
    """N columnas más probables (óptimo exacto para P(14) con N columnas libres)."""
    B=[((),0.0)]
    for i,p in enumerate(probs):
        B=sorted(((c+(s,),lp+math.log(p[s])) for c,lp in B for s in range(3)),
                 key=lambda t:-t[1])[:beam]
    return [c for c,_ in B[:N]]

def greedy_cover13(probs, N, cand=3000):
    """Greedy submodular para P(>=13): cada paso añade la columna que cubre más masa nueva
    en su bola de Hamming de radio 1."""
    M=len(probs)
    colp=lambda c: math.prod(probs[i][c[i]] for i in range(M))
    def ball(c):
        yield c
        for i in range(M):
            for s in range(3):
                if s!=c[i]: yield c[:i]+(s,)+c[i+1:]
    cands=top_columns(probs, cand, beam=cand); covered={}; chosen=[]
    for _ in range(N):
        g,c=max((sum(colp(w) for w in ball(c) if w not in covered),c) for c in cands)
        chosen.append(c); covered.update({w:colp(w) for w in ball(c)})
    return chosen, sum(covered.values())
```

### Gaps
- No encontré ningún paper que resuelva exactamente "N columnas libres → max P(≥13)" para 1X2; lo más cercano es Clair & Letscher (una sola columna, objetivo = retorno esperado contra la masa) y Brill et al. (n brackets, muestreo i.i.d. por entropía, no optimización combinatoria). La garantía (1−1/e) del greedy viene de la teoría general de submodularidad, no de un trabajo específico sobre quinielas.
- La tesis de Thornlund 2012 (Stryktipset) sólo pude leer en abstract (PDF escaneado); su tabla de contenidos incluye "Veckovis vinst (12 rätt)" y "slå oddsen", pero no pude extraer sus fórmulas ni sus números.
- No localicé el texto del artículo de Hämäläinen, Honkala, Litsyn & Östergård, "Football pools — a game for mathematicians", Amer. Math. Monthly 102 (1995) 579–588 (sólo citas).

---

## Pregunta 2 — ¿Cubrir el empate de un favorito (1X a 70/22) añade más P(13+) por euro que un triple en un 36/30/34? Fórmula y números.

### Takeaway
No. Con la regla del ratio de masas, el doble 1X en un 70/22/8 multiplica P(14) por 0,92/0,70 = 1,314 al doble de coste (0,657 por columna), mientras que el triple en un 36/30/34 multiplica por 1/0,36 = 2,78 al triple de coste (0,926 por columna) y el doble 1-2 en ese mismo partido (36+34 = 70 %) por 1,944 al doble de coste (0,972 por columna). Para P(≥13) el orden es el mismo: en un boleto con 12 fijos al 60 %, el triple en el toss-up da 0,00479 de P(≥13) por columna frente a 0,00392 del 1X en el favorito; ambos pierden contra dejar los dos fijos (0,00615 por columna), es decir, cualquier ampliación reduce la eficiencia por euro — se compra probabilidad total, no eficiencia.

### Cited Findings
- Nämnaren 2022: "En helgarderad match innebär att man där är 100 % säker på att få rätt. En halvgardering ökar sannolikheten från 33 % till 66 %" (triple = 100 %, doble = del 33 al 66 % en el caso uniforme) — [Nämnaren 2022:4](https://ncm.gu.se/wp-content/uploads/2023/11/4348_22_4.pdf)
- Clair & Letscher: en un pool de un solo partido contra un rival, apostar al favorito real devuelve p + 2a(1−p) y al no favorito (1−p) + 2(1−a)p; con N→∞ el retorno del favorito es a/p y el del no favorito (1−a)/(1−p) — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- García, Pérez & Rodríguez: sesgo favorito-longshot en las apuestas españolas a cuota fija y "bookmakers' predictions outperform those of football pools bettors" (las predicciones de las casas superan a las de los quinielistas) — [RPD García-Pérez-Rodríguez PDF](https://archives.rpd-online.com/article/download/v25-n3-garcia-perez-rodriguez/1958-7631-1-PB.pdf)

### Inferences
- **Fórmula general (sistema producto).** Sea R = ∏_{j≠i} M_j la masa cubierta en el resto del boleto. Al pasar el partido i de cobertura c a c' el P(14) se multiplica por M_i(c')/M_i(c) y el coste por c'/c. La "eficiencia por columna" de la ampliación es [M_i(c')/M_i(c)] / [c'/c]; siempre < 1 (porque M_i(c') ≤ 1 < M_i(c)·c'/c salvo que p_i(1) < 1/2 y ... en general nunca supera 1 porque M_i(2) ≤ 2·M_i(1) y M_i(3) ≤ 3·M_i(1) con igualdad sólo en el caso uniforme). Por tanto ninguna ampliación aumenta P(14)/euro; la pregunta correcta es "qué ampliación pierde menos eficiencia", y la respuesta es: la que tenga mayor ratio M_i(c')/M_i(c) relativo a c'/c.
  - 1X en 70/22/8: 0,92/0,70 = 1,314 → eficiencia 0,657.
  - 1-2 en 36/30/34: 0,70/0,36 = 1,944 → eficiencia 0,972.
  - Triple en 36/30/34: 1/0,36 = 2,778 → eficiencia 0,926.
  - Triple en 70/22/8: 1/0,70 = 1,429 → eficiencia 0,476 (la peor de todas).
- **P(≥13) con números (calc.py).** Boleto con 12 fijos a 0,60 cada uno + los dos partidos del ejemplo:
  | Opción | Coste (col.) | P(14) | P(≥13) | P(14)/col | P(≥13)/col |
  |---|---|---|---|---|---|
  | fijo 70 + fijo 36 | 1 | 0,00055 | 0,00615 | 0,00055 | 0,00615 |
  | 1X (70/22) + fijo 36 | 2 | 0,00072 | 0,00783 | 0,00036 | 0,00392 |
  | fijo 70 + triple 36/30/34 | 3 | 0,00152 | 0,01437 | 0,00051 | 0,00479 |
  El triple en el toss-up es un 22 % más eficiente que el 1X en el favorito en P(≥13)/columna y un 41 % más en P(14)/columna.
- **Cuándo SÍ compensa el 1X del favorito**: sólo si el precio de la columna no es el coste relevante (p. ej., bote: el extra se compra con dinero "barato") o si la masa juega el 1 del favorito muy por encima de su probabilidad real y el premio es pari-mutuel (ver Pregunta 3): entonces la X de ese partido tiene A/P alto. Por eso la regla práctica del proyecto (el 4º doble va al 2 del visitante despreciado 20-25 %, no a una X sobrejugada) está alineada con ambos criterios: p(2) ≈ 0,20-0,25 da ratio (p1+p2)/p1 mayor que una X al 22 % sobre un 1 al 70 % sólo si p1 es menor (p1 ≈ 0,50-0,55 → ratio ≈ 1,4-1,5 vs 1,31), y además es el signo infrajugado.
- Regla rápida para decidir el próximo doble: ordenar los 14 partidos por p_i(2)/p_i(1) (la probabilidad del segundo signo relativa al primero) y doblar de arriba abajo; para triples, ordenar por 1/(p_i(1)+p_i(2)) entre los ya doblados. Esto es exacto para P(14) en coste logarítmico y es el "greedy de Clair & Letscher por partido" en la variante sin rivales.

### Gaps
- No encontré ninguna comparación cuantitativa publicada (paper o blog con código) de "1X en favoritos vs triple en toss-ups"; los números de arriba son derivación propia con las fórmulas estándar. Los sitios españoles (LAE, betbrothers) sólo dan tablas de coste.

---

## Pregunta 3 — Consideraciones pari-mutuel: cubrir signos que la masa infrajuega. ¿Hay marcos cuantitativos más allá de "jugar contra el público"?

### Takeaway
Sí: (a) Clair & Letscher dan el marco exacto (retorno esperado de una columna = Σ_resultados A(x) × [reparto del bote entre los que empatan tu puntuación]), con el límite N→∞ reducido al cociente A(y)/P(y) y el umbral cerrado (3.1) para un partido; (b) Brill et al. dan la versión "n columnas contra k rivales con entropía r" y muestran que la entropía óptima propia sube con n y con la entropía de la masa; (c) Hauser, König & Krylova (Toto austriaco, 90 jornadas 1996-99) muestran el efecto contrario cuando hay bote/rollover probable: lo óptimo es SOBREjugar favoritos respecto a su probabilidad, y la masa real los sobrejuega aún más.

### Cited Findings
- Clair & Letscher, Ejemplo 3.1 y ecuación (3.1): umbral entre favorito y no favorito en un partido con N rivales: a = [1 + ((1−p)/p)·(1−(1−p)^N)/(1−p^N)]^{-1}, que interpola entre a = 1/2 (N = 1) y a = p (N → ∞) — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Clair & Letscher, resultados NFL 2004-05 (N = 170.000, ESPN Pigskin Pick'em): las columnas óptimas iban contra el modelo Massey en el 44 % de los partidos (6,6 no-favoritos reales por semana) y contra el favorito del público en el 63 % (9,5 por semana); "randomly selected picks had an average weekly expected return of 23.4 when N = 170,000. The optimal picks b varied from 3.4–28 times better than random"; "once football pools get large, crowd avoidance is crucial — even picking at random is better than picking lots of favorites" — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Clair & Letscher, sensibilidad: coeficiente de variación del retorno al perturbar a_i ±0,01: 2,1 % (N=50), 3,5 % (N=9.000), 4,2 % (N=170.000); al perturbar p_i ±0,01: 1,2 %, 3,5 %, 5,4 %. "small pools are about accurate predictions, whereas large pools are about crowd avoidance". Al re-optimizar con datos perturbados ±0,05, el rango de la columna resultante entre las 16.384 posibles fue mediana 6 (rango 1–4.412) — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Clair & Letscher, Tabla 1: más de la mitad de los partidos NFL tenían un favorito con >80 % del público; el público acertó 63,7 % vs 62,9 % del modelo Massey — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Clair & Letscher, aproximación normal (Teorema 4.1, Prop. 4.2): con puntuaciones ~ normales, todo se reduce a tres números (μ, σ², c): μ_X = Σ_i [a_i p_i + (1−a_i)(1−p_i)], σ²_X = Σ_i (a_i + p_i − 2a_i p_i)(1 − a_i − p_i + 2a_i p_i), cov(X,Y) = Σ_i 4a_i(1−a_i)(p_i − ½)(q_i − ½); la aproximación se desvió un 24 % de media del valor exacto pero preservó el ranking (11 de 17 semanas, la columna top por aproximación estaba en el top-10 exacto) — [Clair & Letscher 2007](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Hauser, König & Krylova (IHS Economics Series 87, 2000): "Assuming that the bookmakers' quotas reflect the true probability of each possible result ... we are able to derive a formula for the expected payoff of a betting strategy (Tipp). ... It turns out that given the relatively high probability of a rollover, it is optimal to overbet favourite outcomes (as compared to the probability of their occurrence). Comparing optimal with actual gamblers' behaviour we find that overbetting is even more pronounced than predicted by the model" — [IHS es-87 PDF](https://irihs.ihs.ac.at/id/eprint/1293/1/es-87.pdf); [IDEAS listing](https://ideas.repec.org/p/ihs/ihsesp/87.html)
- Brill, Wyner & Barnett: objetivo con k rivales (Eq. 2.4) P[max_{Bn} f(x,τ) ≥ max_{Ok} f(y,τ)] y beneficio esperado (Eq. 2.6) T·P[nuestro max > max rival] − b·n con bote T = C + b(n+k)(1−α) (C = arrastre, b = precio, α = take). En el ejemplo Pick-Six (Belmont 21/5/2023, k = 25.000, α = 0,05, C = 500.000) "Submitting many tickets at a well-chosen entropy is hugely profitable, especially when the carryover is large" — [arXiv 2308.14339v3](https://arxiv.org/html/2308.14339v3)
- DeStefano, Doyle & Snell ("Evil Twin"): en un pool de m jugadores que eligen a cara o cruz, jugar dos columnas opuestas da retorno R = [2(m+2)/(m+1)]·(1 − 1/2^{m+1}); beneficio máximo ≈ 0,344 $ con 5 jugadores y decrece hacia 0 al crecer m — [Dartmouth, Evil Twin](https://math.dartmouth.edu/~doyle/docs/twin/twin)
- Forrest & Pérez (J. Gambling Studies 2015): La Quiniela "is a pari-mutuel game where prizes represent a share of sales"; las ventas se modelan con el "effective price" = precio nominal − valor esperado de premios, y se comportan "just like the lottery" — [Salford repository](https://salford-repository.worktribe.com/output/1396457/just-like-the-lottery-player-behaviour-and-anomalies-in-the-market-for-football-pools)
- Sitios suecos de "spelvärde": comparan % de "streck" del público con la probabilidad implícita en cuotas (ej. 62 % streckad vs 43 % por cuotas) para elegir signos — [hurbra.se](https://hurbra.se/stryktipset/)

### Inferences
- **Fórmula de valor esperado por columna en 1X2 pari-mutuel** (adaptación directa de Clair & Letscher + estructura LAE): para una columna y y un reparto por categorías k ∈ {14,13,12,11,10} con fracciones f_k del fondo F,
  E(y) = Σ_x A(x) · Σ_k 1[y∧x = k] · f_k F / (1 + N·P_k(x)) (aproximación "número esperado de ganadores"), donde P_k(x) = Σ_{z: z∧x=k} P(z) es la probabilidad de que una columna de la masa tenga exactamente k aciertos dado el resultado x. La versión exacta con empates es la (3.8)/(3.9) de Clair & Letscher; para N grande (La Quiniela: millones de columnas) la aproximación 1/(1+N·P_k(x)) ≈ 1/(N·P_k(x)) es adecuada y da el principio A/P.
- **Dónde poner dobles contra la masa**: el signo i-ésimo tiene "edge" e_i = a_i(s)/p_i(s). Para P(14) sin rivales el doble óptimo va al mayor a_i(2)/a_i(1); contra la masa, va al mayor [a_i(2)/p_i(2)]/[a_i(1)/p_i(1)], es decir, al segundo signo más infrajugado en relación al primero. Las dos reglas coinciden cuando la masa es calibrada (p = a) y divergen justo en los partidos donde la masa está sesgada (favoritos mediáticos, X infrajugadas).
- **Bote (rollover)**: el resultado austriaco (sobrejugar favoritos cuando el bote es probable) y el de Brill (más entropía cuando el carryover es grande) no son contradictorios: Hauser et al. optimizan el valor de una sola columna cuando el premio mayor rara vez se reparte (lo que importa es acertar, no evitar compartir), mientras que Brill optimiza n columnas contra k rivales en un bote ya acumulado (lo que importa es que tus n columnas cubran resultados que los rivales no cubren). Para La Quiniela esto sugiere: en semana normal, sin bote, la columna base va a favoritos; con bote grande y muchas columnas, dispersar hacia resultados típicos infrajugados.
- Clair & Letscher muestran que "la mayoría de las 16.384 columnas tienen E > 1" en pools grandes porque casi todos los rivales juegan una de pocas columnas populares (top-25 columnas = 62 % de 24.000 boletos). Trasladado a La Quiniela: el valor viene de estar fuera de las columnas de masa, no de acertar más.

### Gaps
- El cuerpo del paper de Hauser et al. está en alemán y el texto extraído no permitió aislar la fórmula de pago esperado ni las proporciones óptimas vs reales; sólo el abstract es citable con seguridad.
- No encontré trabajos académicos noruegos sobre Tipping (Norsk Tipping) ni italianos sobre Totocalcio con optimización de sistemas; la literatura italiana localizada es histórica/normativa (regolamento de sistemas, 3^14 = 4.782.969 columnas para 14 triples) — [normattiva](https://www.normattiva.it/eli/id/2004/09/04//004G0260/CONSOLIDATED), [qualcherisposta](https://qualcherisposta.it/chi-e-il-totocalcio).
- Tsyganov / "Bettingbolag" (mencionados en el encargo): sin resultados en búsqueda; no puedo confirmar que existan como papers sobre Stryktipset.

---

## Pregunta 4 — ¿Qué cuestan las garantías de los sistemas reducidos en probabilidad frente a las combinaciones completas? Matemática de coberturas (football pool problem).

### Takeaway
Un sistema reducido "al 13" es un código cubridor ternario de radio 1: garantiza que si aciertas el signo de los partidos fijos, alguna columna tiene ≥13; su coste es que P(14 | aciertas los signos) cae de 1 a (nº columnas reducidas)/(nº columnas completas) cuando las probabilidades son uniformes, y a la suma de probabilidades de las columnas elegidas en general. Con 4 triples la reducción oficial (9 de 81, código de Hamming ternario perfecto) deja P(14) = 11,1 % uniforme (11,2 % con 36/30/34-tipo), P(13) = 100 %; las 9 columnas más probables sin garantía darían P(4/4) = 18,5 % pero P(≥3/4) sólo 62,6 %. El mínimo de columnas K_3(n,1) es conocido exactamente sólo para n = 1..5, 9 y 13 (K_3(13,1) = 59.049; K_3(6,1) ∈ [71,73] tras 140 años-CPU de cómputo).

### Cited Findings
- Definición: un código cubridor K_q(n,R) es el tamaño mínimo de un conjunto de palabras tal que toda palabra de {0..q−1}^n está a distancia ≤ R de alguna; el football pool problem es el caso q = 3, R = 1 — [Wikipedia, Covering code](https://en.wikipedia.org/wiki/Covering_code)
- Tabla K_3(n,1) (según Wikipedia, citando tablas de Kéri, estado 2011): n=1:1, 2:3, 3:5, 4:9, 5:27, 6:71–73, 7:156–186, 8:402–486, 9:1060–1269, 10:2854–3645, 11:7832–9477, 12:21531–27702, 13:59049. Cuando n = (3^k−1)/2 bastan 3^{n−k} columnas (n=4 → 9; n=13 → 59.049) — [Wikipedia, Covering code](https://en.wikipedia.org/wiki/Covering_code); tablas primarias en [Kéri, Tables for Bounds on Covering Codes](https://old.sztaki.hu/~keri/codes/index.htm)
- Linderoth, Margot & Thain: el problema para v = 6 es un programa entero binario z_v = min{1ᵀx | Ax ≥ 1, x ∈ {0,1}^n} con n = 3^6 = 729 variables y 729 restricciones; "For d = 1 and v = 6, the optimal code size is only known to be between the values of 65 and 73"; CPLEX tras 500.000 nodos sólo sube la cota inferior a 58; con poda por isomorfismo y grid de 19.012 máquinas establecieron z_6 ≥ 71 usando >140 años-CPU (M=70: 110,1 años-CPU, 2,85×10⁹ nodos; M=71: 30,3 años-CPU) — [Linderoth-Margot-Thain TR](https://jlinderoth.github.io/papers/Linderoth-Margot-Thain-07-TR-1.pdf); publicación: [INFORMS J. Computing 2009](https://pubsonline.informs.org/doi/fpi/10.1287/ijoc.1090.0334)
- Brink (J. Integer Sequences 2011): T(n,q) = mínimo de esferas de radio n sin interior que cubren {0..q−1}^n (el "inverse football pool problem"); los valores T(n,3) para n = 1..6 proceden de la revista finlandesa de quinielas Veikkaaja en los años 50; Östergård & Riihonen mejoraron cotas con tabu search para n = 9, 10, 11, 13 — [JIS 14 (2011) 11.8.8](https://cs.uwaterloo.ca/journals/JIS/VOL14/Brink/brink3.html)
- Reducciones oficiales LAE (precio 0,75 €/apuesta): 1ª: 4 triples, 81 → 9 apuestas, 6,75 €, garantía al 13; 2ª: 7 dobles, 128 → 16, 12 €, al 13; 3ª: 3 triples + 3 dobles, 216 → 24, 18 €, al 13; 4ª: 2 triples + 6 dobles, 576 → 64, 48 €, al 13; 5ª: 8 triples, 6.561 → 81, 60,75 €, al 12; 6ª: 11 dobles, 2.048 → 132, 99 €, al 12. Se pueden combinar con dobles/triples al directo en otros partidos (ej.: 4 triples reducidos + 1 doble = 13,50 €) — [betbrothers.es](https://betbrothers.es/noticias/quiniela-reducida-precio-dobles-triples/); LAE: "en la primera reducción tenemos un 11,11 % de probabilidad de tener una apuesta de 14 aciertos siempre que todos los resultados coincidan con el pronóstico" — [Loterías y Apuestas (resumen de búsqueda; la página devolvió 403 al fetch directo)](https://www.loteriasyapuestas.es/es/paginas-informativas/quinielas-reducidas-maximiza-tus-posibilidades)
- Nämnaren: Svenska Spel admite hasta 41.472 filas (3^m·2^n); Svenska Spel ofrece "Reducera Fritt" (reducción a medida; un ejemplo de foro: sistema de 230 filas tras 53 % de reducción) — [Nämnaren 2022:4](https://ncm.gu.se/wp-content/uploads/2023/11/4348_22_4.pdf); [flashback (foro, no oficial)](https://www.flashback.org/p47330592)

### Inferences
- **Coste en probabilidad de la garantía.** Para un sistema de t triples y d dobles reducido a S columnas de las 3^t·2^d completas: P(premio máximo | pronóstico de signos correcto) = Σ_{c∈S} ∏ p_i(c_i) / ∏_i M_i, que con probabilidades uniformes dentro de cada partido es exactamente S/(3^t 2^d): 1ª reducción 9/81 = 11,1 %; 2ª 16/128 = 12,5 %; 3ª 24/216 = 11,1 %; 4ª 64/576 = 11,1 %; 5ª 81/6561 = 1,23 % (al 12); 6ª 132/2048 = 6,4 % (al 12). La garantía al 13 (o al 12) vale 100 % condicionada al pronóstico, por construcción.
- **Eficiencia por euro de la reducción ≈ 1 para P(14)** (calc2.py: 4 triples con probabilidades 36/30/34-tipo: P(4/4) reducido 0,1117 por 6,75 € vs 1,0 por 60,75 € → ratio por euro 1,01). La reducción no "compra" P(14) más barata; lo que hace es cambiar P(14) por P(13) garantizado y por un precio de entrada asequible. Comparada con las 9 columnas más probables (sin garantía): éstas dan P(4/4) = 0,185 (+65 %) pero P(≥3/4) = 0,626 vs 1,0. Elegir entre ambas depende del peso relativo que se dé al 13 frente al 14 (reparto LAE: 16 % para 14 vs 7,5 % para 13, más el efecto de que los 13 se reparten entre muchos más acertantes).
- **La 1ª reducción es el código de Hamming ternario perfecto [4,2]:** 9 palabras, radio 1, cada palabra de {0,1,2}^4 está en exactamente una bola; por eso 9 = 3^4/(1+2·4) es cota de esfera alcanzada. Lo mismo para 13 partidos (3^13/(1+2·13) = 59.049): un sistema de 13 triples reducido al 12 necesita exactamente 59.049 columnas (44.287 € a 0,75 €), inviable; por eso las reducidas prácticas combinan pocos triples/dobles.
- **Código de Hamming [4,2]_3 (9 columnas, garantía 3 de 4) para construir la 1ª reducción:**
  ```python
  H4 = [(0,0,0,0),(0,1,1,2),(0,2,2,1),(1,0,1,1),(1,1,2,0),(1,2,0,2),(2,0,2,2),(2,1,0,1),(2,2,1,0)]
  # map 0,1,2 -> signos ordenados por probabilidad en cada partido triplado (o 1,X,2 fijo)
  import itertools
  dist=lambda a,b: sum(x!=y for x,y in zip(a,b))
  assert all(min(dist(w,c) for c in H4)<=1 for w in itertools.product(range(3),repeat=4))
  ```
  Para dobles, el código binario cubridor: 7 dobles al 13 = 16 columnas (código de Hamming binario [7,4], 2^7/(1+7) = 16, perfecto), que es exactamente la 2ª reducción LAE.
- **Cuando las probabilidades no son uniformes, el código perfecto no es el mejor reducido para P(14)**: se puede elegir, entre los códigos cubridores equivalentes (permutaciones de símbolos por coordenada), el que asigne más masa a sus columnas; con 4 triples hay 6^4 = 1.296 relabelings, enumerables. Esto mantiene la garantía al 13 y maximiza P(14) condicionada. No encontré que LAE ni Svenska Spel lo hagan (LAE usa una tabla fija).

### Gaps
- No pude obtener las tablas vivas de Kéri (página antigua) ni confirmar si las cotas 2011 para n = 6..12 han cambiado; una búsqueda citó una prueba k_3(7) ≥ 155 "bajo supuestos" y SDP (Gijswijt & Polak 2025) sin valores ternarios concretos.
- El porcentaje de P(14) de las reducciones 3ª-6ª no aparece en las fuentes; los 11,1 %/12,5 %/... son cálculo propio bajo uniformidad.

---

## Pregunta 5 (transversal) — Kelly adaptado a pools pari-mutuel y portfolio con presupuesto

### Takeaway
No encontré una derivación publicada de Kelly específica para quinielas 1X2; el marco aplicable es el de MacLean–Ziemba–Blazenko (fractional Kelly para apuestas de baja probabilidad y gran premio como lotto) y el de Brill et al. (número de columnas n como variable de decisión con beneficio esperado T·P(ganar) − b·n). En un pari-mutuel con take α ≈ 45 % (La Quiniela) la fracción Kelly es ≤ 0 salvo en semanas de bote con ventaja; la consecuencia práctica es "presupuesto fijo pequeño semanal + extra sólo con bote", lo que el proyecto ya aplica.

### Cited Findings
- MacLean, Ziemba & Blazenko (Management Science 1992): "Utilizing fractional Kelly strategies, we can develop a complete tradeoff of growth versus security. The theory is applicable to favorable investment situations such as blackjack, horseracing, lotto games" — [IDEAS listing](https://ideas.repec.org/a/inm/ormnsc/v38y1992i11p1562-1585.html)
- MacLean, Thorp & Ziemba, "Good and Bad Properties of the Kelly Criterion": fórmula básica f* = (bp − q)/b; el interés de Ziemba en fractional Kelly nace en parte de "investing in lotto games with low success probabilities"; Benter (1994) recomienda medio Kelly en carreras — [Good_Bad_Kelly PDF](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf)
- Revisión experimental (Uhrín et al. 2021, arXiv 2107.08827): Kelly es el método de sizing más extendido; "the most limiting assumption in their application to sports betting is the knowledge of true probabilities"; un fractional Kelly adaptativo es "a very suitable choice across a wide range of settings" — [arXiv 2107.08827](https://arxiv.org/pdf/2107.08827.pdf)
- Hvattum & Arntzen evaluaron Kelly frente a dos heurísticas de sizing en fútbol (citado en PMC 2023; no verificado el original) — [PMC10306238](https://pmc.ncbi.nlm.nih.gov/articles/PMC10306238/)
- Brill et al., Eq. 2.6: beneficio esperado = T·P[max propio > max rival] − b·n con T = C + b(n+k)(1−α); la n óptima y la entropía óptima se eligen conjuntamente; reportan cota inferior del beneficio (Apéndice E) — [arXiv 2308.14339v3](https://arxiv.org/html/2308.14339v3)

### Inferences
- **Kelly para un boleto de N columnas en pari-mutuel** (fórmula operativa, derivación propia a partir de Kelly multi-resultado): sea W el bankroll, coste C_N = 0,75·N, y la distribución discreta del premio G del boleto (calculable con la fórmula E(y) de la Pregunta 3 por categoría). La fracción f = C_N/W óptima maximiza E[log(1 + f·(G/C_N − 1))]. Con P(premio > 0) del orden de 10⁻³–10⁻² y take 45 %, E[G] < C_N en semanas normales → f* = 0 (no jugar) desde el punto de vista estrictamente Kelly; sólo con bote (C grande en la notación de Brill) y columnas infrajugadas E[G]/C_N > 1 y f* > 0 pero muy pequeño (f* ≈ (E[G]/C_N − 1)/Var-ratio, típicamente < 1 % del bankroll). Esto cuadra con el protocolo de bote del proyecto (base 27-40 €, extra sólo con bote).
- **Elección de N (cuántas columnas) vs forma del sistema**: Brill et al. demuestran que n y la entropía se eligen juntas; en 1X2, el análogo es: con pocas columnas, concentrar en la columna "chalk" (favoritos) y poner los pocos dobles en el mayor p(2)/p(1); con muchas columnas (bote), aumentar entropía = más triples en toss-ups y dobles hacia signos típicos infrajugados.

### Gaps
- No existe (que haya encontrado) un paper con Kelly cerrado para quinielas 1X2 pari-mutuel con reparto por categorías; la fórmula de arriba es adaptación estándar.
- "Hausch & Ziemba" aparecen en la literatura de carreras pari-mutuel (Dr. Z system), no localicé aplicación directa a football pools en esta sesión.

---

## Referencias no localizadas / fallos de fetch (para que el redactor lo sepa)
- Hämäläinen, Honkala, Litsyn, Östergård (1995) AMM 102:579–588 — sólo citado, sin texto.
- Clair & Letscher: leídas páginas 1–10 (football pools completo); la parte de torneos (§5) no es relevante.
- Hauser, König & Krylova (IHS 87): sólo abstract legible; cuerpo en alemán con extracción deficiente.
- Thornlund 2012 (Stryktipset): sólo abstract; PDF escaneado.
- loteriasyapuestas.es: HTTP 403 al fetch; datos tomados del snippet de búsqueda y de betbrothers.es.
- Nemhauser–Wolsey–Fisher 1978 (garantía 1−1/e del greedy submodular): citado de memoria, no fetchado.
