from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

LLAMADA_DEBATE = """      const debatePartido = respuestaDebatePartido(q, data);
      if (debatePartido) return debatePartido;
"""

FUNCIONES_DEBATE = r'''
    function datosEquipoCompetitivo(data, nombre) {
      const ligas = ["primera", "segunda"];
      for (const liga of ligas) {
        const competitivo = (data.contextoCompetitivo?.[liga]?.equipos || [])
          .find(e => norm(e.equipo) === norm(nombre) || norm(e.equipo).includes(norm(nombre)) || norm(nombre).includes(norm(e.equipo)));
        const tabla = (data.clasif?.[liga] || [])
          .find(e => norm(e.equipo) === norm(nombre) || norm(e.equipo).includes(norm(nombre)) || norm(nombre).includes(norm(e.equipo)));
        if (competitivo || tabla) return { liga, competitivo: competitivo || {}, tabla: tabla || competitivo || {} };
      }
      return null;
    }

    function equiposMencionados(data, q) {
      const candidatos = [];
      todosEquiposIA(data).forEach(equipo => {
        const nombre = equipo.equipo || "";
        const n = norm(nombre);
        if (!n) return;
        const piezas = n.match(/[a-z0-9]{4,}/g) || [];
        const score = q.includes(n) ? 100 : piezas.filter(p => q.includes(p)).length * 25;
        if (score >= 25 && !candidatos.some(c => norm(c.equipo) === n)) {
          candidatos.push({ ...equipo, score });
        }
      });
      return candidatos.sort((a, b) => b.score - a.score);
    }

    function partidoRelacionadoConEquipos(data, equipos) {
      const partidos = data.prediccion?.partidos || [];
      if (!partidos.length || !equipos.length) return null;
      const claves = equipos.map(e => norm(e.equipo)).filter(Boolean);
      return partidos.find(p => claves.some(clave => norm(p.local).includes(clave) || norm(p.visitante).includes(clave) || clave.includes(norm(p.local)) || clave.includes(norm(p.visitante)))) || null;
    }

    function objetivoPrincipalTexto(datos) {
      const obj = datos?.competitivo?.objetivo_principal || (datos?.competitivo?.objetivos || [])[0] || null;
      if (!obj) return "sin objetivo competitivo claro en memoria";
      const nombre = String(obj.objetivo || "objetivo").replaceAll("_", " ");
      const estado = String(obj.estado || "").replaceAll("_", " ");
      const lectura = obj.lectura || "";
      return `${nombre} (${estado}). ${lectura}`.trim();
    }

    function puntosEquipo(datos) {
      return Number(datos?.competitivo?.puntos ?? datos?.tabla?.puntos ?? datos?.tabla?.pts ?? 0);
    }

    function posicionEquipo(datos) {
      return datos?.competitivo?.posicion ?? datos?.tabla?.posicion ?? "-";
    }

    function formaEquipo(datos) {
      return datos?.competitivo?.tendencias?.forma_5_pts ?? datos?.tabla?.tendencias?.forma_5_pts ?? "-";
    }

    function probTexto(partido) {
      const probs = partido?.probabilidades || {};
      return `1=${probs["1"] ?? "-"}%, X=${probs["X"] ?? "-"}%, 2=${probs["2"] ?? "-"}%`;
    }

    function signoCoberturaRecomendada(partido, equipoObjecion, datosObjecion) {
      const probs = partido?.probabilidades || {};
      const signoBase = partido?.signo_final || partido?.signo_base || "-";
      const esVisitante = norm(partido?.visitante || "").includes(norm(equipoObjecion?.equipo || ""));
      const necesitaPuntuar = String(datosObjecion?.competitivo?.objetivo_principal?.objetivo || "").includes("descenso")
        || String(datosObjecion?.competitivo?.situacion_competitiva || "").includes("descenso")
        || String(datosObjecion?.competitivo?.objetivo_principal?.estado || "").includes("riesgo");

      if (necesitaPuntuar && esVisitante && signoBase === "1") {
        return "Yo mantendria el 1 como favorito, pero tu objecion sube mucho el valor del empate: si se cubre, el primer doble logico es 1X.";
      }
      if (necesitaPuntuar && !esVisitante && signoBase === "2") {
        return "Yo mantendria el 2 como lectura base, pero si ese equipo necesita puntuar, el primer doble logico seria X2.";
      }
      const orden = Object.entries(probs).sort((a, b) => Number(b[1]) - Number(a[1])).map(([s]) => s);
      const doble = orden.slice(0, 2).join("");
      return `Como cobertura prudente, el doble mas natural por probabilidades seria ${doble || "revisar doble"}.`;
    }

    function respuestaDebatePartido(q, data) {
      const tonoDebate = incluye(q, ["no crees", "crees", "tambien", "tambien", "se juega", "necesita", "puntuar", "descenso", "salvar", "bajar", "baja", "doble", "triple", "cambiar", "signo", "analisis"]);
      const mencionados = equiposMencionados(data, q);
      if (!tonoDebate || !mencionados.length) return "";

      const partido = partidoRelacionadoConEquipos(data, mencionados);
      if (!partido) return "";

      const localDatos = datosEquipoCompetitivo(data, partido.local);
      const visitanteDatos = datosEquipoCompetitivo(data, partido.visitante);
      const equipoObjecion = mencionados.find(e => norm(partido.local).includes(norm(e.equipo)) || norm(partido.visitante).includes(norm(e.equipo))) || mencionados[0];
      const datosObjecion = datosEquipoCompetitivo(data, equipoObjecion.equipo);
      const signoBase = partido.signo_final || partido.signo_base || "-";
      const razon = partido.razonamiento || "";
      const yaLoContempla = razon && razon.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").includes(norm(equipoObjecion.equipo).slice(0, 6)) && incluye(norm(razon), ["descenso", "permanencia", "motivacion", "riesgo"]);

      return [
        `Si, buena lectura: ${equipoObjecion.equipo} tambien cuenta aqui.`,
        "",
        `Partido de la jornada ${data.prediccion?.jornada || "-"}: ${partido.num}. ${partido.local} - ${partido.visitante}. Signo actual: ${signoBase}. Probabilidades: ${probTexto(partido)}. Riesgo de sorpresa: ${partido.probabilidad_sorpresa ?? "-"}%.`,
        "",
        `${partido.local}: puesto ${posicionEquipo(localDatos)}, ${puntosEquipo(localDatos)} puntos, forma ultimos 5: ${formaEquipo(localDatos)}. ${objetivoPrincipalTexto(localDatos)}`,
        `${partido.visitante}: puesto ${posicionEquipo(visitanteDatos)}, ${puntosEquipo(visitanteDatos)} puntos, forma ultimos 5: ${formaEquipo(visitanteDatos)}. ${objetivoPrincipalTexto(visitanteDatos)}`,
        "",
        yaLoContempla
          ? `La prediccion si lo tenia en cuenta, pero probablemente lo explicaba demasiado poco. En este caso ${equipoObjecion.equipo} no es un visitante cualquiera: su necesidad competitiva obliga a desconfiar de un fijo limpio.`
          : `Tu objecion anade una pieza importante que la respuesta anterior no estaba destacando con suficiente claridad: ${objetivoPrincipalTexto(datosObjecion)}`,
        signoCoberturaRecomendada(partido, equipoObjecion, datosObjecion),
        "",
        "Conclusion: no cambiaria automaticamente el signo solo por la necesidad, porque tambien pesan forma, goles, casa/fuera y probabilidades. Pero si vas con dobles, este es un partido candidato a cobertura; y si me preguntas antes de validar, te diria que el 1 fijo es mas arriesgado de lo que parece."
      ].join("\n");
    }
'''


