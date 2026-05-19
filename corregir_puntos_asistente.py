from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

OLD_FUNC = '''    function puntosEquipo(datos) {
      return Number(datos?.competitivo?.puntos ?? datos?.tabla?.puntos ?? datos?.tabla?.pts ?? 0);
    }
'''

NEW_FUNC = '''    function puntosEquipoCompetitivo(datos) {
      const candidatos = [
        datos?.competitivo?.puntos,
        datos?.competitivo?.pts,
        datos?.tabla?.puntos,
        datos?.tabla?.pts
      ].map(Number).filter(n => Number.isFinite(n) && n > 0);
      return candidatos.length ? candidatos[0] : 0;
    }
'''

OLD_LOCAL = '''${partido.local}: puesto ${posicionEquipo(localDatos)}, ${puntosEquipo(localDatos)} puntos, forma ultimos 5: ${formaEquipo(localDatos)}. ${objetivoPrincipalTexto(localDatos)}'''
NEW_LOCAL = '''${partido.local}: puesto ${posicionEquipo(localDatos)}, ${puntosEquipoCompetitivo(localDatos)} puntos, forma ultimos 5: ${formaEquipo(localDatos)}. ${objetivoPrincipalTexto(localDatos)}'''

OLD_VISITANTE = '''${partido.visitante}: puesto ${posicionEquipo(visitanteDatos)}, ${puntosEquipo(visitanteDatos)} puntos, forma ultimos 5: ${formaEquipo(visitanteDatos)}. ${objetivoPrincipalTexto(visitanteDatos)}'''
NEW_VISITANTE = '''${partido.visitante}: puesto ${posicionEquipo(visitanteDatos)}, ${puntosEquipoCompetitivo(visitanteDatos)} puntos, forma ultimos 5: ${formaEquipo(visitanteDatos)}. ${objetivoPrincipalTexto(visitanteDatos)}'''


def patch(html):
    if OLD_FUNC in html:
        html = html.replace(OLD_FUNC, NEW_FUNC, 1)
    html = html.replace(OLD_LOCAL, NEW_LOCAL)
    html = html.replace(OLD_VISITANTE, NEW_VISITANTE)
    return html


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo = patch(html)
    if nuevo != html:
        INDEX.write_text(nuevo, encoding="utf-8")
        print("Asistente corregido: puntos competitivos sin choque con el generador de boleto.")
    else:
        print("Asistente ya tenia corregida la lectura de puntos competitivos.")


if __name__ == "__main__":
    main()
