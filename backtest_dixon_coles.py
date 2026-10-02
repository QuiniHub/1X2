"""Backtest del modelo Dixon-Coles + devig Shin ANTES de integrarlo al motor.

Metodo (estandar de la casa: validar antes de desplegar, sin fugas de futuro):

TEST A - temporada 2025/26 completa, walk-forward mensual:
  para cada mes, entrenar D-C solo con partidos anteriores y predecir los
  partidos del mes que tengan cuotas. Comparar RPS (ranked probability
  score, menor = mejor) de: cuotas normalizadas, cuotas con Shin, D-C, y
  blends D-C+Shin. El mercado es el benchmark a batir o igualar.

TEST B - temporada 26/27 (J1-J9 de La Quiniela): comparar las
  probabilidades REALES que uso el motor (probabilidades_usadas del
  detalle de aprendizaje) contra D-C entrenado hasta la vispera de cada
  jornada, sobre los mismos partidos espanoles con signo oficial.

Salida: data/memoria_ia/backtest_dixon_coles.json + resumen por pantalla.
"""
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from modelo_dixon_coles import DixonColes, cargar_partidos, shin_devig, clave_equipo

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SALIDA = DATA / "memoria_ia" / "backtest_dixon_coles.json"

SIGNOS = ("1", "X", "2")


def rps(probs, signo_real):
    """Ranked probability score para 3 categorias ordenadas 1, X, 2."""
    acum_p = 0.0
    acum_o = 0.0
    total = 0.0
    for s in SIGNOS[:-1]:
        acum_p += probs[s]
        acum_o += 1.0 if s == signo_real else 0.0
        total += (acum_p - acum_o) ** 2
    return total / (len(SIGNOS) - 1)


def signo_de(gl, gv):
    return "1" if gl > gv else ("X" if gl == gv else "2")


def test_a(partidos):
    """2025/26 walk-forward mensual: mercado (normalizado y Shin) vs D-C vs blend."""
    objetivo = [p for p in partidos
                if datetime(2025, 8, 1) <= p["fecha"] < datetime(2026, 7, 1)
                and all(isinstance(c, (int, float)) and c for c in p["cuotas"])]
    meses = sorted({(p["fecha"].year, p["fecha"].month) for p in objetivo})
    acum = {k: [] for k in ("normalizado", "shin", "dixon_coles", "blend_50", "blend_70_mercado")}
    aciertos = {k: 0 for k in acum}
    n = 0
    for (anyo, mes) in meses:
        corte = datetime(anyo, mes, 1)
        try:
            modelo = DixonColes().entrenar(partidos, corte)
        except ValueError:
            continue
        del_mes = [p for p in objetivo if (p["fecha"].year, p["fecha"].month) == (anyo, mes)]
        for p in del_mes:
            dc = modelo.probabilidades(p["local"], p["visitante"])
            if dc is None:
                continue
            inv = [1.0 / c for c in p["cuotas"]]
            suma = sum(inv)
            norm = {s: v / suma for s, v in zip(SIGNOS, inv)}
            shin = shin_devig(p["cuotas"]) or norm
            blend50 = {s: (dc[s] + shin[s]) / 2 for s in SIGNOS}
            blend70 = {s: 0.3 * dc[s] + 0.7 * shin[s] for s in SIGNOS}
            real = signo_de(p["gl"], p["gv"])
            for nombre, probs in (("normalizado", norm), ("shin", shin), ("dixon_coles", dc),
                                  ("blend_50", blend50), ("blend_70_mercado", blend70)):
                acum[nombre].append(rps(probs, real))
                if max(probs, key=probs.get) == real:
                    aciertos[nombre] += 1
            n += 1
    return {
        "partidos_evaluados": n,
        "rps_medio": {k: round(sum(v) / len(v), 5) for k, v in acum.items() if v},
        "acierto_signo_pct": {k: round(100 * aciertos[k] / n, 1) for k in acum if n},
    }