def insertar_debate(html):
    if "function respuestaDebatePartido" not in html:
        marcador = "    function respuestaDiagnostico(diagnostico) {"
        if marcador not in html:
            raise SystemExit("No encuentro donde insertar las funciones del asistente.")
        html = html.replace(marcador, FUNCIONES_DEBATE + "\n" + marcador, 1)

    if "const debatePartido = respuestaDebatePartido(q, data);" not in html:
        marcador = "      if (incluye(q, [\"diagnostico\", \"perfecta\", \"perfecto\", \"fiabilidad\", \"autonoma\", \"autonoma\", \"por que no actualiza\", \"porque no actualiza\", \"fallos del sistema\"])) {\n        return respuestaDiagnostico(data.diagnostico);\n      }\n"
        if marcador not in html:
            raise SystemExit("No encuentro el inicio de construirRespuestaIA.")
        html = html.replace(marcador, marcador + LLAMADA_DEBATE, 1)
    return html


def main():
    html = INDEX.read_text(encoding="utf-8")
    actualizado = insertar_debate(html)
    if actualizado != html:
        INDEX.write_text(actualizado, encoding="utf-8")
        print("Asistente IA mejorado con debate de partido y objeciones competitivas.")
    else:
        print("Asistente IA ya tenia debate de partido.")


if __name__ == "__main__":
    main()
