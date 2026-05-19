from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

OLD_PRIMERA = '''      const mejor = evaluadas[0];
      const comparacion = (evaluadasPedidas.length ? evaluadasPedidas : evaluadas.slice(0, 6));
'''

NEW_PRIMERA = '''      const mejorRanking = evaluadas[0];
      const mejorPedida = evaluadasPedidas[0];
      const mejor = mejorPedida || mejorRanking;
      const comparacion = (evaluadasPedidas.length ? evaluadasPedidas : evaluadas.slice(0, 6));
'''

OLD_SEGUNDA = '''      const mejorPedida = evaluadasPedidas[0];
      const decisionPedida = mejorPedida
'''

NEW_SEGUNDA = '''      const decisionPedida = mejorPedida
'''

OLD_TEXTO = '''        `Mi recomendacion global ahora mismo: ${mejor.dobles} dobles y ${mejor.triples} triples${mejor.elige8 ? " + Elige 8" : ""}. Coste: ${eurosEstrategia(mejor.coste.importeTotal)} (${mejor.coste.apuestas} apuestas).`,
'''

NEW_TEXTO = '''        `${pedidas.length ? "Mi recomendacion entre esas opciones" : "Mi recomendacion global ahora mismo"}: ${mejor.dobles} dobles y ${mejor.triples} triples${mejor.elige8 ? " + Elige 8" : ""}. Coste: ${eurosEstrategia(mejor.coste.importeTotal)} (${mejor.coste.apuestas} apuestas).`,
'''


def patch(html):
    if OLD_PRIMERA in html:
        html = html.replace(OLD_PRIMERA, NEW_PRIMERA, 1)
    if OLD_SEGUNDA in html:
        html = html.replace(OLD_SEGUNDA, NEW_SEGUNDA, 1)
    if OLD_TEXTO in html:
        html = html.replace(OLD_TEXTO, NEW_TEXTO, 1)
    return html


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo = patch(html)
    if nuevo != html:
        INDEX.write_text(nuevo, encoding="utf-8")
        print("Estrategia IA afinada: en preguntas A o B recomienda primero entre esas opciones.")
    else:
        print("Recomendacion de estrategia ya afinada.")


if __name__ == "__main__":
    main()
