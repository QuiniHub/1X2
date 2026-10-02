# Investigación mundial de métodos de predicción y juego de quinielas (octubre 2026)

Encargo de Marc (02/10/2026): documentar algoritmos, análisis y estudios de probabilidad
de cualquier web/app/paper del mundo, para decidir qué implantar en la web predictiva.
Cuatro investigaciones paralelas con fuentes citadas (academia, ratings, mercado/pari-mutuel,
apps/herramientas). Este documento es el resumen ejecutivo; el detalle con todas las fuentes
vive en la conversación de esa fecha y en los informes de los agentes.

## 1. Las cinco verdades que establece la literatura mundial

1. **El techo real de acierto 1X2 es ~50-55%** (RPS 0,19-0,21). Benchmarks: 2017 Soccer
   Prediction Challenge (Machine Learning Journal, Springer); mejor resultado publicado
   multi-liga: CatBoost + pi-ratings, RPS 0,1925 (Yeung et al. 2024). Quien anuncia 70-80%
   (Forebet, Predictz...) no resiste verificación independiente (62-70% reales sin cuotas).
2. **El algoritmo importa menos que la información** (Fischer & Heuer 2024, Springer):
   Poisson bien calibrado ≈ machine learning con las mismas features. La ganancia está en
   señales (ratings dinámicos, xG, forma, viaje) y en calibración, no en redes neuronales.
3. **El empate es el cuello de botella mundial**: mejor acierto publicado de la X: 30-37%.
   (Consistente con nuestra Regla 15: el 33% de nuestros fallos son X sin cubrir.)
4. **Las cuotas de cierre son el mejor predictor conocido** (Forrest-Goddard-Simmons 2005;
   Hvattum & Arntzen 2010; tesis CBS; caso FiveThirtyEight vs Pinnacle). Ningún rating puro
   (Elo, Glicko, Massey) las bate; las dos excepciones documentadas con ventaja: pi-ratings
   (Constantinou & Fenton 2013) y modelos xG (Wilkens 2026, Bundesliga).
5. **En pari-mutuel, el EV+ histórico real vino de botes y de jugar contra la masa**:
   Hauser et al. 2000 (Toto austríaco: la masa sobreapuesta lo probable MÁS de lo óptimo);
   sindicatos documentados (Selbee/MIT en Cash WinFall, Mandel en Virginia 1992, Klincewicz
   en Irlanda 1992) — todos explotaron botes/roll-downs, no predicción sobrehumana.
   Peña Q84 (España): esperanza matemática del premio, no maximización de aciertos.

## 2. Qué tenemos ya (validado por la investigación)

- **Blend motor+mercado (Losilla)** = la recomendación estándar de la literatura.
- **Análisis de valor contra % de apostantes LAE** = exactamente el método Q84/Hauser;
  ninguna web comercial del mundo modela esto para La Quiniela. ES nuestra ventaja.
- **Optimizador exhaustivo de estructura + Poisson-binomial de aciertos** = al nivel o por
  encima de todo lo comercial encontrado.
- **Protocolo de bote** (escalar presupuesto solo con bote) = el único mecanismo con EV+
  documentado en pools reales.
- **Estudios propios cuantificados** (revulsivo, distribución de signos, mortalidad de la X,
  sorpresas por temporada) = nadie encontrado hace esto específico para La Quiniela.

## 3. Candidatos a implantar (por prioridad, todos gratis)

| # | Qué | Por qué | Coste/datos | Prioridad |
|---|-----|---------|-------------|-----------|
| 1 | **Corrección Dixon-Coles** (ρ de marcadores bajos + decaimiento temporal ξ) en el motor | El ganador consistente de los benchmarks (RPS 0,191→0,189); corrige EXACTAMENTE la infrapredicción de 0-0/1-1 — nuestra herida de las X | Marcadores que ya tenemos; librería penaltyblog o implementación propia; backtest previo obligatorio (método git-snapshot) | **ALTA** |
| 2 | **Devig Shin** de las probabilidades de mercado | Quitar el margen bien (no proporcional) corrige el sesgo favorito-longshot; afina el blend | Trivial: fórmula sobre lo que ya tenemos de Losilla | **ALTA** |
| 3 | **Optimizar EV del premio, no P(≥10)** (estilo Q84): puntuar columnas por p_real/p_jugada × modelo de reparto | El salto filosófico que Marc pide hace meses ("se cobra lo que la masa falla") formalizado; Hauser 2000 demuestra que la masa deja valor sistemático | % público (LAE/Losilla) + modelo de reparto de premios (elquinielista publica estimaciones; CSV histórico de Losilla desde 1998 para calibrar) | **ALTA (la grande)** |
| 4 | **Pi-ratings** como señal adicional del motor | Único rating con beneficio publicado vs cuotas (EPL 2013); ratings casa/fuera separados + peso a lo reciente | Solo marcadores; penaltyblog | MEDIA |
| 5 | **Métricas serias en el aprendizaje: RPS + calibración por signo** (sustituir "precisión %") | Lo que separa el análisis serio del marketing; benchmark externo gratis: CSVs del SPI de FiveThirtyEight (2016-2023, Primera y Segunda) | Ya tenemos todo | MEDIA |
| 6 | **xG de FBref como feature (80/20 goles/xG estilo Opta)** — hay xG gratis HASTA DE SEGUNDA | El xG añade señal que el mercado no recoge del todo (Wilkens 2026) | Scraping FBref con rate-limit estricto; fiabilidad a vigilar | MEDIA-BAJA |
| 7 | **Reducidas** como compresor de coste en semanas de bote | No cambian el EV, solo la distribución — pero permiten comprar la cobertura que el motor pide con menos dinero | Matrices públicas (LAE tiene 6 oficiales) | BAJA (herramienta puntual) |
| 8 | **Kelly fraccional** para dimensionar el stake del protocolo de bote | Formaliza los escalones 108/180€; con p incierta, quarter-Kelly o menos (Chu-Wu-Swartz) | Nada nuevo | BAJA |

## 4. Qué NO hacer (también es una decisión)

- **Deep learning / redes neuronales**: no bate a GBT ni a Poisson con los mismos datos (literatura unánime).
- **Copiar webs de picks** (Forebet, Predictz...): aciertos no auditados, sin modelo del pari-mutuel.
- **ClubElo**: API cerrada desde sept-2026; no construir dependencias.
- **APIs de pago**: todo lo de la tabla es implementable gratis (regla de Marc intacta).

## 5. Proceso acordado

Nada entra al motor sin backtest previo con el método estándar (snapshots git pre-cierre +
código nuevo + comparación de señales/RPS sobre jornadas reales). Marc decide qué candidatos
se implementan y en qué orden.
