"""Pipeline profesional inicial para predicciones 1X2.

Genera dataset temporal, baseline Elo/Poisson, modelo entrenable opcional
con scikit-learn, backtesting rolling y metricas auditables.
"""

import argparse
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
except Exception:
    LogisticRegression = None
    make_pipeline = None
    StandardScaler = None

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
OUT = DATA / "modelo_predictivo"
LABELS = ("1", "X", "2")
COMPETICIONES = ("primera_division", "segunda_division", "mundial_2026", "selecciones", "liga_extranjera", "desconocida")
FEATURES = (
    "elo_diff", "elo_abs", "elo_1", "elo_x", "elo_2", "poisson_1", "poisson_x", "poisson_2",
    "base_1", "base_x", "base_2", "local_pj", "visitante_pj", "ppg_diff", "forma5_diff",
    "forma10_diff", "gf_pg_diff", "gc_pg_diff", "draw_avg", "neutral", "comp_primera_division",
    "comp_segunda_division", "comp_mundial_2026", "comp_selecciones", "comp_liga_extranjera", "comp_desconocida",
)
MIN_TRAIN = 42


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    if default is None:
        default = {}
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_hash(data):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def norm(text):
    text = str(text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value, low, high):
    return max(min(float(value), high), low)


def normalize_probs(probs):
    vals = {label: max(as_float((probs or {}).get(label)), 0.0) for label in LABELS}
    total = sum(vals.values())
    if total <= 0:
        return {"1": 1 / 3, "X": 1 / 3, "2": 1 / 3}
    return {label: vals[label] / total for label in LABELS}


def top_label(probs):
    probs = normalize_probs(probs)
    return max(LABELS, key=lambda label: probs[label])


def brier_score(items):
    if not items:
        return None
    total = 0.0
    for item in items:
        real = item.get("y")
        probs = normalize_probs(item.get("probs"))
        for label in LABELS:
            target = 1.0 if real == label else 0.0
            total += (probs[label] - target) ** 2
    return round(total / len(items), 6)


def log_loss_1x2(items):
    if not items:
        return None
    total = 0.0
    for item in items:
        real = item.get("y")
        probs = normalize_probs(item.get("probs"))
        total += -math.log(clamp(probs.get(real, 0.0), 1e-15, 1.0))
    return round(total / len(items), 6)


def accuracy_top1(items):
    if not items:
        return None
    ok = sum(1 for item in items if top_label(item.get("probs")) == item.get("y"))
    return round(ok / len(items) * 100.0, 3)


def calibration_curve(items, bins=10):
    out = []
    for idx in range(bins):
        low = idx / bins
        high = (idx + 1) / bins
        bucket = []
        for item in items:
            probs = normalize_probs(item.get("probs"))
            confidence = max(probs.values())
            if low <= confidence < high or (idx == bins - 1 and confidence <= high):
                bucket.append({**item, "probs": probs})
        if not bucket:
            continue
        out.append({
            "bin": f"{low:.1f}-{high:.1f}",
            "muestras": len(bucket),
            "confianza_media": round(sum(max(item["probs"].values()) for item in bucket) / len(bucket) * 100.0, 3),
            "acierto_top1": accuracy_top1(bucket),
        })
    return out


def grouped_metrics(items, key):
    groups = {}
    for item in items:
        groups.setdefault(item.get(key, "desconocido"), []).append(item)
    return {
        group: {
            "muestras": len(group_items),
            "accuracy_top1": accuracy_top1(group_items),
            "brier_score": brier_score(group_items),
            "log_loss": log_loss_1x2(group_items),
        }
        for group, group_items in sorted(groups.items())
    }


def evaluate_predictions(items):
    return {
        "muestras": len(items),
        "accuracy_top1": accuracy_top1(items),
        "brier_score": brier_score(items),
        "log_loss": log_loss_1x2(items),
        "calibration_curve": calibration_curve(items),
        "por_competicion": grouped_metrics(items, "competicion"),
        "por_signo_real": grouped_metrics(items, "y"),
    }


