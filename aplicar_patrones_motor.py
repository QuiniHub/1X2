from pathlib import Path


ROOT = Path(__file__).resolve().parent
MOTOR = ROOT / "motor_prediccion_quiniela.py"

HELPERS = r'''

def texto_competitivo_motor(equipo):
    objetivos = " ".join(
        f"{o.get('objetivo', '')} {o.get('estado', '')} {o.get('lectura', '')}"
        for o in (equipo or {}).get("objetivos", [])
    )
    return f"{objetivos} {(equipo or {}).get('situacion_competitiva', '')} {(equipo or {}).get('motivacion_competitiva', '')}".lower()


def objetivo_cerrado_motor(equipo):
    if not equipo:
        return False
    if equipo.get("objetivos_vivos"):
        return False
    texto = texto_competitivo_motor(equipo)
    return any(
        clave in texto
        for clave in (
            "asegurado_matematicamente",
            "campeon_matematico",
            "salvado_matematicamente",
            "descendido_matematicamente",
            "sin_opciones_matematicas",
            "no se juega nada",
        )
    )


def necesidad_viva_motor(equipo):
    if not equipo or objetivo_cerrado_motor(equipo):
        return False
    texto = texto_competitivo_motor(equipo)
    motivacion = str(equipo.get("motivacion_competitiva") or equipo.get("motivacion") or "").lower()
    return bool(equipo.get("objetivos_vivos")) or motivacion in {"alta", "maxima", "máxima"} or any(
        clave in texto
        for clave in (
            "riesgo_descenso",
            "en_descenso_con_opciones",
            "permanencia_por_cerrar",
            "defiende_plaza",
            "aspira_matematicamente",
            "aspira_por_desempate",
            "descenso",
            "permanencia",
            "playoff",
            "ascenso",
            "conference",
            "europa",
            "champions",
        )
    )


def descenso_vivo_motor(equipo):
    return necesidad_viva_motor(equipo) and any(c in texto_competitivo_motor(equipo) for c in ("descenso", "permanencia", "salvarse"))


def tasa_patron(patrones, clave):
    try:
        return float((patrones.get("patrones") or {}).get(clave, {}).get("tasa_sorpresa") or 0)
    except Exception:
        return 0.0


def ajustar_por_patrones_aprendidos(probs, patrones, local_comp, visitante_comp):
    probs = dict(probs)
    riesgo_extra = 0.0
    lecturas = []
    local_cerrado = objetivo_cerrado_motor(local_comp)
    visitante_cerrado = objetivo_cerrado_motor(visitante_comp)
    local_necesita = necesidad_viva_motor(local_comp)
    visitante_necesita = necesidad_viva_motor(visitante_comp)
    local_descenso = descenso_vivo_motor(local_comp)
    visitante_descenso = descenso_vivo_motor(visitante_comp)
    top = signo_top(probs)

    if visitante_cerrado and local_necesita:
        tasa = tasa_patron(patrones, "necesitado_local_vs_visitante_objetivo_cerrado")
        probs["1"] += 5 + tasa * 0.08
        probs["X"] += 5 + tasa * 0.06
        probs["2"] -= 4
        riesgo_extra += 10 + tasa * 0.20
        lecturas.append(f"Aprendizaje competitivo: cuando el local necesita y el visitante tiene objetivo cerrado, el fijo visitante se rompe con frecuencia ({tasa:.1f}% en la memoria).")

    if local_cerrado and visitante_necesita:
        tasa = tasa_patron(patrones, "visitante_necesitado_vs_local_objetivo_cerrado")
        probs["2"] += 5 + tasa * 0.08
        probs["X"] += 5 + tasa * 0.06
        probs["1"] -= 4
        riesgo_extra += 10 + tasa * 0.20
        lecturas.append(f"Aprendizaje competitivo: cuando el visitante necesita y el local tiene objetivo cerrado, el 1 fijo no debe ser tranquilo ({tasa:.1f}% de rupturas en memoria).")

    if visitante_descenso and top == "1":
        tasa = tasa_patron(patrones, "visitante_descenso_vs_local_favorito")
        probs["X"] += 9 + tasa * 0.07
        probs["2"] += 9 + tasa * 0.07
        probs["1"] -= 8
        riesgo_extra += 24 + tasa * 0.25
        lecturas.append(f"Aprendizaje de descenso: un visitante que se juega permanencia contra favorito local debe subir a zona de cobertura; patron historico {tasa:.1f}%.")

    if local_descenso and top == "2":
        tasa = tasa_patron(patrones, "local_descenso_vs_visitante_favorito")
        probs["X"] += 9 + tasa * 0.07
        probs["1"] += 9 + tasa * 0.07
        probs["2"] -= 8
        riesgo_extra += 24 + tasa * 0.25
        lecturas.append(f"Aprendizaje de descenso: un local que se juega permanencia contra favorito visitante debe subir a zona de cobertura; patron historico {tasa:.1f}%.")

    if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
        tasa = tasa_patron(patrones, "equipo_necesitado_vs_equipo_sin_objetivo")
        riesgo_extra += 8 + tasa * 0.15
        lecturas.append(f"Patron general aprendido: necesidad contra objetivo cerrado aumenta sorpresa y exige desconfiar del fijo limpio ({tasa:.1f}%).")

    return normalizar_probs(probs), round(riesgo_extra, 2), lecturas
'''


