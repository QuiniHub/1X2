from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"


BLOQUE_BUSQUEDA = r'''    function normalizarNombreEquipoCompleto(txt) {
      return repararMojibake(txt)
        .toLowerCase()
        .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
        .replace(/\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el|futbol)\b/g, " ")
        .replace(/[^a-z0-9]+/g, " ")
        .trim()
        .replace(/\s+/g, " ");
    }

    function tokensNombreEquipo(nombre) {
      const limpio = normalizarNombreEquipoCompleto(nombre);
      return limpio ? limpio.split(" ").filter(Boolean) : [];
    }

    function puntuacionNombreEquipo(candidato, objetivo) {
      const base = normalizarNombreEquipoCompleto(candidato || "");
      const buscado = normalizarNombreEquipoCompleto(objetivo || "");
      if (!base || !buscado) return 0;
      if (base === buscado) return 1000;

      const baseTokens = tokensNombreEquipo(candidato);
      const buscadoTokens = tokensNombreEquipo(objetivo);
      const comunes = baseTokens.filter(t => buscadoTokens.includes(t));
      if (!comunes.length) return 0;

      const ambiguos = new Set(["madrid", "barcelona"]);
      if (comunes.length === 1 && ambiguos.has(comunes[0]) && Math.max(baseTokens.length, buscadoTokens.length) > 1) {
        return 0;
      }

      const coberturaBuscado = comunes.length / Math.max(buscadoTokens.length, 1);
      const coberturaBase = comunes.length / Math.max(baseTokens.length, 1);
      let score = comunes.length * 30 + coberturaBuscado * 45 + coberturaBase * 35;

      if (base.includes(buscado) || buscado.includes(base)) score += 20;
      score -= Math.abs(baseTokens.length - buscadoTokens.length) * 8;
      return score;
    }

    function mejorCoincidenciaEquipo(lista, nombre, obtenerNombre = item => item?.equipo || item?.nombre || "") {
      let mejor = null;
      let mejorScore = 0;
      (lista || []).forEach(item => {
        const score = puntuacionNombreEquipo(obtenerNombre(item), nombre);
        if (score > mejorScore) {
          mejor = item;
          mejorScore = score;
        }
      });
      return mejorScore >= 55 ? mejor : null;
    }

    function buscarAnalisisIA(ia, local, visitante) {
      const todos = [
        ...(ia.ligas?.primera?.proximos_partidos || []),
        ...(ia.ligas?.segunda?.proximos_partidos || [])
      ];

      let mejor = null;
      let mejorScore = 0;
      todos.forEach(a => {
        const scoreLocal = puntuacionNombreEquipo(a.local, local);
        const scoreVisitante = puntuacionNombreEquipo(a.visitante, visitante);
        const score = Math.min(scoreLocal, scoreVisitante);
        if (score > mejorScore) {
          mejor = a;
          mejorScore = score;
        }
      });

      return mejorScore >= 55 ? mejor : null;
    }

    function buscarClasificacionEquipo(clasif, nombre) {
      const equipos = [
        ...(clasif.primera || []),
        ...(clasif.segunda || [])
      ];

      return mejorCoincidenciaEquipo(equipos, nombre, e => e.equipo || "");
    }

    function equiposContextoCompetitivo(contexto) {
      return [
        ...((contexto?.primera?.equipos) || []),
        ...((contexto?.segunda?.equipos) || [])
      ];
    }

    function buscarContextoCompetitivo(contexto, nombre) {
      return mejorCoincidenciaEquipo(
        equiposContextoCompetitivo(contexto),
        nombre,
        e => e.equipo || ""
      );
    }
'''

BLOQUE_CONTEXTO_EQUIPOS = r'''    function buscarContextoEquipo(contexto, nombre) {
      const equipos = contexto?.equipos || {};
      const entradas = Object.entries(equipos).map(([equipo, datos]) => ({ equipo, datos }));
      const mejor = mejorCoincidenciaEquipo(entradas, nombre, e => e.equipo || "");
      return mejor ? mejor.datos : null;
    }
'''


def main():
    texto = INDEX.read_text(encoding="utf-8")

    patron_busqueda = re.compile(
        r"    function (?:normalizarNombreEquipoCompleto|buscarAnalisisIA)\([^)]*\) \{.*?\n    function valorMotivacionCompetitiva\(equipo\) \{",
        re.S,
    )
    texto, n_busqueda = patron_busqueda.subn(
        BLOQUE_BUSQUEDA + "\n\n    function valorMotivacionCompetitiva(equipo) {",
        texto,
        count=1,
    )

    patron_contexto = re.compile(
        r"    function buscarContextoEquipo\(contexto, nombre\) \{.*?\n    function normalizarProbabilidades\(p\) \{",
        re.S,
    )
    texto, n_contexto = patron_contexto.subn(
        BLOQUE_CONTEXTO_EQUIPOS + "\n\n    function normalizarProbabilidades(p) {",
        texto,
        count=1,
    )

    if n_busqueda != 1 or n_contexto != 1:
        raise SystemExit(
            f"No se pudo aplicar emparejamiento robusto en index.html: busqueda={n_busqueda}, contexto={n_contexto}"
        )

    INDEX.write_text(texto, encoding="utf-8")
    print("Emparejamiento robusto de equipos aplicado en index.html")


if __name__ == "__main__":
    main()