def parse_score(value):
    match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(value or ""))
    if not match:
        return None
    gl, gv = int(match.group(1)), int(match.group(2))
    if gl > 15 or gv > 15:
        return None
    return gl, gv


def result_sign(value):
    score = parse_score(value)
    if not score:
        return None
    gl, gv = score
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def comp_of(match):
    comp = str(match.get("competicion_resuelta") or (match.get("resolucion_competicion") or {}).get("competicion") or "").lower()
    if comp in COMPETICIONES:
        return comp
    names = f"{match.get('local','')} {match.get('visitante','')}".lower()
    if any(n in names for n in ("alemania", "brasil", "portugal", "inglaterra", "senegal", "mexico", "marruecos", "suiza", "ecuador")):
        return "selecciones"
    return "desconocida"


def iter_closed_matches(jornadas_dir=JORNADAS):
    out = []
    for path in sorted(Path(jornadas_dir).glob("jornada_*.json")):
        data = load_json(path, {})
        for match in data.get("partidos", []):
            if int(match.get("num") or 0) > 14:
                continue
            score = parse_score(match.get("resultado"))
            sign = result_sign(match.get("resultado"))
            if not score or sign not in LABELS:
                continue
            out.append({
                "jornada": data.get("jornada"),
                "num": match.get("num"),
                "fecha_orden": str(match.get("fecha") or data.get("fecha") or path.stem),
                "local": match.get("local") or "",
                "visitante": match.get("visitante") or "",
                "resultado": match.get("resultado"),
                "gl": score[0],
                "gv": score[1],
                "y": sign,
                "competicion": comp_of(match),
            })
    return sorted(out, key=lambda x: (str(x["fecha_orden"]), int(x.get("jornada") or 0), int(x.get("num") or 0)))


def team_state():
    return {"elo": 1500.0, "pj": 0, "pts": 0, "gf": 0, "gc": 0, "draws": 0, "last_pts": deque(maxlen=10)}


def points_for(gl, gv):
    return 3 if gl > gv else 1 if gl == gv else 0


def ppg(team):
    return as_float(team["pts"]) / max(int(team["pj"]), 1)


def gf_pg(team):
    return as_float(team["gf"]) / max(int(team["pj"]), 1)


def gc_pg(team):
    return as_float(team["gc"]) / max(int(team["pj"]), 1)


def form(team, n):
    vals = list(team["last_pts"])[-n:]
    return sum(vals) / max(len(vals), 1) if vals else 0.0


def draw_rate(a, b):
    if not a["pj"] or not b["pj"]:
        return 0.26
    return (as_float(a["draws"]) / a["pj"] + as_float(b["draws"]) / b["pj"]) / 2


def is_neutral(comp):
    return comp in {"mundial_2026", "selecciones"}


def expected_elo(local_elo, away_elo, neutral=False):
    home_adv = 0.0 if neutral else 55.0
    return 1.0 / (1.0 + 10.0 ** (-((local_elo + home_adv) - away_elo) / 400.0))


def elo_probs(local, away, neutral=False):
    exp_home = expected_elo(local["elo"], away["elo"], neutral)
    diff = abs((local["elo"] + (0 if neutral else 55)) - away["elo"])
    px = clamp(draw_rate(local, away) + 0.06 - diff / 2600.0, 0.18, 0.36)
    return normalize_probs({"1": (1 - px) * exp_home, "X": px, "2": (1 - px) * (1 - exp_home)})


def poisson_pmf(lam, k):
    lam = clamp(lam, 0.05, 5.0)
    return math.exp(-lam) * lam ** k / math.factorial(k)


