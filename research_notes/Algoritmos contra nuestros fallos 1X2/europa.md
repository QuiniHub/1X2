# UEFA club competitions (UCL / UEL / UECL, league-phase era 2024-26): predictors for 1X2

Scope note: evidence collected 2026-11-25. Peer-reviewed / arXiv sources weighted over blogs; tipster sites discarded. Where I computed a figure myself from a league table it is flagged "(own calc)".

## Key Question 1 — Measured home advantage in UCL/UEL league phase 2024-26 vs domestic leagues

### Takeaway
Home advantage in the UCL league phase is *larger* than in domestic leagues, not smaller: home wins were 53.5% (2024/25) and 49.3% (2025/26) versus 43.9% in the Big-4 domestic leagues, and draws collapsed to 12.5% in 2024/25 (17.4% in 2025/26) versus ~26% domestically. The effect is driven by strength inequality (favourites are usually at home half the time and win), not by a bigger "venue" effect per se; Elo-fitted home advantage for UEFA matches is ~40-73 Elo points (2022-25), and ClubElo uses HFA ≈ 71 points for European fixtures, higher than it uses for Serie A (49).

### Cited Findings
- UCL 2024/25 league phase (144 matches): home win 53.47% / draw 12.50% / away win 34.03%; 3.26 goals per match; 15.97% of matches decided by 4+ goals. UCL 2025/26: 49.31% / 17.36% / 33.33%; 3.38 goals; 13.19% lopsided — [Predicting Qualification Thresholds... (arXiv 2508.20075)](https://arxiv.org/html/2508.20075v5)
- UEL 2024/25: 48.61% / 24.31% / 27.08%, 2.83 goals, 3.47% lopsided. UEL 2025/26: 52.78% / 17.36% / 29.86%, 2.68 goals, 4.17% lopsided — [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5)
- Comparison baselines in the same paper: old UCL group stage 2020/21–2023/24 combined 46.35% / 20.05% / 33.59% (3.09 goals); Big-4 domestic leagues 2023/24 combined 43.91% / 26.42% / 29.67% (2.92 goals, 6.57% lopsided). Authors: share of home wins in UCL 2024/25 is ~10 pp above the national-league average; UCL strength distribution more unequal than national leagues and UEL → more lopsided results and fewer draws — [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5)
- The 2024/25 UCL produced 18 draws versus ~31 expected by an independent-Poisson model trained on domestic data — [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5). Wikipedia table confirms 18 draws / 126 wins in 144 matches (own calc) — [2024–25 UCL league phase](https://en.wikipedia.org/wiki/2024%E2%80%9325_UEFA_Champions_League_league_phase); 2025/26 table gives 25 draws (own calc, columns do not fully reconcile) — [2025–26 UCL league phase](https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Champions_League_league_phase)
- UEL 2024/25 league phase: 35 drawn matches of 144 (24.3%), 408 goals (own calc from table) — [2024–25 UEL league phase](https://en.wikipedia.org/wiki/2024%E2%80%9325_UEFA_Europa_League_league_phase)
- Historical UCL group stage 2003/04–2021/22: 1,824 group matches, 1,402 decisive, home team won 61.6% of decisive matches (≈ 47.3% of all matches; 23.1% draws, own calc); logistic constant for home 0.559–0.591 — [Csató, Club coefficients in the UCL (arXiv 2304.09078)](https://arxiv.org/html/2304.09078v6)
- Devriesere et al. training set (UCL group stage 2005/06–2022/23, 1,968 matches): 46.76% home wins, 22.86% draws, 30.38% away wins; actual 2023/24 group stage 46.9/20.8/32.3; actual 2024/25 league phase 53.5/12.5/34.0. Home term in Poisson log-rate +0.1484 (≈ +16% home goal rate) — [Evaluating competitiveness in UEFA's new UCL format (arXiv 2508.08290)](https://arxiv.org/html/2508.08290v2)
- Van Damme & Baert (2,012 UCL 2008–16 + UEL 2011–16 matches): 24.2% draws; playing at home raises goal difference by +0.811, win probability by +18.3 pp and points by +0.550, ceteris paribus; HA is larger with more spectators (+0.2 pp win prob per 1,000 fans) and when the home team is stronger by UEFA coefficient — [IZA DP 12143](https://repec.iza.org/dp12143.pdf)
- Goumas (2014b), 1,384 UCL+UEL group matches: home advantage 58.8% (CL) / 58.0% (EL) in goals, 57.8% (CL) / 59.2% (EL) in points — [summary table of Goumas 2014b](https://benthamopen.com/FULLTEXT/TOSSJ-11-3/TABLE/T9/)
- Team-level HA in UCL 2003/04–2021/22 (2,344 matches, 42 teams with ≥40 matches): adjusted HA ranged 32.1% (Lille) to 79.5% (Sevilla); 37 of 42 teams had significant HA; HA larger vs weak opponents (p<0.001) and consistent between group and knockout stages (p=0.74); only 12/42 teams had a significant away disadvantage — [Journal of Human Kinetics 2024, PMC11079936](https://pmc.ncbi.nlm.nih.gov/articles/PMC11079936/)
- Elo home-advantage parameter fitted for UEFA matches by year: 40 Elo points (2022/23), 66 (2023/24), 73 (2024/25); mean home–away goal difference 0.366, xG difference 0.327 in UCL+UEL 2020/21–2024/25 — [Elo vs Transfermarkt in UEFA club competitions (arXiv 2609.21674)](https://arxiv.org/html/2609.21674)
- ClubElo's live match table applies a competition-specific HFA: 71 points for European fixtures (e.g., Man City–Napoli, Real Madrid–PSV) versus 49 for Serie A matches and 53 for MLS (methodology not documented on page) — [clubelo.com](http://clubelo.com/System)
- Domestic Big-7 leagues pooled 2011/12–2020/21 (Buchheit et al., >61,000 fixtures): 45.5% home wins, 24.6% draws, 29.9% away wins — [Buchheit et al. 2022, SPSR 175](https://sportperfsci.com/wp-content/uploads/2022/10/SPSR175_Buchheit.pdf)

### Inferences
- For a 1X2 model, the UCL league phase needs a *lower* draw prior (12–18%) than La Liga/Segunda (~26–28%), and a home-win prior near 50%. The UEL behaves more like a domestic league (draws 17–24%).
- The home effect is partly an artefact of strength dispersion: with a strong favourite the home side wins more often because half the time the favourite is at home and the 4+ goal blowouts (13–16% of UCL matches) are overwhelmingly home wins. A model that conditions on Elo difference should use a venue bump of ~0.15 in log goal rate or ~65–75 Elo, not the domestic ~50.
- 2025/26 regressed toward the mean (more draws, fewer home wins than 2024/25); two seasons are too few to claim a structural shift, and the Dixon-Coles ρ estimates in arXiv 2508.20075 were not significant.

### Gaps
- No source gives home/draw/away splits *by matchday* for the league phase; Wikipedia pages were truncated before the match results. Would need to compute from football-data.co.uk / FBref.
- No Conference League home/draw/away league-phase totals found (only UEFA goal stats: 2.38 goals/match in 2025/26 league phase — [UEFA](https://www.uefa.com/uefaconferenceleague/news/02a0-1f7ffb6441e3-a55962096e81-1000--conference-league-2025-26-league-phase-in-numbers)).
- No peer-reviewed estimate of the venue effect *holding team strength fixed* for 2024-26 specifically; arXiv 2609.21674 gives venue coefficients but with wide p-values (goal diff 0.416, p≈0.05 only in restricted-attendance subsample).

## Key Question 2 — Which cross-league rating best predicts UCL/UEL results?

### Takeaway
Elo (ClubElo-style) clearly beats the official UEFA club coefficient (73.3% vs 70.7% group-match hit rate; AUC 0.814 vs 0.784), and Transfermarkt squad value is at least as good as Elo for UCL/UEL (RPS 19.53 vs 19.73 ×100, hit rate 57.7% vs 55.8%); an equal-weight pool of Elo and Transfermarkt is the best single recipe found (RPS 19.43, significantly better than Elo alone, p=0.045). Plain Elo over-rates clubs from mid-sized leagues (Netherlands, Portugal, Turkey, Belgium) by ~0.15 points per match against Big-5 opposition.

### Cited Findings
- Csató (UCL 2003/04–2021/22): simple "higher-rated wins" accuracy — group matches: Elo 73.32% vs UEFA coefficient 70.68%; knockout qualification: 65.00% vs 61.92%; group ranking: 78.51% vs 75.22%. Logistic AUC for group matches Elo 0.814 vs UEFA 0.784; when both are included UEFA loses significance; multinomial model with draws: draws hardest to predict (AUC 0.578). Elo settings k=400, K=20 (ClubElo-like) — [arXiv 2304.09078](https://arxiv.org/html/2304.09078v6)
- Later period (2012/13–2021/22) is more predictable: Elo AUC 0.824 vs 0.797 (UEFA); knockouts 0.748 vs 0.608 — [arXiv 2304.09078](https://arxiv.org/html/2304.09078v6)
- Elo vs Transfermarkt (UCL 689 + UEL 814 matches, 2020/21–2024/25; out-of-sample 600 matches 2023/24–2024/25; ordered probit): RPS×100 Historical 23.07, Elo 19.73, Transfermarkt 19.53, Joint 19.54, Equal-weight pool 19.43, Estimated combination 19.48. Hit rates 0.51 / 0.558 / 0.577 / 0.560 / 0.568 / 0.563. Elo–TM correlation 0.877. Equal-weight vs Elo Δ=−0.297 (p=0.045); vs TM not significant (p=0.50). Goal-difference RMSE 1.71 (Elo or TM) vs 1.96 naive; R² ≈ 0.24–0.26 — [arXiv 2609.21674](https://arxiv.org/html/2609.21674)
- Same paper: no structural break in the 272 league-phase matches (all p>0.2), i.e. ratings fitted on the group-stage era still work in the league phase; removing neutral/relocated matches improves RPS slightly (19.35 vs 19.43); RPS without the 2024/25 league phase is 19.15 (that season was harder to predict) — [arXiv 2609.21674](https://arxiv.org/html/2609.21674)
- Calibration: observed home-win frequency exceeded predicted probability in every bin; in the 0.8–1.0 bin equal-weight pool predicted 0.856, observed 0.935 (n=31) → big favourites at home slightly *under*-priced by rating models — [arXiv 2609.21674](https://arxiv.org/html/2609.21674)
- Devriesere et al.: Elo-based GLM for UCL group/league matches — correct 58.3% in both 2023/24 and 2024/25; RPS 17.54 (2023/24) and 19.23 (2024/25) vs random 23.4–24.0; polynomial Elo-win-probability models 54–59% correct; no significant difference among Poisson variants. Elo win probability uses a 100-point home offset — [arXiv 2508.08290](https://arxiv.org/html/2508.08290v2)
- Cross-league bias of plain Elo (independent open-source UCL model, 66,607 matches 2010–2026, 23 competitions): mid-league clubs' actual score was 0.152 per match below Elo-expected against Big-5 clubs (n=284, 2022–26); a league-aware variant cuts the gap to −0.021 (−86%) at negligible RPS cost (European matches 2022–26, n=2,390: RPS 0.2089 → 0.2096); European matches weighted double in training — [ucl-predictor (GitHub, not peer-reviewed)](https://github.com/AsimanImanzade/ucl-predictor)
- Elo rating in arXiv 2508.20075: UCL field mean Elo 1782 (2024/25) / 1788 (2025/26), SD 137/145; UEL mean 1632/1628, SD 117/108; Transfermarkt SD 362 vs 190 (2024/25). Fitted Elo slope on goal rate 0.0021 (UCL) vs 0.0013 (UEL) → rating gaps translate to results more strongly in UCL — [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5)
- Historical UEFA coefficient still adds some signal for *group ranking* when combined with Elo (coef 0.012, significant) but not for single matches — [arXiv 2304.09078](https://arxiv.org/html/2304.09078v6)

### Inferences
- Practical recipe supported by evidence: average Elo (ClubElo) and Transfermarkt-value-based strength, then add a venue bump; expect ~56–58% hit rate and RPS ≈ 0.195 on UCL/UEL, which is ~0.01 RPS better than the typical domestic-league model (~0.205).
- UEFA coefficient (5-year) should not be used as the strength variable; at most as a tie-breaker for qualification-threshold questions.
- Because Elo from domestic play over-rates Eredivisie/Liga Portugal/Süper Lig/Pro League sides vs Big-5 opponents, a league-strength adjustment (or heavier weighting of European results) is justified; the two sources that quantify it agree in direction (ucl-predictor bias; Csató's suggestion to upweight European matches).

### Gaps
- No published head-to-head of ClubElo vs FiveThirtyEight SPI vs Opta Power Rankings on UCL matches (538 discontinued 2023). ClubElo methodology page does not document HFA or cross-league calibration.
- No bookmaker benchmark in the academic papers (arXiv 2609.21674 excludes odds deliberately), so the gap between the best rating model and closing odds on UCL is not quantified here.

## Key Question 3 — Does domestic form transfer? European results so far vs domestic position

### Takeaway
No study isolates "domestic form" vs "European form so far" as competing predictors for UCL matches. The indirect evidence says the strength ratings that work best (Elo, Transfermarkt) are built mostly from domestic matches and do not break in the league phase, and a model trained *only* on domestic-league data reproduces UCL/UEL outcomes well except for the draw rate. There is weak evidence (one open model) that weighting European results more than domestic ones helps cross-league calibration.

### Cited Findings
- Ratings mostly fed by domestic matches (ClubElo-type Elo, Transfermarkt) show no structural break in league-phase matches (Chow-type tests all p>0.2) — [arXiv 2609.21674](https://arxiv.org/html/2609.21674)
- An independent Poisson model fitted on 1,446 domestic matches (Big-4, 2023/24) with Elo difference + home advantage was used to simulate UCL/UEL thresholds; its main failure was over-predicting draws (31 vs 18 observed in UCL 2024/25); its balanced-match output is 44.3/24.9/30.8 — [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5)
- Csató: Elo "takes national league games into account" and is still the better predictor of UCL results; he suggests future ratings might weight European matches more heavily than domestic ones — [arXiv 2304.09078](https://arxiv.org/html/2304.09078v6)
- ucl-predictor weights European matches double and reports the league-gap bias of plain (domestic-driven) Elo (−0.152 per match for mid-league clubs vs Big-5) — [GitHub](https://github.com/AsimanImanzade/ucl-predictor)
- Buchheit et al.: CL clubs win 64.8% of domestic matches vs non-CL opponents (2011–21), 2.14 pts/match; EL clubs 49.2%, 1.72 pts/match; the gap grew +0.5% wins/year over two decades — [SPSR 175](https://sportperfsci.com/wp-content/uploads/2022/10/SPSR175_Buchheit.pdf)
- Team-level UCL home advantage did not differ between group and knockout stages (p=0.74), suggesting European venue effects are stable within a club across contexts — [PMC11079936](https://pmc.ncbi.nlm.nih.gov/articles/PMC11079936/)

### Inferences
- Treat domestic strength (Elo/market value) as the base; a club's own league *position* adds little beyond Elo because position already feeds Elo. European results from the first 3–5 league-phase matches are a small sample (one match ≈ 20 Elo points), so they should update, not replace, the prior.
- The Eredivisie/Portugal/Turkey/Belgium over-rating is the specific place where "domestic form does not transfer": a club dominating a mid-league at home is weaker vs Big-5 opponents than its Elo says, by roughly 0.15 points per match.

### Gaps
- No paper found that regresses UCL match outcome on domestic league position *and* European points-so-far simultaneously. Practitioner claims ("European form first") are tipster content with no data and were discarded.

## Key Question 4 — Incentives in the 36-team league phase (dead rubbers, matchday 7–8, effect on draws and favourites)

### Takeaway
Simulation evidence says the league phase has far fewer stakeless matches than the old group stage (0.75% vs 2.78% overall; 5.6% vs 15.8% in the final round) but *more* mutually beneficial draw ("collusion") opportunities (0.17% vs 0.11%, ~21% of seasons contain one, mostly on the final matchday). Qualification thresholds moved (15 points not enough for top 8 in 2024/25; 16 needed in both seasons; 9–11 points at the 24th-place line), so almost everyone has something to play for until MD8. Empirically, favourites fell more on MD8 than models expected in both seasons (PSV–Liverpool 2025; Benfica 4–2 Real Madrid, Chelsea at Napoli 2026).

### Cited Findings
- Simulation of six seasons, 10,000 runs/schedule: old group stage 2.78% stakeless / 10.28% asymmetric / 0.11% collusive / 86.82% competitive; new 36-team league phase 0.75% / 5.14% / 0.17% / 93.94%; all differences significant (p<0.01) — [arXiv 2508.08290](https://arxiv.org/html/2508.08290v2)
- Final round: group stage round 6 was 15.79% stakeless, 44.67% asymmetric, 39.17% competitive; league-phase round 8 is 5.55% stakeless, 31.69% asymmetric, 1.34% collusive, 61.42% competitive — [arXiv 2508.08290](https://arxiv.org/html/2508.08290v2)
- Collusion types (league phase): draw guarantees top 24 for both 32.7%; top 8 for one and top 24 for the other 35.2%; top 8 for both 13.3%; "small-loss" collusion 18.7%. Probability a season has ≥1 collusion opportunity: ~21.1% (league phase) vs ~10.5% (groups) — [arXiv 2508.08290](https://arxiv.org/html/2508.08290v2)
- 2024/25 UCL actual cutoffs: 8th place 16 pts (Aston Villa), 9th 15 (Atalanta, Dortmund also 15 → play-offs); 24th Club Brugge 11 pts, 25th Dinamo Zagreb 11 pts (out on tie-break), Stuttgart out with 10 — [Wikipedia 2024–25](https://en.wikipedia.org/wiki/2024%E2%80%9325_UEFA_Champions_League_league_phase); [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5)
- 2025/26 UCL cutoffs: 8th Manchester City 16 pts, 9th Real Madrid 15; 24th Benfica 9 pts, 25th Marseille 9. Eliminated: Marseille, Pafos, Union SG, PSV, Athletic, Napoli, Copenhagen, Ajax, Frankfurt, Slavia, Villarreal, Kairat — [Wikipedia 2025–26](https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Champions_League_league_phase)
- UEL 2024/25 cutoffs: 8th and 9th both 14 pts (Rangers / Bodø); 24th and 25th both 10 pts (Fenerbahçe / Braga) — [Wikipedia UEL 2024–25](https://en.wikipedia.org/wiki/2024%E2%80%9325_UEFA_Europa_League_league_phase)
- Pre-season Opta forecast for 2024/25 said 15 pts = 73% top-8 and 9 pts = 69% play-offs; reality was harsher (15 pts insufficient; 10–11 pts eliminated). Dixon-Coles refit on 2024/25: 16 pts = 73% top 8, 15 pts = 22%; for 2025/26 out-of-sample 16 pts = 82% and all 16-point teams did qualify directly — [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5)
- Authors estimate Stuttgart's and Dinamo Zagreb's eliminations had pre-season probabilities of 7.7% and 0.04% (qualification 92.3% / 99.96%), i.e. threshold variance is very high; in simulations 7 pts sometimes sufficed and 11 pts sometimes did not — [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5)
- MD8 2025/26 outcomes: Benfica 4–2 Real Madrid dropped Madrid out of the top 8; Chelsea won 3–2 at Napoli (Napoli eliminated); Arsenal 8/8 wins; Liverpool 6–0 — [Sofascore MD8 review](https://www.sofascore.com/news/ucl-round-8-review); Liverpool unbeaten until losing at PSV on MD8 2024/25 — [Racing Post](https://www.racingpost.com/sport/football-tips/champions-league/champions-league-2025-26-winner-predictions-odds-and-best-bets-a4HYn7H8Tb1q/)
- Before MD8 2025/26 only Arsenal and Bayern had a guaranteed bye; only four clubs (Frankfurt, Slavia, Villarreal, Kairat) were already out of everything — [CBS Sports MD8](https://www.cbssports.com/soccer/news/champions-league-matchday-8-odds-napoli-psg-newcastle/)
- RPS of the rating model worsened when last-matchday fixtures were excluded? No: excluding the last league-phase matchday *raised* RPS (19.54 vs 19.43), i.e. MD8 was not harder to predict than average in 2023/24–2024/25 — [arXiv 2609.21674](https://arxiv.org/html/2609.21674)

### Inferences
- "Dead rubber" is rarer in the league phase than under the old groups; the 1X2 risk on MD7–8 is not low intensity but *asymmetric* motivation (~32% of final-round matches) and the small set of mutually convenient draws. Rule of thumb: flag MD8 matches where a draw secures both sides' goal (top 24 for both is the most common type).
- Because 16 pts was the real top-8 line in both seasons and 9–11 pts the elimination line, a team on 13–15 pts entering MD7–8 is fully motivated; a team on 6–8 pts is in a must-win and tends to attack (more away wins / fewer draws, consistent with the low draw rates observed).
- Early matchdays (MD1–3) carry no incentive distortion; the incentive layer only matters for the last two rounds.

### Gaps
- No published matchday-by-matchday favourite-failure rate or draw rate for the league phase (would require closing-odds dataset; football-data.co.uk does not cover UCL). The Racing Post anecdotes (e.g. "15 of 16 favourites win") are single-matchday observations, not data.
- No empirical (not simulated) study yet on how already-qualified teams actually played on MD8 2025 or 2026 (rotation %, xG).

## Key Question 5 — Squad rotation and fixture congestion in European midweeks

### Takeaway
Top clubs' results do not suffer measurably in *domestic* matches after a European midweek: CL clubs win 70%+ at home two days after a European game (even 77% in the home/home scenario, 2011–21) and their away drop (−15 to −26 pp) is the same as the generic home/away gap. EL-level clubs are more fragile (away/away after Europe: 40% wins vs 41–56% for CL clubs). Direct rotation studies find more rotation → worse outcomes, mediated by passing/shooting, but the effect is modest and the European-match literature says depth and logistics offset it for the elite.

### Cited Findings
- Buchheit et al. 2022 (top-7 leagues, 2001/02–2020/21, 269 teams, >61,000 fixtures): CL clubs vs non-CL domestic opponents — 58.5% wins (2001–11) → 64.8% (2011–21), 1.99 → 2.14 pts/match; EL clubs 44.1% → 49.2%, 1.58 → 1.72 — [SPSR 175](https://sportperfsci.com/wp-content/uploads/2022/10/SPSR175_Buchheit.pdf)
- Same study, congested (league match within 2 days of a European midweek): CL clubs' domestic win % when not congested 67.0/46.0 (home/away, 2001–11) and 70.2/52.6 (2011–21); in the congested home/home scenario 77% wins and >2.2 pts/match (2011–21), higher than non-congested; worst case away/away 41% (2001–11) and 56.5% (2011–21) — still ≥ non-European clubs' *home* non-congested win rate (41.2% / 38.5%). EL clubs: non-congested 51.2/32.2 and 56.2/41.2; away/away after Europe 32% (2001–11) and 40% (2011–21); home/home 58% — [SPSR 175](https://sportperfsci.com/wp-content/uploads/2022/10/SPSR175_Buchheit.pdf)
- Authors' conclusion: the away-vs-home drop after Europe (−15 to −26 pp) is the same size as the generic home/away gap, so "congestion and travels are unlikely to worsen the effect of match location per se"; performance ordering home/home > away/home > home/away = away/away (2011–21); scheduling an EL club away/away is worth ≈ +0.2 pts/match to the opponent — [SPSR 175](https://sportperfsci.com/wp-content/uploads/2022/10/SPSR175_Buchheit.pdf)
- Settembre/Buchheit factor analysis (21 seasons elite European data): rest days, matches since coach appointment and match-to-match rotations influence outcomes but "their effect was much smaller than the main drivers" (team quality, venue) — [Settembre et al., factors associated with match outcomes](https://martin-buchheit.net/wp-content/uploads/2023/11/Settembre-Football-Performance-Factors.docx.pdf)
- "Chop and Change" (Int J Sports Sci & Coaching, 2024): increased rotation negatively affects match outcomes; partially mediated by declines in passing and shooting performance; universal rotation may not raise season points — [ResearchGate abstract](https://www.researchgate.net/publication/383324807_Chop_and_Change_Examining_the_occurrence_of_squad_rotation_and_its_effect_on_team_performance_in_top_European_football_leagues) (full text not accessible, 403)
- Earlier Spanish evidence (2003–06): Spanish Champions League teams did not perform below their normal standard at the weekend after a midweek match — [Consequences of a busy soccer match schedule (ResearchGate)](https://www.researchgate.net/publication/289158556_Consequences_of_a_busy_soccer_match_schedule_on_team_performance_Empirical_evidence_from_Spain)
- Secondary/blog: LaLiga players' high-intensity output drops during UCL-congested weeks vs cup weeks, especially high-minute players — [The xG Football Club substack](https://thexgfootballclub.substack.com/p/the-hidden-cost-of-midweek-matches) (not peer-reviewed)

### Inferences
- For La Quiniela: a Big-5 club playing *at home* on the weekend after a UCL match should not be downgraded; if anything the home/home sequence is its best scenario. The downgrade case is a Europa/Conference-level Spanish club (Betis, Celta, Rayo-type) playing *away* after an away European trip: ≈ −0.2 pts/match, roughly −5 pp win probability.
- Rotation itself (the midweek XI) is the mechanism, not fatigue; for UCL matchdays the relevant signal is whether the *European* XI is rotated (e.g., ahead of a derby), which none of these papers measure directly.

### Gaps
- No study quantifying the effect of rotation *within* UCL matches (favourite rests starters on MD7–8) on UCL results; the rotation literature is about domestic league outcomes.
- Buchheit's Table 3 (exact % per scenario) is a figure in the PDF; only the headline numbers quoted above are text-readable.

## Key Question 6 — Travel distance, time zones, Eastern European / Scandinavian venues, altitude

### Takeaway
For European club competitions, travel distance has at most a small positive effect on home advantage (Goumas 2014: significant at p<0.05 in Europe; Van Damme & Baert: not significant once other distance dimensions are controlled), time zones show no effect in Europe (only in South America), and the one robust moderator is altitude (+1.1 pp home-win probability per 100 m the home side is higher). Elite clubs' charter logistics appear to neutralise travel.

### Cited Findings
- Goumas 2014b ("Tyranny of distance", international club competitions, Poisson regression): HA rose with time zones crossed only in South America (p<0.001), no effect in other confederations; distance travelled positively associated with HA in Africa (p<0.01) and Europe (p<0.05), none in Asia — [IDEAS/RePEc record](https://ideas.repec.org/a/taf/rpanxx/v14y2014i1p1-13.html); [Table summary](https://benthamopen.com/FULLTEXT/TOSSJ-11-3/TABLE/T9/)
- Van Damme & Baert (2,012 UCL/UEL matches): of travel length, altitude, temperature, precipitation, cultural distance and wealth gap, only altitude difference significantly moderates HA: per +100 m, +0.050 goal difference (p=0.006), +1.1 pp win probability (p=0.014), +0.032 points (p=0.008); direction matters (home higher = more HA); cultural distance only weakly significant in one of three specs (p=0.053, "may be a statistical artefact"); travel length not significant; no derby or regional (Balkan / Northern Europe) heterogeneity — [IZA DP 12143](https://repec.iza.org/dp12143.pdf)
- Pollard & Armatas (2017), World Cup qualifying groups: each 1,000 m altitude difference = +0.115 points for the home team (cited in Van Damme & Baert) — [IZA DP 12143](https://repec.iza.org/dp12143.pdf)
- Bundesliga (6,389 away games 1986–2007): significantly negative effect of distance on away outcome — [Oberhofer, Philippovich & Winner 2010](https://www.sciencedirect.com/science/article/abs/pii/S0167487009001196); 17,376 Bundesliga matches 1964–2020 study of distance and HA over time — [PMC8656141](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8656141/) (figures not extracted)
- Buchheit et al.: similar win % for home/home vs away/home sequences shows "travelling is not that challenging for the European clubs", attributed to charter flights, hotels and recovery resources — [SPSR 175](https://sportperfsci.com/wp-content/uploads/2022/10/SPSR175_Buchheit.pdf)
- Longest 2025/26 trip: Kairat Almaty → Lisbon, 6,911 km; Bodø/Glimt plays inside the Arctic Circle — [Wikipedia 2025–26](https://en.wikipedia.org/wiki/2025%E2%80%9326_UEFA_Champions_League_league_phase). Kairat finished in the eliminated group (25–36) — same source.

### Inferences
- A distance / time-zone feature is not worth adding for UCL/UEL 1X2; the evidence is weak and elite logistics neutralise it. Altitude is real but rarely relevant in UEFA (few high-altitude venues).
- Scandinavian/Eastern venues matter through *conditions* (artificial turf, cold, hostile crowd) rather than travel; this matches the user's own Champions-League notes (artificial pitch as a surprise signal) but no quantified study was found.

### Gaps
- No quantified study of artificial turf or sub-zero temperatures on UCL results (Bodø/Glimt, Kairat, Qarabağ, Slovan).
- Goumas 2014b full text is paywalled; the "0.05 points per time zone" figure surfaced in a search snippet could not be verified and is omitted.

## Key Question 7 — Neutral-venue "home" matches (Shakhtar etc.)

### Takeaway
No systematic study quantifies the home advantage of displaced clubs. Removing neutral/relocated matches improved rating-model RPS slightly (19.35 vs 19.43), implying they are modestly noisier. Shakhtar's exile record is mixed: strong in Hamburg 2023/24 (beat Barcelona and Antwerp, 45,000+ crowds) but with much smaller crowds in Gelsenkirchen 2024/25 (21,636 vs Atalanta, 17,420 vs Young Boys); spectator count is a documented HA moderator (+0.2 pp win prob per 1,000 fans).

### Cited Findings
- Excluding neutral/relocated matches: equal-weight pool RPS 19.353 vs 19.431 for the full sample — [arXiv 2609.21674](https://arxiv.org/html/2609.21674)
- HA is consistently higher with more spectators: +0.009 goal difference, +0.2 pp win probability and +0.007 points per 1,000 extra spectators — [IZA DP 12143](https://repec.iza.org/dp12143.pdf)
- Shakhtar venues: Warsaw (2022/23), Hamburg Volksparkstadion (2023/24, wins vs Barcelona and Antwerp, >45,000 at each of Porto/Barcelona/Antwerp), Gelsenkirchen (2024/25 onward, 62,000 capacity; 21,636 vs Atalanta and 17,420 vs Young Boys); the club counts 10 different "home" venues since 2014 — [FC Bayern report](https://fcbayern.com/en/news/2024/12/shakhtar-donetsk-in-exile-a-stirring-fixture-for-bayern); [Bundesliga.com on Hamburg](https://www.bundesliga.com/en/bundesliga/news/hamburg-volksparkstadion-to-host-shakhtar-donestk-champions-league-matches-2023-24-24408); [ZDF on Gelsenkirchen](https://www.zdfheute.de/sport/fussball-champions-league-schachtar-donezk-fc-bayern-gelsenkirchen-100.html)
- Historical UCL analyses exclude the neutral 2019/20 Lisbon mini-tournament and finals when estimating HA, treating them as non-home matches — [PMC11079936](https://pmc.ncbi.nlm.nih.gov/articles/PMC11079936/); [arXiv 2304.09078](https://arxiv.org/html/2304.09078v6)

### Inferences
- Reasonable modelling choice: halve the venue bump for displaced "home" teams (and for matches behind closed doors), consistent with the crowd-size coefficient and the small RPS gain from dropping them.

### Gaps
- No win/draw/loss tally for displaced clubs' neutral home games across 2022–26 was found; would need manual compilation (Shakhtar, Dynamo Kyiv, Maccabi Tel Aviv/Haifa, Qarabağ when relocated).

## Key Question 8 — Midweek vs weekend draw rates; published UCL/UEL model accuracy and features

### Takeaway
No source isolates a midweek-vs-weekend draw effect; the draw-rate difference in UCL is explained by strength dispersion, not by the day of the week. Published UCL/UEL model accuracies cluster at 56–59% hit rate and RPS 0.175–0.197 (random ≈ 0.234–0.240; "historical frequencies" 0.231), with team strength (Elo and/or market value) and venue as the only features that matter; draws are the weakest class (AUC 0.578).

### Cited Findings
- arXiv 2609.21674 (600 UCL+UEL matches 2023/24–2024/25): RPS 0.1943 (equal-weight Elo+TM), hit rate 56.8%; historical-frequency baseline RPS 0.2307, hit 51.0%; features = rating difference, venue, competition/phase/season fixed effects — [arXiv 2609.21674](https://arxiv.org/html/2609.21674)
- arXiv 2508.08290 (UCL group/league rounds): GLM 58.3% correct, RPS 0.1754 (2023/24) and 0.1923 (2024/25); random guess 31–38% / RPS 0.234–0.240 — [arXiv 2508.08290](https://arxiv.org/html/2508.08290v2)
- Csató: Elo logistic AUC 0.814 (group matches), 0.69 (knockout), draws AUC 0.578 — [arXiv 2304.09078](https://arxiv.org/html/2304.09078v6)
- Open-source UCL model (league-aware Elo + Dixon-Coles): RPS 0.2089–0.2096 on 2,390 European matches 2022–26 including qualifiers; 0.198–0.200 holdout all competitions — [ucl-predictor](https://github.com/AsimanImanzade/ucl-predictor)
- Bayesian cumulative-probit UCL model (2013/14): 24% accuracy improvement over zero-prior control — [arXiv 1501.05831](https://arxiv.org/pdf/1501.05831)
- General football ML benchmark (not UCL-specific): best accuracy ≈ 0.52 and RPS ≈ 0.206 (XGBoost on pi-ratings) — [arXiv 2403.07669](https://arxiv.org/pdf/2403.07669)
- UCL draw shares: 12.5% (2024/25), 17.4% (2025/26), 20.1% (groups 2020–24), 22.9% (groups 2005–23), 24.2% (UCL+UEL 2008–16) versus 26.4% Big-4 domestic 2023/24 — [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5); [arXiv 2508.08290](https://arxiv.org/html/2508.08290v2); [IZA DP 12143](https://repec.iza.org/dp12143.pdf)

### Inferences
- The UCL is *more* predictable than La Liga (RPS ~0.19 vs ~0.20–0.21) because of larger strength gaps and fewer draws; the exploitable part for a Quiniela is the X: back the draw less in UCL (12–18%) and roughly as in domestic football in the UEL (17–24%).
- Features beyond strength + venue (travel, rotation, incentives) have no demonstrated predictive value in published UCL models; incentive effects are confined to MD7–8.

### Gaps
- No paper on midweek vs weekend draw rates; no UCL-specific comparison of model RPS against Pinnacle closing odds; no Kaggle notebook with a credible out-of-sample UCL benchmark was found.
- Opta Analyst publishes match probabilities but no public accuracy report for the league phase.
