from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

OLD = '''      const comparaSeparado = dobles.length && triples.length && (q.includes(" o ") || q.includes("frente") || q.includes("compar"));
'''

NEW = '''      const combinaDoblesTriples = q.includes("doblesy") || q.includes("dobley")
        || q.includes("doblesmas") || q.includes("doblemas")
        || q.includes("doblescon") || q.includes("doblecon");
      const comparaSeparado = dobles.length && triples.length && !combinaDoblesTriples;
'''


def patch(html):
    if OLD in html:
        return html.replace(OLD, NEW, 1)
    return html


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo = patch(html)
    if nuevo != html:
        INDEX.write_text(nuevo, encoding="utf-8")
        print("Estrategia IA corregida: distingue '6 dobles o 3 triples' de '6 dobles y 3 triples'.")
    else:
        print("Comparacion de estrategia ya corregida.")


if __name__ == "__main__":
    main()