def poisson_probs(local, away, neutral=False):
    base = 1.28
    bonus = 0.0 if neutral else 0.16
    lam_l = clamp(((gf_pg(local) if local["pj"] else base) + (gc_pg(away) if away["pj"] else base)) / 2 + bonus, 0.25, 3.8)
    lam_v = clamp(((gf_pg(away) if away["pj"] else base) + (gc_pg(local) if local["pj"] else base)) / 2, 0.25, 3.8)
    probs = {"1": 0.0, "X": 0.0, "2": 0.0}
    for gl in range(8):
        p_gl = poisson_pmf(lam_l, gl)
        for gv in range(8):
            probs["1" if gl > gv else "X" if gl == gv else "2"] += p_gl * poisson_pmf(lam_v, gv)
    return normalize_probs(probs)


def update_state(local, away, gl, gv, neutral=False):
    exp_home = expected_elo(local["elo"], away["elo"], neutral)
    real_home = 1.0 if gl > gv else 0.5 if gl == gv else 0.0
    change = (22 + min(abs(gl - gv), 4) * 3) * (real_home - exp_home)
    local["elo"] += change
    away["elo"] -= change
    for team, gf, gc in ((local, gl, gv), (away, gv, gl)):
        team["pj"] += 1
        team["gf"] += gf
        team["gc"] += gc
        team["pts"] += points_for(gf, gc)
        team["draws"] += 1 if gf == gc else 0
        team["last_pts"].append(points_for(gf, gc))


def prior(counter):
    total = sum(counter.values())
    return {label: (counter[label] + 1) / (total + 3) for label in LABELS}


def make_features(local, away, comp, prior_probs):
    neutral = is_neutral(comp)
    pe = elo_probs(local, away, neutral)
    pp = poisson_probs(local, away, neutral)
    pb = normalize_probs({label: pe[label] * 0.42 + pp[label] * 0.42 + prior_probs[label] * 0.16 for label in LABELS})
    elo_diff = (local["elo"] + (0 if neutral else 55)) - away["elo"]
    row = {
        "elo_diff": elo_diff,
        "elo_abs": abs(elo_diff),
        "elo_1": pe["1"], "elo_x": pe["X"], "elo_2": pe["2"],
        "poisson_1": pp["1"], "poisson_x": pp["X"], "poisson_2": pp["2"],
        "base_1": pb["1"], "base_x": pb["X"], "base_2": pb["2"],
        "local_pj": local["pj"], "visitante_pj": away["pj"], "ppg_diff": ppg(local) - ppg(away),
        "forma5_diff": form(local, 5) - form(away, 5), "forma10_diff": form(local, 10) - form(away, 10),
        "gf_pg_diff": gf_pg(local) - gf_pg(away), "gc_pg_diff": gc_pg(local) - gc_pg(away),
        "draw_avg": draw_rate(local, away), "neutral": 1.0 if neutral else 0.0,
    }
    for c in COMPETICIONES:
        row[f"comp_{c}"] = 1.0 if comp == c else 0.0
    return row, pb


def build_dataset(jornadas_dir=JORNADAS):
    states = defaultdict(lambda: defaultdict(team_state))
    priors = defaultdict(Counter)
    rows = []
    for match in iter_closed_matches(jornadas_dir):
        comp = match["competicion"]
        local_key, away_key = norm(match["local"]), norm(match["visitante"])
        if not local_key or not away_key:
            continue
        local, away = states[comp][local_key], states[comp][away_key]
        features, base = make_features(local, away, comp, prior(priors[comp]))
        row = {**match, **{k: round(as_float(v), 8) for k, v in features.items()}}
        row["prob_baseline"] = {k: round(v, 8) for k, v in base.items()}
        rows.append(row)
        update_state(local, away, match["gl"], match["gv"], is_neutral(comp))
        priors[comp][match["y"]] += 1
    return rows


def matrix_x(rows):
    return [[as_float(row.get(col)) for col in FEATURES] for row in rows]


def vector_y(rows):
    return [row["y"] for row in rows]


def can_train(rows):
    counts = Counter(vector_y(rows))
    return len(rows) >= MIN_TRAIN and all(counts[label] >= 2 for label in LABELS)