def _norm_equipo_txt(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def test_b(partidos):
    """26/27 J1-J9: motor real (probabilidades_usadas) vs D-C walk-forward."""
    detalle = json.loads((DATA / "aprendizaje_ia.json").read_text(encoding="utf-8")).get("detalle", [])
    jornadas_fechas = {}
    for n_j in range(1, 10):
        path = DATA / "jornadas" / f"jornada_{n_j}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        fechas = [str(p.get("fecha") or "") for p in data.get("partidos", [])]
        fechas = [f for f in fechas if re.match(r"^\d{4}-\d{2}-\d{2}", f)]
        if fechas:
            jornadas_fechas[n_j] = datetime.strptime(min(fechas)[:10], "%Y-%m-%d")
        # mapa num -> (local, visitante) para castear el detalle
        jornadas_fechas[(n_j, "partidos")] = {
            int(p.get("num") or 0): (p.get("local"), p.get("visitante"))
            for p in data.get("partidos", [])
        }
    modelos = {}
    res = {k: [] for k in ("motor", "dixon_coles", "blend_50")}
    hits = {k: 0 for k in res}
    n = 0
    sin_modelo = 0
    for e in detalle:
        j = e.get("jornada")
        if not isinstance(j, int) or not (1 <= j <= 9) or j not in jornadas_fechas:
            continue
        pu = e.get("probabilidades_usadas") or {}
        if not all(s in pu for s in SIGNOS):
            continue
        # el detalle guarda "Local - Visitante" sin numerar; se parte por el guion
        trozos = re.split(r"\s+-\s+", re.sub(r"^\s*\d+\.\s*", "", str(e.get("partido") or "")), maxsplit=1)
        if len(trozos) != 2:
            continue
        local, visitante = trozos[0].strip(), trozos[1].strip()
        real = str(e.get("signo_real") or "").upper()
        if real not in SIGNOS:
            continue
        if j not in modelos:
            try:
                modelos[j] = DixonColes().entrenar(partidos, jornadas_fechas[j])
            except ValueError:
                modelos[j] = None
        modelo = modelos[j]
        dc = modelo.probabilidades(local, visitante) if modelo else None
        if dc is None:
            sin_modelo += 1  # equipos fuera del universo espanol (Liga F, Champions...)
            continue
        motor = {s: float(pu[s]) / 100.0 for s in SIGNOS}
        total = sum(motor.values()) or 1.0
        motor = {s: v / total for s, v in motor.items()}
        blend = {s: (motor[s] + dc[s]) / 2 for s in SIGNOS}
        for nombre, probs in (("motor", motor), ("dixon_coles", dc), ("blend_50", blend)):
            res[nombre].append(rps(probs, real))
            if max(probs, key=probs.get) == real:
                hits[nombre] += 1
        n += 1
    return {
        "partidos_evaluados": n,
        "sin_cobertura_dc": sin_modelo,
        "rps_medio": {k: round(sum(v) / len(v), 5) for k, v in res.items() if v},
        "acierto_signo_pct": {k: round(100 * hits[k] / n, 1) for k in res if n},
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    partidos = cargar_partidos()
    print(f"Partidos cargados: {len(partidos)}")
    print("\n== TEST A: 2025/26 walk-forward mensual (mercado vs D-C) ==")
    a = test_a(partidos)
    print(json.dumps(a, ensure_ascii=False, indent=1))
    print("\n== TEST B: 26/27 J1-J9, motor real vs D-C ==")
    b = test_b(partidos)
    print(json.dumps(b, ensure_ascii=False, indent=1))
    salida = {
        "version": 1,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Backtest Dixon-Coles + Shin vs mercado (25/26) y vs motor real (26/27 J1-J9). RPS: menor = mejor.",
        "test_a_2526_vs_mercado": a,
        "test_b_2627_vs_motor": b,
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nGuardado en", SALIDA)
