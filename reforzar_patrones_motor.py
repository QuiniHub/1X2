from pathlib import Path


ROOT = Path(__file__).resolve().parent
MOTOR = ROOT / "motor_prediccion_quiniela.py"

OLD_VISITANTE = '''    if visitante_descenso and top == "1":
        tasa = tasa_patron(patrones, "visitante_descenso_vs_local_favorito")
        probs["X"] += 9 + tasa * 0.07
        probs["2"] += 9 + tasa * 0.07
        probs["1"] -= 8
        riesgo_extra += 24 + tasa * 0.25
        lecturas.append(f"Aprendizaje de descenso: un visitante que se juega permanencia contra favorito local debe subir a zona de cobertura; patron historico {tasa:.1f}%.")
'''

NEW_VISITANTE = '''    if visitante_descenso and top == "1":
        tasa = tasa_patron(patrones, "visitante_descenso_vs_local_favorito")
        probs["X"] += 12 + tasa * 0.10
        probs["2"] += 14 + tasa * 0.12
        probs["1"] -= 10
        riesgo_extra += 75 + tasa * 0.40
        lecturas.append(f"Aprendizaje de descenso: un visitante que se juega permanencia contra favorito local debe subir a zona prioritaria de cobertura; patron historico {tasa:.1f}%.")
'''

OLD_LOCAL = '''    if local_descenso and top == "2":
        tasa = tasa_patron(patrones, "local_descenso_vs_visitante_favorito")
        probs["X"] += 9 + tasa * 0.07
        probs["1"] += 9 + tasa * 0.07
        probs["2"] -= 8
        riesgo_extra += 24 + tasa * 0.25
        lecturas.append(f"Aprendizaje de descenso: un local que se juega permanencia contra favorito visitante debe subir a zona de cobertura; patron historico {tasa:.1f}%.")
'''

NEW_LOCAL = '''    if local_descenso and top == "2":
        tasa = tasa_patron(patrones, "local_descenso_vs_visitante_favorito")
        probs["X"] += 12 + tasa * 0.10
        probs["1"] += 14 + tasa * 0.12
        probs["2"] -= 10
        riesgo_extra += 75 + tasa * 0.40
        lecturas.append(f"Aprendizaje de descenso: un local que se juega permanencia contra favorito visitante debe subir a zona prioritaria de cobertura; patron historico {tasa:.1f}%.")
'''


def main():
    html = MOTOR.read_text(encoding="utf-8")
    cambiado = False
    if OLD_VISITANTE in html:
        html = html.replace(OLD_VISITANTE, NEW_VISITANTE, 1)
        cambiado = True
    if OLD_LOCAL in html:
        html = html.replace(OLD_LOCAL, NEW_LOCAL, 1)
        cambiado = True
    if "zona prioritaria de cobertura" in html:
        MOTOR.write_text(html, encoding="utf-8")
        print("Patrones de descenso reforzados en motor.")
        return
    if not cambiado:
        raise SystemExit("No encuentro bloques antiguos de patrones de descenso en motor.")
    MOTOR.write_text(html, encoding="utf-8")
    print("Patrones de descenso reforzados en motor.")


if __name__ == "__main__":
    main()
