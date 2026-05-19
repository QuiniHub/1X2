import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def estado_desde_control(control):
    estado = control.get("estado")
    if estado == "critico":
        return "critico_actualizacion", 45
    if estado == "revisar":
        return "requiere_revision_datos", 70
    if estado == "operativo_con_avisos":
        return "operativo_con_avisos", 82
    return "operativo", 100


def main():
    control = cargar_json(DATA / "control_calidad_actualizacion.json", {})
    if not control:
        print("No existe control de calidad; no se normaliza diagnostico.")
        return

    diagnostico = cargar_json(DATA / "diagnostico_sistema.json", {})
    estado, score = estado_desde_control(control)
    diagnostico["estado"] = estado
    diagnostico["score_salud"] = score
    diagnostico["generado_en"] = control.get("generado_en")
    diagnostico["control_calidad"] = control
    diagnostico["prediccion"] = control.get("prediccion", {})
    diagnostico["jornadas_control"] = control.get("jornadas", {})
    diagnostico["clasificacion_control"] = control.get("clasificacion", {})
    diagnostico["contexto_competitivo_control"] = control.get("contexto_competitivo", {})
    diagnostico["alertas"] = control.get("alertas", [])

    guardar_json(DATA / "diagnostico_sistema.json", diagnostico)
    guardar_json(MEMORIA / "diagnostico_sistema.json", diagnostico)
    print("Diagnostico normalizado desde control de calidad.")


if __name__ == "__main__":
    main()
