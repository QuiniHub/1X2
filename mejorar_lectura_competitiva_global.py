from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"

HELPER_ROL = r'''
    function rolEquipoPartido(partido, equipo) {
      const nombre = norm(equipo?.equipo || "");
      if (!nombre) return "equipo";
      if (norm(partido?.visitante || "").includes(nombre) || nombre.includes(norm(partido?.visitante || ""))) return "visitante";
      if (norm(partido?.local || "").includes(nombre) || nombre.includes(norm(partido?.local || ""))) return "local";
      return "equipo";
    }
'''

FUNCION_GLOBAL = r'''
    function estadoLegibleCompetitivo(equipo) {
      const obj = equipo?.objetivo_principal || (equipo?.objetivos || [])[0] || {};
      const nombre = String(obj.objetivo || "situacion").replaceAll("_", " ");
      const estado = String(obj.estado || "sin estado").replaceAll("_", " ");
      const lectura = obj.lectura || equipo?.lectura_resumen || "Sin lectura guardada.";
      return `${nombre} (${estado}). ${lectura}`;
    }

    function equipoTieneNecesidadCompetitiva(equipo) {
      const vivos = equipo?.objetivos_vivos || [];
      const texto = `${equipo?.motivacion_competitiva || ""} ${equipo?.situacion_competitiva || ""} ${estadoLegibleCompetitivo(equipo)}`.toLowerCase();
      return vivos.length > 0
        || texto.includes("defiende")
        || texto.includes("aspira")
        || texto.includes("riesgo")
        || texto.includes("descenso")
        || texto.includes("permanencia por cerrar")
        || texto.includes("playoff")
        || texto.includes("ascenso directo");
    }

    function equipoSinObjetivoVivo(equipo) {
      const vivos = equipo?.objetivos_vivos || [];
      const texto = `${equipo?.motivacion_competitiva || ""} ${equipo?.situacion_competitiva || ""} ${estadoLegibleCompetitivo(equipo)}`.toLowerCase();
      return !vivos.length && (
        texto.includes("asegurado matematicamente")
        || texto.includes("campeon matematico")
        || texto.includes("salvado matematicamente")
        || texto.includes("descendido matematicamente")
        || texto.includes("sin opciones matematicas")
        || texto.includes("no se juega nada")
      );
    }

    function lineaCompetitivaEquipo(equipo) {
      const motivacion = equipo?.motivacion_competitiva || equipo?.motivacion || "-";
      const puntos = equipo?.puntos ?? equipo?.pts ?? "-";
      const pj = equipo?.pj ?? "-";
      const restantes = equipo?.partidos_restantes ?? "-";
      return `- ${equipo.equipo}: ${puntos} pts, PJ ${pj}, quedan ${restantes}. Motivacion ${motivacion}. ${estadoLegibleCompetitivo(equipo)}`;
    }

    function respuestaLecturaCompetitivaGlobal(q, data) {
      const pregunta = incluye(q, ["se juegan", "juega algo", "no se juega", "no se juegan", "necesidad", "necesitan", "necesita", "objetivos vivos", "motivacion competitiva", "matices", "puntos en juego", "todos los equipos"]);
      if (!pregunta) return "";
      if (equiposMencionados(data, q).length) return "";

      const ligaPedida = ligaDesdePregunta(q);
      const ligas = ligaPedida ? [ligaPedida] : ["primera", "segunda"];
      const bloques = [];

      ligas.forEach(liga => {
        const equipos = (data.contextoCompetitivo?.[liga]?.equipos || []).slice();
        if (!equipos.length) return;
        const nombreLiga = liga === "primera" ? "1a Division" : "2a Division";
        const conNecesidad = equipos.filter(equipoTieneNecesidadCompetitiva)
          .sort((a, b) => (b.objetivos_vivos || []).length - (a.objetivos_vivos || []).length || (a.posicion || 99) - (b.posicion || 99));
        const sinObjetivo = equipos.filter(equipoSinObjetivoVivo)
          .sort((a, b) => (a.posicion || 99) - (b.posicion || 99));

        bloques.push(`${nombreLiga}:`);
        bloques.push("Equipos con algo real en juego ahora mismo:");
        bloques.push(...(conNecesidad.length ? conNecesidad.map(lineaCompetitivaEquipo) : ["- No detecto objetivos vivos claros con la clasificacion actual."]));
        bloques.push("");
        bloques.push("Equipos con objetivo principal cerrado o sin opciones matematicas:");
        bloques.push(...(sinObjetivo.length ? sinObjetivo.map(lineaCompetitivaEquipo) : ["- No detecto equipos completamente cerrados."]));
        bloques.push("");
      });

      if (!bloques.length) return "No tengo cargado el contexto competitivo de 1a y 2a. En la siguiente actualizacion debe regenerarse desde las clasificaciones.";
      return [
        "Si. Esta lectura debe hacerse para todos los equipos de 1a y 2a, no solo para los ejemplos que estamos comentando.",
        "La IA compara puntos actuales, partidos restantes, puntos en juego, objetivos vivos y objetivos ya cerrados antes de valorar fijo, doble o triple.",
        "",
        ...bloques,
        "Regla practica: un equipo con objetivo vivo no gana automaticamente, pero obliga a desconfiar de fijos demasiado limpios; un equipo con objetivo cerrado no pierde automaticamente, pero su urgencia competitiva pesa menos."
      ].join("\n");
    }
'''


