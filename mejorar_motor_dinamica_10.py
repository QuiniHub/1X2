from pathlib import Path


ROOT = Path(__file__).resolve().parent
MOTOR = ROOT / "motor_prediccion_quiniela.py"

OLD_FUERZA = '''def fuerza(equipo, condicion):
    if not equipo:
        return 0.0
    pj = max(float(equipo.get("pj") or 0), 1.0)
    cond = equipo.get(condicion, {})
    cond_pj = max(float(cond.get("pj") or 0), 1.0)
    tendencias = equipo.get("tendencias", {})
    ppg = float(equipo.get("pts") or 0) / pj
    dg = float(equipo.get("dg") or 0) / pj
    cond_ppg = float(cond.get("pts") or 0) / cond_pj
    forma_5 = float(tendencias.get("forma_5_pts") or 0) / 5.0
    empates = float(tendencias.get("empates_pct") or 0)
    return ppg * 34 + dg * 12 + cond_ppg * 22 + forma_5 * 20 + empates * 0.08
'''

NEW_FUERZA = '''def forma_float(tendencias, clave, divisor):
    try:
        return float(tendencias.get(clave) or 0) / divisor
    except Exception:
        return 0.0


def fuerza(equipo, condicion):
    if not equipo:
        return 0.0
    pj = max(float(equipo.get("pj") or 0), 1.0)
    cond = equipo.get(condicion, {})
    cond_pj = max(float(cond.get("pj") or 0), 1.0)
    tendencias = equipo.get("tendencias", {})
    ppg = float(equipo.get("pts") or 0) / pj
    dg = float(equipo.get("dg") or 0) / pj
    cond_ppg = float(cond.get("pts") or 0) / cond_pj
    forma_5 = forma_float(tendencias, "forma_5_pts", 5.0)
    forma_10 = forma_float(tendencias, "forma_10_pts", 10.0)
    aceleracion = forma_5 - forma_10
    empates = float(tendencias.get("empates_pct") or 0)
    return (
        ppg * 30
        + dg * 12
        + cond_ppg * 20
        + forma_5 * 14
        + forma_10 * 12
        + aceleracion * 6
        + empates * 0.08
    )


def dinamica_texto(equipo):
    if not equipo:
        return ""
    tendencias = equipo.get("tendencias", {})
    forma_5 = float(tendencias.get("forma_5_pts") or 0)
    forma_10 = float(tendencias.get("forma_10_pts") or 0)
    if forma_10 <= 0:
        return "sin dinámica de 10 jornadas suficiente"
    media_5 = forma_5 / 5.0
    media_10 = forma_10 / 10.0
    if media_5 >= media_10 + 0.35:
        etiqueta = "dinámica positiva reciente"
    elif media_5 <= media_10 - 0.35:
        etiqueta = "dinámica negativa reciente"
    else:
        etiqueta = "dinámica estable"
    return f"forma últimos 5/10: {forma_5:.0f}/{forma_10:.0f} puntos, {etiqueta}"
'''

OLD_LOCAL = '''        razones.append(
            f"{partido.get('local')} llega con {local.get('pts', 0)} puntos, "
            f"{t.get('forma_5_pts', 0)} puntos en los ultimos 5 y "
            f"{t.get('goles_favor_por_partido', 0)} goles a favor por partido."
        )
'''

NEW_LOCAL = '''        razones.append(
            f"{partido.get('local')} llega con {local.get('pts', 0)} puntos, "
            f"{dinamica_texto(local)} y "
            f"{t.get('goles_favor_por_partido', 0)} goles a favor por partido."
        )
'''

OLD_VISITANTE = '''        razones.append(
            f"{partido.get('visitante')} llega con {visitante.get('pts', 0)} puntos, "
            f"{t.get('forma_5_pts', 0)} puntos en los ultimos 5 y "
            f"{t.get('goles_contra_por_partido', 0)} goles encajados por partido."
        )
'''

NEW_VISITANTE = '''        razones.append(
            f"{partido.get('visitante')} llega con {visitante.get('pts', 0)} puntos, "
            f"{dinamica_texto(visitante)} y "
            f"{t.get('goles_contra_por_partido', 0)} goles encajados por partido."
        )
'''


def patch(html):
    if OLD_FUERZA in html:
        html = html.replace(OLD_FUERZA, NEW_FUERZA, 1)
    elif "def dinamica_texto(equipo):" not in html:
        raise SystemExit("No encuentro el bloque fuerza original para añadir forma 10.")

    if OLD_LOCAL in html:
        html = html.replace(OLD_LOCAL, NEW_LOCAL, 1)
    if OLD_VISITANTE in html:
        html = html.replace(OLD_VISITANTE, NEW_VISITANTE, 1)

    return html


def main():
    html = MOTOR.read_text(encoding="utf-8")
    nuevo = patch(html)
    if nuevo != html:
        MOTOR.write_text(nuevo, encoding="utf-8")
        print("Motor actualizado: usa forma de 5 y 10 jornadas y explica dinamica reciente.")
    else:
        print("Motor ya usa forma de 5 y 10 jornadas.")


if __name__ == "__main__":
    main()
