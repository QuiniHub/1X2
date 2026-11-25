# Which strong favourite will fail? Ex-ante ranking methods for "favourite failure" (football, UCL/UEL focus)

Research date: 2026-11-25. Scope: academic + practitioner methods that rank candidate favourites by probability of NOT winning, using pre-match signals (rotation / line-ups, injuries, congestion, form divergence, incentives, market movement, bookmaker disagreement, xG regression, fragility, classifiers). Favourite-longshot bias, closing odds as benchmark, Dixon-Coles and Shin are deliberately skipped.

Overall verdict up front: I found NO peer-reviewed method that explicitly targets "favourite fails" as a classification problem and demonstrates lift over the closing market on that target. The literature is fragmented: (a) general ML-vs-odds papers (mostly no edge, a few narrow ones), (b) congestion/rotation studies that measure team performance rather than betting value and mostly find small or null effects on results, (c) market-value / line-up work showing squad value is a strong strength proxy but never tested on announced-XI deviations, (d) market-microstructure papers on overreaction. The "practical recipe" in KQ5 is therefore an assembly of individually-sourced components, not a replication of a published pipeline.

---

## KQ1. Does any published method beat the closing market at predicting favourite failures? Features and lift?

### Takeaway
No. The best-documented edges are small, narrow and come from xG-based calibration or from exploiting overreaction, not from an upset-specific classifier. The only upset-targeted academic paper (Le, Ferrara & Flammini 2015, Twitter sentiment) reports ~8% margin on a tiny sample and has not been replicated. Everything else treats favourite failure implicitly via 1X2 probabilities.