def replace_once(html, old, new, desc):
    if new.strip() in html:
        return html
    if old not in html:
        raise SystemExit(f"No encuentro bloque para {desc}.")
    return html.replace(old, new, 1)


def main():
    html = MOTOR.read_text(encoding="utf-8")

    if "PATRONES_COMPETITIVOS" not in html:
        html = html.replace(
            'CONTEXTO_COMPETITIVO = DATA / "memoria_ia" / "contexto_competitivo.json"\n',
            'CONTEXTO_COMPETITIVO = DATA / "memoria_ia" / "contexto_competitivo.json"\nPATRONES_COMPETITIVOS = DATA / "memoria_ia" / "patrones_competitivos.json"\n',
            1,
        )

    if "def ajustar_por_patrones_aprendidos" not in html:
        marker = '\ndef signo_top(probs):\n'
        if marker not in html:
            raise SystemExit("No encuentro signo_top para insertar patrones.")
        html = html.replace(marker, HELPERS + marker, 1)

    if "patrones_competitivos = cargar_json(PATRONES_COMPETITIVOS" not in html:
        html = html.replace(
            '    contexto_competitivo = cargar_json(CONTEXTO_COMPETITIVO, {})\n',
            '    contexto_competitivo = cargar_json(CONTEXTO_COMPETITIVO, {})\n    patrones_competitivos = cargar_json(PATRONES_COMPETITIVOS, {})\n',
            1,
        )

    old = '''        probs, riesgo_motivacion, lecturas_motivacion = ajustar_por_motivacion(probs, local_comp, visitante_comp)
        inc = incertidumbre(probs, local, visitante, diff, riesgo_contexto + riesgo_motivacion)
'''
    new = '''        probs, riesgo_motivacion, lecturas_motivacion = ajustar_por_motivacion(probs, local_comp, visitante_comp)
        probs, riesgo_patrones, lecturas_patrones = ajustar_por_patrones_aprendidos(
            probs, patrones_competitivos, local_comp, visitante_comp
        )
        lecturas_motivacion.extend(lecturas_patrones)
        inc = incertidumbre(probs, local, visitante, diff, riesgo_contexto + riesgo_motivacion + riesgo_patrones)
'''
    if "riesgo_patrones" not in html:
        html = replace_once(html, old, new, "aplicar patrones en predecir")

    MOTOR.write_text(html, encoding="utf-8")
    print("Motor reforzado con patrones competitivos aprendidos.")


if __name__ == "__main__":
    main()
