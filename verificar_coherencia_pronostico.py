import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "memoria_ia"
INDEX = ROOT / "index.html"
MOTOR = ROOT / "motor_prediccion_quiniela.py"

REGLAS_INDEX = {
    "version_web_coherente": "coherencia-pronostico-analisis-2026-05-20",
    "patrones_en_probabilidades": "function ajustarPorPatronesAprendidosWeb",
    "probabilidades_antes_del_signo": "probs = ajustarPorPatronesAprendidosWeb(probs, compL, compV);",
    "riesgo_real_no_bonus_crudo": "riesgo_necesidad: necesidadViva(compL) || necesidadViva(compV) || descensoVivo(compL) || descensoVivo(compV)",
    "prioridad_cobertura_web": "prioridadCoberturaAnalisis(b) - prioridadCoberturaAnalisis(a)",
    "texto_fijo_limitado": "queda como signo base solo por limite de dobles/triples",
}

REGLAS_MOTOR = {
    "motor_presente": "def ajustar_por_patrones_aprendidos",
    "memoria_competitiva": "Patron general aprendido",
}

PROHIBIDOS_INDEX = {
    "riesgo_por_bonus_crudo": "riesgo_necesidad: bonusCompetitivo >= 18",
    "orden_antiguo_por_incertidumbre": "sort((a, b) => b.incertidumbre - a.incertidumbre)",
}


def comprobar(nombre, contenido, obligatorios, prohibidos=None):
    fallos = []
    for regla, texto in obligatorios.items():
        if texto not in contenido:
            fallos.append({
                "archivo": nombre,
                "regla": regla,
                "detalle": f"Falta la marca obligatoria: {texto}",
            })
    for regla, texto in (prohibidos or {}).items():
        if texto in contenido:
            fallos.append({
                "archivo": nombre,
                "regla": regla,
                "detalle": f"Sigue apareciendo la marca prohibida: {texto}",
            })
    return fallos


def main():
    index = INDEX.read_text(encoding="utf-8")
    motor = MOTOR.read_text(encoding="utf-8")

    fallos = []
    fallos.extend(comprobar("index.html", index, REGLAS_INDEX, PROHIBIDOS_INDEX))
    fallos.extend(comprobar("motor_prediccion_quiniela.py", motor, REGLAS_MOTOR))

    salida = {
        "version": "2.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "estado": "ok" if not fallos else "fallo",
        "fallos": fallos,
        "lectura": "El boleto y el analisis se generan desde la misma capa de probabilidades, necesidad viva y prioridad de cobertura.",
    }
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "verificacion_pronostico_analisis.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if fallos:
        for fallo in fallos:
            print(f"[{fallo['archivo']}] {fallo['regla']}: {fallo['detalle']}")
        raise SystemExit("La coherencia entre pronostico y analisis no esta garantizada.")

    print("Coherencia pronostico/analisis OK.")


if __name__ == "__main__":
    main()