def patch(html):
    if "function rolEquipoPartido" not in html:
        marcador = "    function signoCoberturaRecomendada(partido, equipoObjecion, datosObjecion) {"
        if marcador not in html:
            raise SystemExit("No encuentro signoCoberturaRecomendada.")
        html = html.replace(marcador, HELPER_ROL + "\n" + marcador, 1)

    if "function respuestaLecturaCompetitivaGlobal" not in html:
        marcador = "    function respuestaDiagnostico(diagnostico) {"
        if marcador not in html:
            raise SystemExit("No encuentro respuestaDiagnostico.")
        html = html.replace(marcador, FUNCION_GLOBAL + "\n" + marcador, 1)

    llamada_old = '''      const estrategiaApuesta = respuestaEstrategiaApuesta(q, data);
      if (estrategiaApuesta) return estrategiaApuesta;
      const debatePartido = respuestaDebatePartido(q, data);
'''
    llamada_new = '''      const estrategiaApuesta = respuestaEstrategiaApuesta(q, data);
      if (estrategiaApuesta) return estrategiaApuesta;
      const lecturaCompetitiva = respuestaLecturaCompetitivaGlobal(q, data);
      if (lecturaCompetitiva) return lecturaCompetitiva;
      const debatePartido = respuestaDebatePartido(q, data);
'''
    if "const lecturaCompetitiva = respuestaLecturaCompetitivaGlobal(q, data);" not in html:
        if llamada_old not in html:
            raise SystemExit("No encuentro punto de llamada para lectura competitiva.")
        html = html.replace(llamada_old, llamada_new, 1)

    texto_old = '''        yaLoContempla
          ? `La prediccion si lo tenia en cuenta, pero probablemente lo explicaba demasiado poco. En este caso ${equipoObjecion.equipo} no es un visitante cualquiera: su necesidad competitiva obliga a desconfiar de un fijo limpio.`
          : `Tu objecion anade una pieza importante que la respuesta anterior no estaba destacando con suficiente claridad: ${objetivoPrincipalTexto(datosObjecion)}`,
'''
    texto_new = '''        yaLoContempla
          ? `La prediccion si lo tenia en cuenta, pero probablemente lo explicaba demasiado poco. En este caso ${equipoObjecion.equipo} (${rolEquipoPartido(partido, equipoObjecion)}) no es un rival cualquiera: su necesidad competitiva obliga a desconfiar de un fijo limpio.`
          : `Tu objecion anade una pieza importante que la respuesta anterior no estaba destacando con suficiente claridad: ${objetivoPrincipalTexto(datosObjecion)}`,
'''
    if texto_old in html:
        html = html.replace(texto_old, texto_new, 1)

    conclusion_old = '''        "Conclusion: no cambiaria automaticamente el signo solo por la necesidad, porque tambien pesan forma, goles, casa/fuera y probabilidades. Pero si vas con dobles, este es un partido candidato a cobertura; y si me preguntas antes de validar, te diria que el 1 fijo es mas arriesgado de lo que parece."
'''
    conclusion_new = '''        `Conclusion: no cambiaria automaticamente el signo solo por la necesidad, porque tambien pesan forma, goles, casa/fuera y probabilidades. Pero si vas con dobles, este es un partido candidato a cobertura; y si me preguntas antes de validar, te diria que el fijo ${signoBase} es mas arriesgado de lo que parece.`
'''
    if conclusion_old in html:
        html = html.replace(conclusion_old, conclusion_new, 1)

    return html


def main():
    html = INDEX.read_text(encoding="utf-8")
    nuevo = patch(html)
    if nuevo != html:
        INDEX.write_text(nuevo, encoding="utf-8")
        print("Asistente reforzado: lectura competitiva global para 1a y 2a.")
    else:
        print("Lectura competitiva global ya estaba aplicada.")


if __name__ == "__main__":
    main()
