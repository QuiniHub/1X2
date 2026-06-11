from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
VERSION_JS = "20260610-pleno-fix"


def aplicar_reemplazos(texto: str) -> str:
    texto = texto.replace("\n        && !activarElige8", "")
    texto = texto.replace("\n        && !activarElige8\n", "\n")
    texto = texto.replace(
        "        && dobles === 0\n        && triples === 0\n        && prediccionBackend.configuracion?.cobertura_auto;",
        "        && ((dobles === 0 && triples === 0) || (dobles === Number(prediccionBackend.resumen?.dobles ?? prediccionBackend.configuracion?.dobles ?? 0) && triples === Number(prediccionBackend.resumen?.triples ?? prediccionBackend.configuracion?.triples ?? 0)))\n        && prediccionBackend.configuracion?.cobertura_auto;",
    )
    texto = texto.replace(
        '<script src="resumen_rapido_metricas.js"></script>',
        f'<script src="resumen_rapido_metricas.js?v={VERSION_JS}"></script>',
    )
    texto = texto.replace(
        'pronostico: pleno.pronostico || pleno.signo_nuestro || pleno.resultado || "1-1",',
        'pronostico: (pleno.pronostico && !["Pendiente", "No jugada", "No validada"].includes(pleno.pronostico)) ? pleno.pronostico : "1-1",',
    )
    return texto


def main() -> None:
    if not INDEX.exists():
        raise SystemExit("No existe index.html")
    original = INDEX.read_text(encoding="utf-8")
    actualizado = aplicar_reemplazos(original)
    if actualizado != original:
        INDEX.write_text(actualizado, encoding="utf-8")
        print("Web estabilizada: Elige 8, Pleno al 15 y cache JS.")
    else:
        print("Web ya estaba estabilizada.")


if __name__ == "__main__":
    main()
