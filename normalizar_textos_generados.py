import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RUTAS_JSON = [
    ROOT / "data" / "predicciones",
    ROOT / "data" / "memoria_ia",
    ROOT / "data" / "historial_quinielas.json",
    ROOT / "data" / "quinielas_jugadas.json",
]


def reparar_mojibake_texto(texto):
    texto = str(texto)
    if not any(marca in texto for marca in ("Ã", "Â", "â", "�")):
        return texto
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "�" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def normalizar_valor(valor):
    if isinstance(valor, str):
        return reparar_mojibake_texto(valor)
    if isinstance(valor, list):
        return [normalizar_valor(item) for item in valor]
    if isinstance(valor, dict):
        return {normalizar_valor(k) if isinstance(k, str) else k: normalizar_valor(v) for k, v in valor.items()}
    return valor


def iter_json_files():
    vistos = set()
    for ruta in RUTAS_JSON:
        if ruta.is_dir():
            candidatos = sorted(ruta.rglob("*.json"))
        elif ruta.is_file():
            candidatos = [ruta]
        else:
            candidatos = []
        for candidato in candidatos:
            if candidato in vistos:
                continue
            vistos.add(candidato)
            yield candidato


def normalizar_archivo(path):
    try:
        original = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"Saltado JSON no valido: {path}")
        return False

    normalizado = normalizar_valor(original)
    if normalizado == original:
        return False

    path.write_text(json.dumps(normalizado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Texto normalizado: {path}")
    return True


def main():
    cambios = sum(1 for path in iter_json_files() if normalizar_archivo(path))
    print(f"Normalizacion de textos generados completada. Archivos modificados: {cambios}")


if __name__ == "__main__":
    main()
