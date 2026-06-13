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


def combinar_alertas(*listas_alertas):
    combinadas = []
    vistas = set()
    for alertas in listas_alertas:
        for alerta in alertas or []:
            clave = (
                str(alerta.get("nivel", "")),
                str(alerta.get("titulo", "")),
                str(alerta.get("detalle", "")),
            )
            if clave in vistas:
                continue
            vistas.add(clave)
            combinadas.append(alerta)
    return combinadas


def estado_desde_alertas(alertas):
    niveles = {str(alerta.get("nivel", "")).lower() for alerta in alertas or []}
    if "critica" in niveles:
        return "critico_actualizacion", 45
    if "alta" in niveles:
        return "requiere_revision_datos", 70
    if "media" in niveles:
        return "operativo_con_avisos", 82
    if "baja" in niveles:
        return "operativo_con_avisos", 92
    return "operativo", 100


def estado_final(control, diagnostico):
    alertas = combinar_alertas(control.get("alertas", []), diagnostico.get("alertas", []))
    estado_control, score_control = estado_desde_control(control)
    estado_alertas, score_alertas = estado_desde_alertas(alertas)
    try:
        score_diagnostico = int(diagnostico.get("score_salud", score_control) or score_control)
    except (TypeError, ValueError):
        score_diagnostico = score_control

    score = min(score_control, score_alertas, score_diagnostico)
    if score <= 45 or estado_control == "critico_actualizacion" or estado_alertas == "critico_actualizacion":
        estado = "critico_actualizacion"
    elif score <= 70 or estado_control == "requiere_revision_datos" or estado_alertas == "requiere_revision_datos":
        estado = "requiere_revision_datos"
    elif score < 100 or alertas:
        estado = "operativo_con_avisos"
    else:
        estado = "operativo"
    return estado, score, alertas


def main():
    control = cargar_json(DATA / "control_calidad_actualizacion.json", {})
    if not control:
        print("No existe control de calidad; no se normaliza diagnostico.")
        return

    diagnostico = cargar_json(DATA / "diagnostico_sistema.json", {})
    estado, score, alertas = estado_final(control, diagnostico)
    diagnostico["estado"] = estado
    diagnostico["score_salud"] = score
    diagnostico["generado_en"] = control.get("generado_en")
    diagnostico["control_calidad"] = control
    diagnostico["prediccion"] = control.get("prediccion", {})
    diagnostico["jornadas_control"] = control.get("jornadas", {})
    diagnostico["clasificacion_control"] = control.get("clasificacion", {})
    diagnostico["contexto_competitivo_control"] = control.get("contexto_competitivo", {})
    diagnostico["alertas"] = alertas

    guardar_json(DATA / "diagnostico_sistema.json", diagnostico)
    guardar_json(MEMORIA / "diagnostico_sistema.json", diagnostico)
    print("Diagnostico normalizado desde control de calidad.")


if __name__ == "__main__":
    main()
