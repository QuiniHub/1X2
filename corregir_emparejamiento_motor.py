from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
MOTOR = ROOT / "motor_prediccion_quiniela.py"


BLOQUE_MOTOR = r'''def puntuacion_nombre_equipo(candidato, objetivo):
    base = normalizar(candidato)
    buscado = normalizar(objetivo)
    if not base or not buscado:
        return 0
    if base == buscado:
        return 1000

    base_tokens = base.split()
    buscado_tokens = buscado.split()
    comunes = [token for token in base_tokens if token in buscado_tokens]
    if not comunes:
        return 0

    ambiguos = {"madrid", "barcelona"}
    if len(comunes) == 1 and comunes[0] in ambiguos and max(len(base_tokens), len(buscado_tokens)) > 1:
        return 0

    cobertura_buscado = len(comunes) / max(len(buscado_tokens), 1)
    cobertura_base = len(comunes) / max(len(base_tokens), 1)
    score = len(comunes) * 30 + cobertura_buscado * 45 + cobertura_base * 35
    if base in buscado or buscado in base:
        score += 20
    score -= abs(len(base_tokens) - len(buscado_tokens)) * 8
    return score


def mejor_coincidencia_equipo(items, nombre, getter):
    mejor = None
    mejor_score = 0
    for item in items or []:
        score = puntuacion_nombre_equipo(getter(item), nombre)
        if score > mejor_score:
            mejor = item
            mejor_score = score
    return mejor if mejor_score >= 55 else None


def buscar_equipo(memoria, nombre):
    return mejor_coincidencia_equipo(
        equipos_memoria(memoria),
        nombre,
        lambda equipo: equipo.get("equipo", ""),
    )


def equipos_contexto(contexto):
    return contexto.get("equipos", {})


def buscar_contexto_equipo(contexto, nombre):
    entradas = [
        {"equipo": equipo, "datos": datos}
        for equipo, datos in equipos_contexto(contexto).items()
    ]
    mejor = mejor_coincidencia_equipo(entradas, nombre, lambda item: item.get("equipo", ""))
    return mejor.get("datos") if mejor else None


def equipos_contexto_competitivo(contexto):
    equipos = []
    for liga in ("primera", "segunda"):
        for equipo in (contexto.get(liga) or {}).get("equipos", []):
            equipos.append({**equipo, "liga": liga})
    return equipos


def buscar_contexto_competitivo(contexto, nombre):
    return mejor_coincidencia_equipo(
        equipos_contexto_competitivo(contexto),
        nombre,
        lambda equipo: equipo.get("equipo", ""),
    )
'''


def main():
    texto = MOTOR.read_text(encoding="utf-8")
    patron = re.compile(
        r"def (?:puntuacion_nombre_equipo|buscar_equipo)\([^)]*\):.*?\n\ndef valor_motivacion\(equipo\):",
        re.S,
    )
    texto, n = patron.subn(BLOQUE_MOTOR + "\n\ndef valor_motivacion(equipo):", texto, count=1)
    if n != 1:
        raise SystemExit(f"No se pudo aplicar emparejamiento robusto en motor: cambios={n}")
    MOTOR.write_text(texto, encoding="utf-8")
    print("Emparejamiento robusto de equipos aplicado en motor_prediccion_quiniela.py")


if __name__ == "__main__":
    main()
