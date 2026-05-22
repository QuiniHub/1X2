import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MEM = ROOT / "data" / "memoria_ia"
CONTEXTO = MEM / "contexto_competitivo.json"
SALIDA = MEM / "fuente_verdad_competitiva.json"


def cargar(path):
    if not path.exists():
        raise SystemExit(f"Falta archivo requerido: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def guardar(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def limpiar_equipo(equipo):
    principal = equipo.get("objetivo_principal") or {}
    objetivos = equipo.get("objetivos") or []
    if equipo.get("override_oficial_jornada"):
        objetivos = [principal]

    return {
        "equipo": equipo.get("equipo"),
        "liga": equipo.get("liga"),
        "posicion": equipo.get("posicion"),
        "puntos": equipo.get("puntos"),
        "puntos_en_juego": equipo.get("puntos_en_juego"),
        "maximo_puntos": equipo.get("maximo_puntos"),
        "motivacion_competitiva": equipo.get("motivacion_competitiva", "baja"),
        "motivacion": equipo.get("motivacion", equipo.get("motivacion_competitiva", "baja")),
        "situacion_competitiva": equipo.get("situacion_competitiva"),
        "lectura_resumen": equipo.get("lectura_resumen"),
        "objetivo_principal": principal,
        "objetivos": objetivos,
        "objetivos_vivos": equipo.get("objetivos_vivos") or [],
        "override_oficial_jornada": bool(equipo.get("override_oficial_jornada")),
    }


def construir():
    contexto = cargar(CONTEXTO)
    equipos = {}
    for liga in ("primera", "segunda"):
        for equipo in (contexto.get(liga) or {}).get("equipos", []):
            limpio = limpiar_equipo({**equipo, "liga": liga})
            equipos[limpio["equipo"]] = limpio

    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "fuente": "data/memoria_ia/contexto_competitivo.json",
        "descripcion": "Fuente unica de verdad competitiva para motor, quiniela, analisis y asistentes.",
        "equipos": equipos,
    }
    guardar(SALIDA, salida)
    print(SALIDA)


if __name__ == "__main__":
    construir()
