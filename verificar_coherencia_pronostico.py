import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "memoria_ia"
INDEX = ROOT / "index.html"
MOTOR = ROOT / "motor_prediccion_quiniela.py"

REGLAS_INDEX = {
    "normalizacion_competitiva": "function normalizarCompetitivoTextoBoleto",
    "patrones_en_probabilidades": "probs = ajustarPorPatronesAprendidosWeb(probs, contextoCompetitivoLocal, contextoCompetitivoVisitante, patronesCompetitivos);",
    "riesgo_real_no_bonus_crudo": "riesgo_necesidad: riesgoNecesidad",
    "prioridad_cobertura_web": "prioridadCoberturaAnalisis(b) - prioridadCoberturaAnalisis(a)",
}

REGLAS_MOTOR = {
    "prioridad_cobertura_motor": "def prioridad_cobertura",
    "riesgo_real_motor": "def riesgo_necesidad_real",
    "choque_necesidades": "Choque de necesidades vivas",
}

PROHIBIDOS_INDEX = {
    "riesgo_por_bonus_crudo": "riesgo_necesidad: bonusCompetitivo >= 18",
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
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "estado": "ok" if not fallos else "fallo",
        "fallos": fallos,
        "lectura": "El boleto debe usar la misma capa competitiva que explica el analisis antes de repartir fijos, dobles y triples.",
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