def train_model(rows):
    if LogisticRegression is None or make_pipeline is None or StandardScaler is None or not can_train(rows):
        return None
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced"))
    model.fit(matrix_x(rows), vector_y(rows))
    return model


def predict_model(model, row):
    if model is None:
        return dict(row.get("prob_baseline") or {"1": 1 / 3, "X": 1 / 3, "2": 1 / 3})
    raw = model.predict_proba(matrix_x([row]))[0]
    classes = list(getattr(model[-1], "classes_", []))
    return normalize_probs({label: raw[classes.index(label)] if label in classes else 0.0 for label in LABELS})


def baseline_items(rows):
    return [{"jornada": r["jornada"], "num": r["num"], "competicion": r["competicion"], "y": r["y"], "probs": r["prob_baseline"]} for r in rows]


def rolling_backtest(rows):
    if len(rows) < MIN_TRAIN + 8:
        return {"estado": "muestra_insuficiente", "muestras_dataset": len(rows), "metricas": evaluate_predictions(baseline_items(rows))}
    preds = []
    model = None
    for index, row in enumerate(rows):
        if index < MIN_TRAIN:
            continue
        if model is None or (index - MIN_TRAIN) % 8 == 0:
            model = train_model(rows[:index])
        probs = predict_model(model, row)
        preds.append({
            "jornada": row["jornada"], "num": row["num"], "competicion": row["competicion"],
            "y": row["y"], "probs": {k: round(v, 8) for k, v in probs.items()},
            "top": top_label(probs), "acierto_top1": top_label(probs) == row["y"],
        })
    return {"estado": "ok", "muestras_backtesting": len(preds), "metricas": evaluate_predictions(preds), "ultimas_predicciones": preds[-120:]}


def run(root=ROOT):
    global ROOT, DATA, JORNADAS, OUT
    ROOT = Path(root)
    DATA = ROOT / "data"
    JORNADAS = DATA / "jornadas"
    OUT = DATA / "modelo_predictivo"
    rows = build_dataset(JORNADAS)
    version_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dataset_hash = stable_hash(rows)
    model = train_model(rows)
    in_sample = [{"jornada": r["jornada"], "num": r["num"], "competicion": r["competicion"], "y": r["y"], "probs": predict_model(model, r)} for r in rows]
    backtest = rolling_backtest(rows)
    payload = {
        "version": "1.0", "generado_en": now_iso(), "version_id": version_id, "dataset_hash": dataset_hash,
        "features": list(FEATURES), "labels": list(LABELS), "muestras": len(rows), "rows": rows,
    }
    metrics = {
        "version": "1.0", "generado_en": now_iso(), "version_id": version_id, "dataset_hash": dataset_hash,
        "estado": "modelo_entrenado" if model is not None else "baseline_sin_modelo_entrenado",
        "sklearn_disponible": LogisticRegression is not None,
        "muestras": len(rows), "muestras_por_competicion": dict(Counter(r["competicion"] for r in rows)),
        "baseline_elo_poisson": evaluate_predictions(baseline_items(rows)),
        "modelo_entrenable_in_sample": evaluate_predictions(in_sample),
        "backtesting_rolling": backtest,
        "nota": "El backtesting rolling es la metrica principal; in_sample solo diagnostica ajuste interno.",
    }
    manifest = {"version_id": version_id, "dataset_hash": dataset_hash, "generado_en": metrics["generado_en"], "estado": metrics["estado"], "muestras": len(rows)}
    save_json(OUT / "dataset_partidos.json", payload)
    save_json(OUT / "metricas_modelo.json", metrics)
    save_json(OUT / "backtesting_rolling.json", backtest)
    save_json(OUT / "modelo_actual.json", manifest)
    save_json(OUT / "versiones" / version_id / "manifest.json", manifest)
    print(f"Modelo predictivo 1X2 actualizado: {len(rows)} partidos, {metrics['estado']}")
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Genera dataset, baseline Elo/Poisson, modelo entrenable y backtesting rolling 1X2.")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    run(Path(args.root))


if __name__ == "__main__":
    main()
