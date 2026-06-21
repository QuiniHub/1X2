import math

LABELS = ("1", "X", "2")


def clamp(value, low, high):
    return max(min(float(value), high), low)


def normalize_probs(probs):
    vals = {label: max(float((probs or {}).get(label) or 0), 0.0) for label in LABELS}
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
