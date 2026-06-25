from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

REEMPLAZOS = [
    (
        "const items = a.partidos || a.diario || a.detalle || a.aprendizajes || [];",
        "const items = a.entradas || a.partidos || a.diario || a.detalle || a.aprendizajes || [];",
    ),
    (
        "const ok = it.acierto === true || it.resultado_aprendizaje === 'acierto';",
        "const ok = it.acierto === true || it.acertado === true || it.resultado_aprendizaje === 'acierto' || it.categoria_fallo === 'acierto';",
    ),
    (
        "<span>Predijo: <b>${fmt(it.predicho || it.prediccion || it.signo_predicho)}</b> · Pasó: <b>${fmt(it.real || it.resultado || it.signo_real)}</b></span>",
        "<span>Predijo: <b>${fmt(it.predicho || it.pronostico_jugado || it.prediccion?.signo_final || it.prediccion || it.signo_predicho)}</b> · Pasó: <b>${fmt(it.real || it.resultado_real?.signo_oficial || it.signo_real || it.resultado)}</b></span>",
    ),
    (
        "<span class=\"result\">${ok ? 'Acierto' : 'Fallo'} · ${fmt(it.aprendizaje || it.lectura || it.que_aprende, 'Ajusta pesos y señales para futuras jornadas.')}</span>",
        "<span class=\"result\">${ok ? 'Acierto' : 'Fallo'} · ${fmt(it.ajuste_recomendado || it.explicacion || it.aprendizaje || it.lectura || it.que_aprende, 'Ajusta pesos y señales para futuras jornadas.')}</span>",
    ),
    (
        "const totalCobrado = rows.reduce((s, r) => s + Number(r.premio || r.premio_euros || r.cobrado || 0), 0);",
        "const totalCobrado = rows.reduce((s, r) => s + Number(r.premio_eur ?? r.premio ?? r.premio_euros ?? r.cobrado ?? 0), 0);",
    ),
    (
        "metric('Premios conseguidos', rows.filter(r => Number(r.premio || r.premio_euros || r.cobrado || 0) > 0).length),",
        "metric('Premios conseguidos', rows.filter(r => Number(r.premio_eur ?? r.premio ?? r.premio_euros ?? r.cobrado ?? 0) > 0).length),",
    ),
    (
        "const premio = Number(r.premio || r.premio_euros || r.cobrado || 0);",
        "const premio = Number(r.premio_eur ?? r.premio ?? r.premio_euros ?? r.cobrado ?? 0);",
    ),
    (
        "const acumulado = rows.slice(0, i + 1).reduce((s, x) => s + Number(x.premio || x.premio_euros || x.cobrado || 0), 0);",
        "const acumulado = rows.slice(0, i + 1).reduce((s, x) => s + Number(x.premio_eur ?? x.premio ?? x.premio_euros ?? x.cobrado ?? 0), 0);",
    ),
    (
        "fmt(r.estado || (premio > 0 ? 'premio' : 'sin premio'))",
        "fmt(r.estado || r.fuente_premio || (premio > 0 ? 'premio' : 'sin premio'))",
    ),
    (
        "getJson('data/memoria_ia/historial_quinielas.json', await getJson('data/memoria_ia/premios_historico.json'))",
        "getJson('data/premios/historial_premios.json')",
    ),
]


def main():
    html = INDEX.read_text(encoding="utf-8")
    original = html
    aplicados = 0
    ya_aplicados = 0

    for anterior, nuevo in REEMPLAZOS:
        if anterior in html:
            html = html.replace(anterior, nuevo)
            aplicados += 1
        elif nuevo in html:
            ya_aplicados += 1
        else:
            print(f"AVISO: no se encontro patron esperado en index.html: {anterior[:90]}")

    if html != original:
        INDEX.write_text(html, encoding="utf-8")
        print(f"Lectura de datos web corregida en index.html: {aplicados} cambio(s).")
    else:
        print(f"Lectura de datos web ya estaba corregida o sin cambios. Patrones ya aplicados: {ya_aplicados}.")


if __name__ == "__main__":
    main()