### Cited Findings
- Review of ML for soccer prediction (Bunker, Yeung, Fujii 2024): betting odds "have proven difficult to beat"; a gradient-boosting model with sophisticated features could not outperform predictions based on bookmaker odds; best goals-only models are gradient-boosted trees (CatBoost) on pi-ratings. — [arXiv 2403.07669](https://arxiv.org/abs/2403.07669)
- Systematic review of ML in sports betting (2024): the betting line is a good predictor of straight-up winners; models rarely beat it. — [arXiv 2410.21484](https://arxiv.org/pdf/2410.21484)
- 2025 six-classifier comparison: the de-vigged bookmaker probability is among the strongest baselines, with error close to the best model. — [Computation 14(9):195](https://doi.org/10.3390/computation14090195)
- Wilkens (2026, Journal of Sports Analytics 12): Skellam model on recent xG + isotonic calibration, 11 Bundesliga seasons 2014/15-2024/25. Reported ~10% return at average market odds and ~15% at best available prices, while acknowledging bookmaker odds show superior calibration overall; the edge lies in a few signals the market misses. Also reports bettors overweight previous-season records and under-apply regression to the mean. (Full text paywalled; figures from abstract/search summaries.) — [SAGE](https://journals.sagepub.com/doi/10.1177/22150218261416681); index record [sponet.de](https://sponet.de/sponet/Record/4097217?lng=en)
- Ren & Susnjak (2022): Premier League 2019-2021, ensemble classifiers + Kelly Index to sort matches by predictive difficulty; define an "upset" as a case where the model is right while the bookmaker both predicted wrongly and gave the highest odds to the actual outcome; profit only when restricted to high-confidence matches; no ROI figure in abstract. — [arXiv 2211.15734](https://arxiv.org/abs/2211.15734)
- Le, Ferrara & Flammini (2015): the only paper framed explicitly on upsets ("outcomes deemed highly unlikely by professional bookmakers"); real-time Twitter sentiment just before kick-off; 2014 World Cup + four European leagues and UCL (25 Oct-26 Nov 2014); reports >8% marginal profit with simple strategies. Tiny sample, feasibility study. — [arXiv 1502.05886](https://arxiv.org/abs/1502.05886)
- Swedish thesis (Allsvenskan): best ML model ~52% accuracy vs ~40% for picking the lowest-odds outcome (student work, small league). — [DiVA](https://www.diva-portal.org/smash/get/diva2:1772002/FULLTEXT01.pdf)
- "Profiting from overreaction in soccer betting odds" (JQAS 16(3), 2020) is a peer-reviewed overreaction strategy paper; full text could not be fetched (403), numbers not confirmed. — [LSE Research Online](https://researchonline.lse.ac.uk/id/eprint/115490); [JQAS](https://www.degruyterbrill.com/document/doi/10.1515/jqas-2019-0009/pdf)
- Odachowski & Grekow (2012): 1,116 matches; pre-match odds MOVEMENTS carry information about final results ("collective knowledge embedded in bookmaker odds can be used to predict the final result"). — [ResearchGate](https://www.researchgate.net/publication/262395354_Using_Bookmaker_Odds_to_Predict_the_Final_Result_of_Football_Matches)
- Odds-only vs GLM on 90,014 matches, 2012-2024, five bookmakers (2026): large-dataset reference for testing any favourite-failure signal against the efficient-market baseline. — [arXiv 2604.17194](https://arxiv.org/pdf/2604.17194)

### Inferences
- A "favourite fails" classifier should be trained on the RESIDUAL (actual outcome minus closing-odds probability), not on raw outcomes; otherwise it re-learns the odds. None of the found papers does this explicitly for favourites.
- The realistic target is not "beat the market" but "rank the 3-5 flagged favourites of a round better than chance": a within-round ordinal problem the literature has not studied.

### Gaps
- No paper found with "favourite does not win" as the binary target with reported AUC/lift vs implied probability (three phrasings tried). Genuine hole.
- Wilkens 2026 full text inaccessible; the 10%/15% return and the regression-to-the-mean finding come from abstract-level summaries.

---

## KQ2. How much does announced rotation / starting-XI value change win probability (quantified)?

### Takeaway
Squad market value (Transfermarkt) is as predictive as Elo for UEFA matches and starting-XI value share even predicts penalty shootouts, but no study quantifies the win-probability shift from the ANNOUNCED XI deviating from the usual XI. Rotation studies find negative effects that are small, league-dependent and larger for richer clubs.

### Cited Findings
- Csurilla & Csató (2026): UCL + UEL 2020/21-2024/25; Football Club Elo and Transfermarkt squad values give "almost identical out-of-sample accuracy" separately; combining gives a modest improvement; squad-level values, not line-ups. — [arXiv 2609.21674](https://arxiv.org/abs/2609.21674)
- van Hemert & van der Kamp (2026): pre-game strength = market value of starting 11 / combined starting-11 value of both teams (%); this ratio predicts the winner of penalty shootouts, i.e., starting-XI value carries signal even in nominally random events. — [IJSSC](https://doi.org/10.1177/17479541261416771)
- Lower-level English football (2024): uses log of total LINEUP market value (starters + subs) inside Colley/Massey ratings rather than squad totals; shows lineup-level valuation is practical with free Transfermarkt data. — [arXiv 2411.09085](https://arxiv.org/html/2411.09085v1)
- Peeters (2018): Transfermarkt crowd valuations predict international results (abstract only). — [ResearchGate](https://www.researchgate.net/publication/322175868_Testing_the_Wisdom_of_Crowds_in_the_field_Transfermarkt_valuations_and_international_soccer_results)
- Mehta, Bassek, Garnica-Caparros & Memmert (2024, IJSSC 19(6):2467-2475): 16,720 matches, ENG/FRA/ITA/ESP, 2010/11-2021/22; universally deploying rotation does not yield more season points, but the effect of rotation on success keeps increasing with team market value; more rotation negatively affected match points in EPL and Ligue 1, negligible in Serie A and La Liga. — [ResearchGate](https://www.researchgate.net/publication/383324807_Chop_and_Change_Examining_the_occurrence_of_squad_rotation_and_its_effect_on_team_performance_in_top_European_football_leagues); [DOI](https://doi.org/10.1177/17479541241274438)
- Bekris et al. (2020, Journal of Human Sport and Exercise): UCL quarter-finalists 2014/15-2017/18; when many players were in the starting list for three games in a week, more domestic points were lost; larger starting-list changes between games also hurt domestic results (small cohort). — [DOAJ record](https://doaj.org/article/21ef6cc830a44df19d8180d78e9a42d9); regression table [ResearchGate](https://www.researchgate.net/figure/Regression-model-predicting-the-total-points-won-during-all-competitive-years_tbl1_338230371)
- 2025 mediation study: increased rotation negatively affects match outcomes, partly mediated by declines in passing and shooting performance (abstract only; 403 on full text). — [ResearchGate](https://www.researchgate.net/publication/395557638_The_negative_impact_of_squad_rotation_on_football_match_outcomes_Mediating_roles_of_passing_and_shooting_performance)
- Berkeley SAG blog (98 top-5-league teams, 2016-17): game-to-game lineup changes vs change in points: p=0.359, r2=0.106; changes/game vs season points r2<0.01. Chelsea (fewest changes) and Real Madrid (most changes) both won titles with 93 pts. — [Berkeley Sports Analytics](https://sportsanalytics.studentorg.berkeley.edu/articles/soccer-squad-rotation.html)
- Injury side: a 1% rise in predicted severe-injury probability is associated with ~2.29% lower market value, so Transfermarkt values already partially price availability risk. — [Nature HSSC](https://www.nature.com/articles/s41599-026-06511-w)
- Practitioner descriptions (unmeasured): most volatile pre-match odds movement in the 60-90 min before kick-off when XIs are announced; markets react to team news relative to what was already expected. — [GoalIQ](https://www.goaliqai.com/how-betting-markets-absorb-team-news/); [22bet guide](https://news.22bet.com/wiki/betting-guide/lineups-team-news-injuries-football-betting-strategy-odds-movement/)

### Inferences
- Replicable proxy: xi_value_share = TM value of announced XI / (XI_home + XI_away); rotation_gap = 1 - value(announced XI) / value(modal XI over last 5 matches). Literature supports that XI value is informative and that rotation hurts more for high-value teams (exactly the strong-favourite case), but the coefficient must be estimated in-house: no published number maps "x% of XI value rested" to "y pp less win probability".
- Markets reprice within minutes of team sheets; an XI-based signal is exploitable for La Quiniela only because Quiniela prices are fixed before line-ups are known. That is the structural edge, not a market inefficiency.

### Gaps
- No study quantifying the win-probability effect of announced-XI deviations from the usual XI. Bekris and the mediation paper are small cohorts; Mehta et al. is seasonal, not match-level predictive.
- No study on the predictive value of PREDICTED line-ups (media / Transfermarkt) vs confirmed ones.

---

## KQ3. Rest days / congestion in European competition (2018-2026): any effect at all on results?

### Takeaway
Consistent null-to-tiny effect on RESULTS. The two largest studies (CIES/UEFA 2015: 15 leagues 2009/10-2014/15; Buchheit et al. 2022: 7 leagues, >61,000 fixtures, 2001-2021) find European midweek games do not reduce domestic points; venue dominates. Congestion raises muscle-injury rates (Bengtsson 2013) but not loss rates.

### Cited Findings
- CIES Football Observatory for UEFA (Poli, Besson, Ravenel, Aug 2015), 15 associations, 2009/10-2014/15: points per domestic match without vs with a European game within 5 days: total 1.74 vs 1.72; home 2.02 vs 1.97; away 1.46 vs 1.48; CL teams 1.99 vs 1.96; EL teams 1.64 vs 1.66; by full recovery days: 1-2 days 1.75, 3 days 1.81, 4-5 days 1.72, >5 days 1.74; none statistically significant. Conclusion: explaining domestic defeats by fatigue from UEFA participation "cannot be considered as a valid argument from a scientific perspective". — [UEFA PDF](https://www.uefa.com/MultimediaFiles/Download/competitions/General/02/29/97/46/2299746_DOWNLOAD.pdf)
- Buchheit, Settembre, Hader, Tarascon, McHugh, Verheijen (SPSR 175, Oct 2022): top 7 leagues, 20 seasons 2001/02-2020/21, 43 competitions, 269 teams, >61,000 fixtures (Transfermarkt). CL teams vs non-CL: wins 58.5% (2001-11) -> 64.8% (2011-21), points/match 1.99 -> 2.14; EL teams 1.58 -> 1.72. With only 2 days of recovery after a European match, CL teams still gained up to +0.5 pts/match more than average non-European teams in non-congested fixtures; the away/away vs home/home drop is similar to the normal home-away gap (~0.1 pts); travel pattern (home/home vs away/home) made no difference. Home/home congested CL teams in the last decade: 77% wins, >2.2 pts/match. — [SPSR PDF](https://sportperfsci.com/wp-content/uploads/2022/10/SPSR175_Buchheit.pdf); summary [Kitman Labs](https://www.kitmanlabs.com/blog/verheijen-20-year-study/)
- Bengtsson, Ekstrand, Hägglund (BJSM 2013, 11-year UEFA CL injury study): fixture congestion increases muscle-injury rates (lower when >=6 days between matches) but has no or very limited influence on team match performance. — [ResearchGate](https://www.researchgate.net/publication/249319881_Muscle_injury_rates_in_professional_football_increase_with_fixture_congestion_An_11-year_follow-up_of_the_UEFA_Champions_League_injury_study)
- Single-club 2011-12 study (UCL + Ligue 1): shorter rest reduced high-speed running; match-outcome effects unclear. — [ResearchGate](https://www.researchgate.net/publication/235668871_The_effects_of_a_congested_fixture_period_on_physical_performance_technical_activity_and_injury_rate_during_matches_in_a_professional_soccer_team)

### Inferences
- For ranking favourites, rest days / congestion deserve near-zero weight. The studied direction is European match -> domestic match; the reverse (domestic -> European midweek) has no dedicated outcome study, but symmetry of the null is plausible.
- The useful residual signal is not fatigue itself but what the coach does about it (rotation), covered in KQ2.

### Gaps
- No 2018-2026 study specifically on rest days before UCL/UEL league-phase matches (36-team format from 2024/25). Both large studies end in 2015 and 2021 and look at the domestic side.

---

## KQ4. Other signals: motivation/incentives, market movement, bookmaker disagreement, xG regression, fragility

### Takeaway
Incentive effects are documented at format level (dead rubbers ~15% of old-format group games, ~2% projected in the new format) but not as a match-level upset predictor; odds movement carries information (Odachowski & Grekow) and bettors overreact to news (Ötting et al.); no study tests cross-bookmaker dispersion or goals-conceded variance as favourite-failure predictors.

### Cited Findings
- Dead rubbers: the old UCL format "frequently produced non-competitive fixtures, including so-called dead rubbers" in final rounds. — [arXiv 2508.20075](https://arxiv.org/html/2508.20075v5)
- Simulation (UWA, 5,000 matches): dead-rubber ratio falls to ~2% under the new league phase vs 15% in the old format. — [UWA](https://www.uwa.edu.au/news/article/2024/september/champions-league-data-suggests-new-format-could-end-up-being-fairer-and-more-competitive)
- New-format incentives: "robustly stronger incentives for offensive play" in the league phase (first demonstration that format changes on-field behaviour). — [arXiv 2509.13141](https://arxiv.org/pdf/2509.13141)
- Qualification-threshold forecasting for the league phase via Dixon-Coles (open method; useful to compute each favourite's marginal value of 3 points on a given matchday). — [arXiv 2508.20075](https://arxiv.org/pdf/2508.20075)
- Odds movement: 1,116 matches; changes in bookmaker odds before kick-off are informative about the final result. — [Odachowski & Grekow 2012](https://www.researchgate.net/publication/262395354_Using_Bookmaker_Odds_to_Predict_the_Final_Result_of_Football_Matches)
- European football master's thesis (CBS): closing odds more accurate than opening; most movement on match day; home favourites priced above ~75% showed abnormal positive returns, i.e. strong home favourites were UNDER-priced (opposite of a fade signal). — [CBS thesis](https://research-api.cbs.dk/ws/portalfiles/portal/60750333/237159_final_digital.pdf)
- NFL (2002-2011, 2,560 games): opening vs closing lines not significantly different in predictive value; line moves rarely exceed 2 points; caution against over-reading movement. — [arXiv 1211.4000](https://arxiv.org/pdf/1211.4000)
- Overreaction to news: Ötting, Michels, Langrock, Deutscher, 1 Hz stakes data from a large European bookmaker; bettors overreact to news (live market). — [arXiv 2108.00821](https://ar5iv.labs.arxiv.org/html/2108.00821); cited as "Ötting et al. (2024)" in [arXiv 2505.21275](https://arxiv.org/html/2505.21275v1)
- Overreaction strategy paper (JQAS 2020) exists; numbers unverified (paywall). — [JQAS 16(3)](https://econpapers.repec.org/RePEc:bpj:jqsprt:v:16:y:2020:i:3:p:193-209:n:1)
- Bookmaker vs exchange: the betting exchange is clearly superior to bookmakers over 5,478 matches (IJF 2010), so "disagreement" is better measured as bookmaker consensus vs exchange price than between bookmakers. — [Franck, Verbeek, Nüesch 2010](https://www.unifr.ch/tim/en/assets/public/uploads/Publication%20list/2010/IJoF_Franck_Verbeek_Nuesch.pdf)
- xG regression: Wilkens (2026) finds bettors under-apply regression to the mean and overweight previous-season records; the xG-Skellam edge is consistent with fading over-performers. Practitioner claims (">15% xG over-performance over 20 games reverts within 5% ~78% of the time"; "+1-3 pp accuracy") are UNSOURCED blog figures. — [SAGE](https://journals.sagepub.com/doi/10.1177/22150218261416681); unsourced claims at [predictionengine.app](https://predictionengine.app/learn/what-is-xg-soccer-betting)

### Inferences
- Incentive signal is computable for free: simulate the league-phase table (Dixon-Coles as in arXiv 2508.20075) and compute delta P(top-8 / top-24) from a win vs a draw for the favourite; a near-zero delta flags a potential dead rubber. Rare under the new format (~2%), so it fires mainly on matchdays 7-8.
- Dispersion between bookmakers has no empirical support in the literature found; movement (open->close) and the bookmaker-vs-exchange gap do. For La Quiniela, movement itself cannot be traded (fixed prices), but the gap between the Quiniela-implied probability and the Pinnacle/Betfair closing price is the best-validated "favourite failure" signal available: favourites whose market price drifted up after Quiniela odds were set.

### Gaps
- No study testing goals-conceded variance / "fragility" as a predictor beyond standard strength models.
- No study on domestic-vs-European form divergence as a predictor of European upsets.
- No peer-reviewed study on bookmaker disagreement (odds dispersion) as a predictor.

---

## KQ5. Practical ranking recipe replicable in Python with free data

### Takeaway
Because no published pipeline exists, the recipe assembles the components that DO have evidence, weighted by evidence strength: (1) market gap vs Quiniela, (2) announced/expected XI value share and rotation gap, (3) xG over-performance, (4) incentive delta; congestion/rest days get ~0 weight. Validation must be on the residual vs closing probability and on within-round ranking.

### Cited Findings (data and tools)
- Transfermarkt line-up and squad-value scraping is standard in the academic literature (Buchheit et al. scraped all fixtures from Transfermarkt; arXiv 2411.09085 uses lineup-level TM values). — [SPSR 175](https://sportperfsci.com/wp-content/uploads/2022/10/SPSR175_Buchheit.pdf); [arXiv 2411.09085](https://arxiv.org/html/2411.09085v1)
- Football Club Elo Ratings (clubelo.com) match Transfermarkt accuracy in UEFA competitions; combining both improves modestly. — [arXiv 2609.21674](https://arxiv.org/abs/2609.21674)
- CatBoost / gradient-boosted trees on pi-ratings are the best goals-only models per the 2024 review. — [arXiv 2403.07669](https://arxiv.org/abs/2403.07669)
- Dixon-Coles simulation of UEFA league-phase thresholds (open method) for the incentive component. — [arXiv 2508.20075](https://arxiv.org/pdf/2508.20075)
- xG + Skellam + isotonic calibration pipeline (Wilkens 2026) as the xG component. — [SAGE](https://journals.sagepub.com/doi/10.1177/22150218261416681)
- Kelly-Index style match-difficulty binning (Ren & Susnjak) to restrict action to matches where the model is confident. — [arXiv 2211.15734](https://arxiv.org/abs/2211.15734)

### Inferences (proposed recipe; in-house validation required)
1. Universe: favourites with closing (Pinnacle/Betfair) implied P(win) >= 0.60 in the round. Target y = 1 if the favourite does not win.
2. Features (all free):
   - gap_market = P_closing(fav) - P_quiniela_implied(fav); negative = market has cooled on the favourite. Evidence: odds movement informative (Odachowski & Grekow); exchange > bookmaker (Franck et al.).
   - xi_value_share = TM value of expected/announced XI / sum of both XIs; rotation_gap = 1 - value(announced XI)/value(modal XI last 5). Evidence: KQ2 (Csurilla & Csató; van Hemert; Mehta et al.: effect grows with team value).
   - absent_value_share = TM value of injured/suspended regulars / modal-XI value (Transfermarkt injury pages).
   - xg_overperf = (goals - xG)/xG over last 10 (Understat / FBref free); flag > +0.15. Evidence: Wilkens (bettors under-apply regression).
   - incentive_delta = P(qualify | win) - P(qualify | draw) from a Dixon-Coles league-phase simulation; flag < 0.02.
   - rest_days, travel: controls only; expect ~0 (CIES, Buchheit).
3. Model: logistic regression or CatBoost on the RESIDUAL (y - P_closing(not win)), leave-one-season-out CV; report AUC, within-round Spearman rank vs actual failures, and Brier of (P_closing + model adjustment) vs P_closing alone. If Brier does not improve out of sample, keep the signals as tie-breakers only, never as probability shifters.
4. Sample-size warning: ~36-72 UCL league-phase favourites >= 0.60 per season; expect 3+ seasons before any signal is distinguishable from noise (consistent with the nulls in KQ3 and the efficiency reviews in KQ1).

### Gaps
- No open-source repository found implementing a favourite-failure ranker; blogs named in the brief (Tony ElHabr, FC Python, Soccermatics) did not surface a dedicated post on this target within the search budget.
- The lineup-change coefficient must be estimated in-house; no published value exists.
