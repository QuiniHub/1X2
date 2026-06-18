(function () {
  const CACHE = "?v=" + Date.now();
  const PRECIO_APUESTA_QUINIELA = 0.75;
  const PRECIO_ELIGE8_POR_APUESTA = 0.50;
  let estadoJornadaObjetivoCache = null;

  function euros(valor) {
    const n = Number(valor || 0);
    return n.toFixed(2).replace(".", ",") + " €";
  }

  function normalizarSignos(valor) {
    if (Array.isArray(valor)) return valor.map(String).slice(0, 14);
    const texto = String(valor || "").trim().toUpperCase();
    if (!texto || texto === "NO VALIDADA" || texto === "NO JUGADA") return [];
    const porEspacios = texto.split(/\s+/).filter(Boolean);
    if (porEspacios.length > 1) return porEspacios.slice(0, 14);
    if (/^[12X]{14}$/.test(texto)) return texto.split("");
    return [];
  }

  async function fetchJSON(url, fallback) {
    try {
      const res = await fetch(url + CACHE);
      if (!res.ok) throw new Error(url);
      return await res.json();
    } catch (e) {
      return fallback;
    }
  }

  async function cargarEstadoJornadaObjetivo() {
    if (estadoJornadaObjetivoCache) return estadoJornadaObjetivoCache;
    estadoJornadaObjetivoCache = await fetchJSON("data/estado_jornada_objetivo.json", {});
    return estadoJornadaObjetivoCache || {};
  }

  function jornadaObjetivoDesdeEstado(estado) {
    return Number(estado?.jornada_objetivo || 0);
  }

  function jornadaSeleccionadaWeb() {
    const activo = document.querySelector("#lista-jornadas-quiniela button.active");
    const match = String(activo?.id || activo?.textContent || "").match(/(\d+)/);
    return match ? Number(match[1]) : 0;
  }

  function prediccionEsJornadaObjetivo(prediccion, estado) {
    const objetivo = jornadaObjetivoDesdeEstado(estado);
    if (!objetivo) return true;
    return Number(prediccion?.jornada || 0) === objetivo;
  }

  function listaJornadasTexto(jornadas) {
    return (jornadas || []).length ? jornadas.join(", ") : "ninguna";
  }

  function renderAvisoPrediccionDesfasada(prediccion, estado) {
    const objetivo = jornadaObjetivoDesdeEstado(estado) || "-";
    const cargada = estado?.jornada_objetivo_cargada;
    const futuras = listaJornadasTexto(estado?.jornadas_futuras_cargadas);
    const faltantes = listaJornadasTexto(estado?.jornadas_intermedias_faltantes);
    const accion = cargada
      ? `Abre la Jornada ${objetivo} y genera la predicción desde esa jornada.`
      : `Esperando a que se cargue el boleto oficial de la Jornada ${objetivo}.`;
    return `<div class="boleto-resumen" id="aviso-prediccion-desfasada"><h3>Predicción bloqueada por jornada objetivo</h3><p><strong>La última predicción guardada es Jornada ${prediccion?.jornada || "-"}, pero la jornada que toca predecir es Jornada ${objetivo}.</strong></p><p>Última jornada aprendida: ${estado?.ultima_jornada_aprendida || "-"}. Jornadas futuras cargadas solo para calendario: ${futuras}. Jornadas intermedias faltantes o incompletas: ${faltantes}.</p><p>${accion} La IA no debe saltar a jornadas futuras hasta aprender la jornada anterior.</p></div>`;
  }

  async function marcarEstadoJornadaObjetivo(estado) {
    const objetivo = jornadaObjetivoDesdeEstado(estado);
    if (!objetivo) return;
    const futuras = new Set((estado?.jornadas_futuras_cargadas || []).map(Number));
    const faltantes = new Set((estado?.jornadas_intermedias_faltantes || []).map(Number));
    document.querySelectorAll("#lista-jornadas-quiniela button").forEach(boton => {
      const match = String(boton.id || boton.textContent || "").match(/(\d+)/);
      const jornada = match ? Number(match[1]) : 0;
      if (!jornada) return;
      if (jornada === objetivo) {
        boton.title = "Jornada objetivo de predicción: siguiente tras la última aprendida.";
        boton.dataset.estadoObjetivo = "objetivo";
      } else if (futuras.has(jornada)) {
        boton.title = "Jornada futura cargada: visible en calendario, pero no debe predecirse todavía.";
        boton.dataset.estadoObjetivo = "futura";
      } else if (faltantes.has(jornada)) {
        boton.title = "Jornada intermedia faltante o incompleta: debe revisarse antes de avanzar.";
        boton.dataset.estadoObjetivo = "faltante";
      }
    });

    const contenedor = document.getElementById("lista-jornadas-quiniela");
    if (!contenedor || document.getElementById("aviso-jornada-objetivo-web")) return;
    contenedor.insertAdjacentHTML("afterend", `<p id="aviso-jornada-objetivo-web" class="small-muted">Jornada objetivo de predicción: <strong>${objetivo}</strong>. Las jornadas futuras cargadas no se predicen hasta validar y aprender la anterior.</p>`);
  }

  async function abrirJornadaObjetivoEnWeb() {
    const estado = await cargarEstadoJornadaObjetivo();
    const objetivo = jornadaObjetivoDesdeEstado(estado);
    if (!objetivo) return;
    await marcarEstadoJornadaObjetivo(estado);
    const seleccionada = jornadaSeleccionadaWeb();
    if (seleccionada === objetivo) return;
    if (typeof window.abrirQuinielaIA === "function") {
      await window.abrirQuinielaIA(objetivo);
      await marcarEstadoJornadaObjetivo(estado);
    }
  }

  function instalarBloqueoPrediccionFutura() {
    if (window.__bloqueoJornadaObjetivoActiva || typeof window.generarBoletoIA !== "function") return;
    window.__bloqueoJornadaObjetivoActiva = true;
    const generarOriginal = window.generarBoletoIA;
    window.generarBoletoIA = async function generarBoletoIASoloJornadaObjetivo() {
      const estado = await cargarEstadoJornadaObjetivo();
      const objetivo = jornadaObjetivoDesdeEstado(estado);
      const seleccionada = jornadaSeleccionadaWeb();
      if (objetivo && seleccionada && seleccionada !== objetivo) {
        alert(`La predicción activa debe ser la Jornada ${objetivo}. La Jornada ${seleccionada} puede estar cargada, pero no debe predecirse hasta aprender las jornadas anteriores.`);
        return;
      }
      return generarOriginal.apply(this, arguments);
    };
  }

  function signoOficialDesdeItem(item) {
    const texto = String(item.resultado_oficial || item.resultado || "").trim().toUpperCase();
    if (["1", "X", "2"].includes(texto)) return texto;
    return "";
  }

  function apuestasDesdeSignos(signos) {
    return signos.reduce((total, signo) => {
      const limpios = String(signo || "").replace(/[^1X2]/g, "");
      return total * Math.max(limpios.length || 1, 1);
    }, 1);
  }

  function costeJugada(signos, elige8) {
    const apuestas = apuestasDesdeSignos(signos);
    const importeQuiniela = Math.max(apuestas * PRECIO_APUESTA_QUINIELA, 1.50);
    const importeElige8 = elige8 ? apuestas * PRECIO_ELIGE8_POR_APUESTA : 0;
    return { apuestas, importe: importeQuiniela + importeElige8 };
  }

  function costePrediccionActual(prediccion) {
    const coste = prediccion.coste || {};
    const config = prediccion.configuracion || {};
    const apuestas = Number(coste.apuestas || apuestasDesdeSignos(signosPrediccion(prediccion)) || 1);
    const importeQuiniela = Math.max(apuestas * PRECIO_APUESTA_QUINIELA, 1.50);
    const importeElige8Correcto = apuestas * PRECIO_ELIGE8_POR_APUESTA;
    const totalConElige8 = importeQuiniela + importeElige8Correcto;
    const totalSinElige8 = importeQuiniela;
    return { apuestas, importeQuiniela, importeElige8Correcto, totalActual: config.elige8 ? totalConElige8 : totalSinElige8, totalConElige8, elige8Activado: Boolean(config.elige8) };
  }

  function textoCostePrediccion(prediccion) {
    const coste = costePrediccionActual(prediccion);
    if (coste.elige8Activado) return `Coste quiniela: ${euros(coste.importeQuiniela)} · Elige 8 (${coste.apuestas} apuestas x 0,50 €): ${euros(coste.importeElige8Correcto)} · Total: ${euros(coste.totalActual)}.`;
    return `Coste quiniela: ${euros(coste.importeQuiniela)} · Si añades Elige 8 (${coste.apuestas} apuestas x 0,50 €): +${euros(coste.importeElige8Correcto)} · Total con Elige 8: ${euros(coste.totalConElige8)}.`;
  }

  function calcularMetricas(historial) {
    const jornadas = (historial.jornadas || []).filter(j => normalizarSignos(j.nuestra_quiniela || j.signos).length >= 14);
    const acumulado = { jornadas: 0, partidos: 0, aciertos: 0, coste: 0, porTipo: { FIJO: { total: 0, aciertos: 0 }, DOBLE: { total: 0, aciertos: 0 }, TRIPLE: { total: 0, aciertos: 0 } }, evolucion: [] };
    jornadas.forEach(jornada => {
      const signos = normalizarSignos(jornada.nuestra_quiniela || jornada.signos);
      const oficial = normalizarSignos(jornada.resultado_oficial || jornada.signos_oficiales);
      if (signos.length < 14 || oficial.length < 14) return;
      let aciertosJornada = 0;
      signos.slice(0, 14).forEach((jugado, idx) => {
        const real = oficial[idx] || signoOficialDesdeItem((jornada.partidos || [])[idx] || {});
        if (!["1", "X", "2"].includes(real)) return;
        const limpios = String(jugado || "").replace(/[^1X2]/g, "");
        const tipo = limpios.length >= 3 ? "TRIPLE" : limpios.length === 2 ? "DOBLE" : "FIJO";
        const acierto = limpios.includes(real);
        acumulado.partidos += 1;
        acumulado.porTipo[tipo].total += 1;
        if (acierto) {
          acumulado.aciertos += 1;
          acumulado.porTipo[tipo].aciertos += 1;
          aciertosJornada += 1;
        }
      });
      const coste = costeJugada(signos, Array.isArray(jornada.elige8) && jornada.elige8.length > 0);
      acumulado.coste += coste.importe;
      acumulado.jornadas += 1;
      acumulado.evolucion.push({ jornada: jornada.jornada, aciertos: aciertosJornada });
    });
    return acumulado;
  }

  function pct(aciertos, total) {
    if (!total) return "sin datos";
    return ((aciertos / total) * 100).toFixed(1).replace(".", ",") + "%";
  }

  function signosPrediccion(prediccion) {
    return (prediccion.partidos || []).filter(p => Number(p.num) <= 14).sort((a, b) => Number(a.num) - Number(b.num)).map(p => p.signo_final || p.signo_base || "?");
  }

  function razonesClave(prediccion) {
    const partidos = (prediccion.partidos || []).filter(p => Number(p.num) <= 14);
    return [...partidos].sort((a, b) => Number(b.incertidumbre || b.probabilidad_sorpresa || 0) - Number(a.incertidumbre || a.probabilidad_sorpresa || 0)).slice(0, 3).map(p => {
      const probs = p.probabilidades || {};
      const riesgo = p.probabilidad_sorpresa !== undefined ? `sorpresa ${p.probabilidad_sorpresa}%` : `incertidumbre ${Math.round(Number(p.incertidumbre || 0))}`;
      return `${p.num}. ${p.local} - ${p.visitante}: ${p.signo_final || p.signo_base || "?"} (${riesgo}; 1=${probs["1"] ?? "-"}%, X=${probs["X"] ?? "-"}%, 2=${probs["2"] ?? "-"}%).`;
    });
  }

  function renderMetricas(prediccion, metricas) {
    const signos = signosPrediccion(prediccion);
    const config = prediccion.configuracion || {};
    const porTipo = metricas.porTipo;
    const ultimas = metricas.evolucion.slice(-5).map(x => `J${x.jornada}: ${x.aciertos}/14`).join(" · ") || "sin histórico validado";
    const razones = razonesClave(prediccion);
    const precisionGlobal = pct(metricas.aciertos, metricas.partidos);
    const roiTecnico = metricas.jornadas ? `Coste simulado validado: ${euros(metricas.coste)}. Premios/ROI real: pendiente de integrar escrutinio oficial.` : "Sin coste histórico validado todavía.";
    const costeTexto = textoCostePrediccion(prediccion);
    return `<div class="boleto-resumen" id="resumen-rapido-metricas"><h3>Resumen rápido</h3><p><strong>¿Qué jugar ahora?</strong><br>Jornada ${prediccion.jornada || "-"}: ${signos.join(" ") || "sin signos"}. ${config.dobles || 0} dobles · ${config.triples || 0} triples${config.elige8 ? " · Elige 8" : ""}. ${costeTexto}</p><p><strong>¿Por qué lo recomienda?</strong><br>${(razones.length ? razones : ["El modelo combina probabilidad, forma, casa/fuera, contexto competitivo y riesgo de sorpresa."]).join("<br>")}</p><p><strong>¿Qué tal ha funcionado antes?</strong><br>Precisión global: ${precisionGlobal} (${metricas.aciertos}/${metricas.partidos} signos revisados). Fijos: ${pct(porTipo.FIJO.aciertos, porTipo.FIJO.total)} · Dobles: ${pct(porTipo.DOBLE.aciertos, porTipo.DOBLE.total)} · Triples: ${pct(porTipo.TRIPLE.aciertos, porTipo.TRIPLE.total)}.<br>Evolución reciente: ${ultimas}.<br>${roiTecnico}</p></div>`;
  }

  function activarMejoraXCercana() {
    if (window.__mejoraXCercanaActiva || typeof window.prioridadDobleAnalisis !== "function") return;
    window.__mejoraXCercanaActiva = true;
    const prioridadOriginal = window.prioridadDobleAnalisis;
    function ordenProbabilidades(probs) { return Object.entries(probs || {}).map(([signo, valor]) => [signo, Number(valor || 0)]).sort((a, b) => b[1] - a[1]); }
    function objetivoVivo(datos) { if (!datos) return false; const texto = JSON.stringify(datos).toLowerCase(); return texto.includes("descenso") || texto.includes("permanencia") || texto.includes("playoff") || texto.includes("ascenso") || texto.includes("defiende") || texto.includes("aspira") || texto.includes("europa") || texto.includes("conference"); }
    function mejoraXCercana(partido) {
      const orden = ordenProbabilidades(partido?.probabilidades || {});
      if (orden.length < 2) return 0;
      const [primero, segundo] = orden;
      const margen = primero[1] - segundo[1];
      const xCerca = segundo[0] === "X" && margen <= 12 && primero[1] < 58;
      const necesidad = Boolean(partido?.riesgo_necesidad || partido?.riesgo_necesidad_real) || objetivoVivo(partido?.contexto_competitivo_local) || objetivoVivo(partido?.contexto_competitivo_visitante);
      if (!xCerca || !necesidad) return 0;
      let bonus = 180;
      if (margen <= 8) bonus += 80;
      if (Number(partido?.probabilidad_sorpresa || 0) >= 60 || Number(partido?.incertidumbre || 0) >= 180) bonus += 60;
      return bonus;
    }
    window.prioridadDobleAnalisis = function prioridadDobleAnalisisConXCercana(partido) { return prioridadOriginal(partido) + mejoraXCercana(partido); };
  }

  function estabilizarElige8SobreBoletoBase() {
    if (window.__elige8EstableActiva || typeof window.evaluarConfiguracionEstrategia !== "function") return;
    window.__elige8EstableActiva = true;
    const evaluarOriginal = window.evaluarConfiguracionEstrategia;
    window.evaluarConfiguracionEstrategia = function evaluarConfiguracionEstrategiaElige8Estable(partidosBase, dobles, triples, elige8 = false) {
      const base = evaluarOriginal(partidosBase, dobles, triples, false);
      if (!elige8) return base;
      const conElige8 = evaluarOriginal(partidosBase, dobles, triples, true);
      return { ...base, elige8: true, coste: conElige8.coste, elige8Candidatos: conElige8.elige8Candidatos, valor: base.valor + 0.01 };
    };
  }

  function pronosticoValidoPleno(valor) {
    const texto = String(valor || "").trim();
    if (!texto) return "";
    const bajo = texto.toLowerCase();
    if (bajo === "pendiente" || bajo === "no jugada" || bajo === "no validada") return "";
    return texto;
  }

  function plenoCalculado(pleno, partidos) {
    if (!pleno) return null;
    if (typeof pronosticarPleno15 === "function") {
      const calculado = pronosticarPleno15(pleno, partidos);
      if (calculado?.pronostico) return calculado;
    }
    return {
      local: pleno.local || "",
      visitante: pleno.visitante || "",
      pronostico: pronosticoValidoPleno(pleno.pronostico) || pronosticoValidoPleno(pleno.signo_nuestro) || pronosticoValidoPleno(pleno.resultado) || "1-1",
      explicacion: pleno.explicacion || "Pronóstico orientativo del Pleno al 15 basado en la predicción activa."
    };
  }

  function instalarGeneradorBoletoEstable() {
    if (window.__generadorBoletoElige8Estable || typeof window.generarBoletoIA !== "function") return;
    window.__generadorBoletoElige8Estable = true;
    const generarOriginal = window.generarBoletoIA;
    window.generarBoletoIA = async function generarBoletoIAEstable() {
      const doblesInput = document.getElementById("num-dobles");
      const triplesInput = document.getElementById("num-triples");
      const elige8Input = document.getElementById("activar-elige8");
      const doblesSolicitados = parseInt(doblesInput?.value || "0", 10);
      const triplesSolicitados = parseInt(triplesInput?.value || "0", 10);
      const activarElige8 = Boolean(elige8Input?.checked);
      const prediccionBackend = await fetchJSON("data/predicciones/ultima_prediccion.json", null);
      const estado = await cargarEstadoJornadaObjetivo();
      const objetivo = jornadaObjetivoDesdeEstado(estado);
      const jornada = typeof jornadaActualIA !== "undefined" ? jornadaActualIA : prediccionBackend?.jornada;
      if (objetivo && Number(jornada) !== objetivo) {
        alert(`La predicción activa debe ser la Jornada ${objetivo}. La Jornada ${jornada || "seleccionada"} puede estar cargada, pero no debe predecirse todavía.`);
        return;
      }
      const backendDobles = Number(prediccionBackend?.resumen?.dobles ?? prediccionBackend?.configuracion?.dobles ?? 0);
      const backendTriples = Number(prediccionBackend?.resumen?.triples ?? prediccionBackend?.configuracion?.triples ?? 0);
      const coincideConfig = (doblesSolicitados === 0 && triplesSolicitados === 0) || (doblesSolicitados === backendDobles && triplesSolicitados === backendTriples);
      const usarBackend = prediccionBackend && Number(prediccionBackend.jornada) === Number(jornada) && prediccionBackend.configuracion?.cobertura_auto && coincideConfig;
      if (!usarBackend) return generarOriginal.apply(this, arguments);
      if (doblesInput) doblesInput.value = backendDobles;
      if (triplesInput) triplesInput.value = backendTriples;
      if (elige8Input) elige8Input.checked = activarElige8;
      if (typeof calcularImporteIA === "function") calcularImporteIA();
      const partidos = (prediccionBackend.partidos || []).filter(p => Number(p.num) <= 14).map(p => ({ ...p, num: Number(p.num), tipo_apuesta: p.tipo || "FIJO", signo_final: p.signo_final || p.signo_base || "1", explicacion: p.razonamiento || "", confianza: p.confianza || "IA", riesgo: p.riesgo || (Number(p.incertidumbre || 0) >= 115 || Number(p.probabilidad_sorpresa || 0) >= 55 ? "Alto" : "Medio") })).sort((a, b) => a.num - b.num);
      const elige8Set = new Set();
      if (activarElige8 && typeof candidatosElige8CobroWeb === "function") candidatosElige8CobroWeb(partidos.map(p => ({ partido: p, num: p.num, tipo: p.tipo_apuesta, signos: p.signo_final, riesgo: p.incertidumbre }))).forEach(item => elige8Set.add(Number(item.num)));
      const plenoBase = (typeof pleno15JornadaIA !== "undefined" && pleno15JornadaIA) || prediccionBackend.pleno15 || null;
      const plenoIA = plenoCalculado(plenoBase, partidos);
      const contenedor = document.getElementById("boleto-ia");
      if (!contenedor) return;
      const importe = document.getElementById("importe-quiniela")?.textContent || "";
      contenedor.innerHTML = `<div class="boleto-resumen"><strong>Jornada ${jornada}</strong> · ${14 - backendDobles - backendTriples} sencillos · ${backendDobles} dobles · ${backendTriples} triples · ${activarElige8 ? "Elige 8 activado" : "Elige 8 no activado"} · ${importe}</div>${partidos.map(p => `<div class="fila-boleto ${elige8Set.has(p.num) ? "elige8-activo" : ""}"><div>${p.num}</div><div><strong>${p.local} - ${p.visitante}</strong><br><small>1: ${p.probabilidades?.["1"] ?? "-"}% · X: ${p.probabilidades?.["X"] ?? "-"}% · 2: ${p.probabilidades?.["2"] ?? "-"}%</small><br><small>Confianza: ${p.confianza} · Riesgo: ${p.riesgo}</small>${elige8Set.has(p.num) ? `<br><span class="elige8-badge">Elige 8</span>` : ""}</div><div class="signos-ia">${String(p.signo_final).split("").map(s => `<span>${s}</span>`).join("")}</div></div>`).join("")}${plenoIA ? `<div class="fila-boleto pleno15"><div>15</div><div><strong>Pleno al 15</strong><br><small>${plenoIA.local} - ${plenoIA.visitante}</small><br><small>${plenoIA.explicacion}</small></div><div class="signos-ia"><span>${plenoIA.pronostico}</span></div></div>` : ""}<div class="card" style="margin-top:20px;"><h3>Análisis IA del boleto</h3>${partidos.map(p => `<p><strong>${p.num}. ${p.local} - ${p.visitante}</strong><br>Signo recomendado: <strong>${p.signo_final}</strong><br>${elige8Set.has(p.num) ? "<strong>Marcado para Elige 8.</strong><br>" : ""}${p.explicacion}</p>`).join("")}</div>`;
    };
  }

  function instalarRegistroQuinielaIAGenerada() {
    if (window.__registroQuinielaIAGeneradaActiva || typeof window.generarBoletoIA !== "function") return;
    window.__registroQuinielaIAGeneradaActiva = true;
    const generarOriginal = window.generarBoletoIA;
    window.generarBoletoIA = async function generarBoletoIAConRegistroPendiente() {
      const resultado = await generarOriginal.apply(this, arguments);
      const botonValidacionVisible = document.querySelector("#boleto-ia button[onclick^='validarBoletoIAGenerado']");
      const jornada = typeof jornadaActualIA !== "undefined" ? Number(jornadaActualIA) : 0;
      if (botonValidacionVisible || !jornada || typeof window.registrarQuinielaIAGenerada !== "function") return resultado;

      const prediccionBackend = await fetchJSON("data/predicciones/ultima_prediccion.json", null);
      if (!prediccionBackend || Number(prediccionBackend.jornada) !== jornada) return resultado;
      const partidos = (prediccionBackend.partidos || [])
        .filter(p => Number(p.num) <= 14)
        .sort((a, b) => Number(a.num) - Number(b.num));
      if (!partidos.length) return resultado;
      let elige8 = partidos.filter(p => p.elige8).map(p => Number(p.num)).slice(0, 8);
      if (document.getElementById("activar-elige8")?.checked && typeof candidatosElige8CobroWeb === "function") {
        elige8 = candidatosElige8CobroWeb(partidos.map(p => ({
          partido: p,
          num: Number(p.num),
          tipo: p.tipo_apuesta || p.tipo,
          signos: p.signo_final,
          riesgo: p.incertidumbre
        }))).map(item => Number(item.num)).slice(0, 8);
      }
      const pleno = plenoCalculado(prediccionBackend.pleno15, partidos);
      await window.registrarQuinielaIAGenerada({
        jornada,
        signos: partidos.map(p => p.signo_final || p.signo_base || "1"),
        elige8,
        pleno15: pleno?.pronostico || ""
      });
      return resultado;
    };
  }

  function programarEstabilidadElige8() {
    setTimeout(estabilizarElige8SobreBoletoBase, 200);
    setTimeout(estabilizarElige8SobreBoletoBase, 1200);
    setTimeout(estabilizarElige8SobreBoletoBase, 3000);
    setTimeout(instalarGeneradorBoletoEstable, 200);
    setTimeout(instalarGeneradorBoletoEstable, 1200);
    setTimeout(instalarGeneradorBoletoEstable, 3000);
    setTimeout(instalarRegistroQuinielaIAGenerada, 250);
    setTimeout(instalarRegistroQuinielaIAGenerada, 1300);
    setTimeout(instalarRegistroQuinielaIAGenerada, 3100);
    setTimeout(instalarBloqueoPrediccionFutura, 350);
    setTimeout(instalarBloqueoPrediccionFutura, 1400);
    setTimeout(instalarBloqueoPrediccionFutura, 3200);
  }

  async function initResumenRapidoMetricas() {
    activarMejoraXCercana();
    estabilizarElige8SobreBoletoBase();
    instalarGeneradorBoletoEstable();
    instalarBloqueoPrediccionFutura();
    await abrirJornadaObjetivoEnWeb();
    const contenedor = document.getElementById("prediccion-resumen");
    if (!contenedor || document.getElementById("resumen-rapido-metricas") || document.getElementById("aviso-prediccion-desfasada")) return;
    const [prediccion, historial, estado] = await Promise.all([
      fetchJSON("data/predicciones/ultima_prediccion.json", null),
      fetchJSON("data/historial_quinielas.json", { jornadas: [] }),
      cargarEstadoJornadaObjetivo()
    ]);
    if (!prediccion) return;
    if (!prediccionEsJornadaObjetivo(prediccion, estado)) {
      contenedor.innerHTML = renderAvisoPrediccionDesfasada(prediccion, estado);
      return;
    }
    const metricas = calcularMetricas(historial || { jornadas: [] });
    contenedor.insertAdjacentHTML("beforeend", renderMetricas(prediccion, metricas));
  }

  function programarResumenRapidoMetricas() {
    programarEstabilidadElige8();
    setTimeout(abrirJornadaObjetivoEnWeb, 700);
    setTimeout(abrirJornadaObjetivoEnWeb, 2000);
    setTimeout(initResumenRapidoMetricas, 1200);
    setTimeout(initResumenRapidoMetricas, 3000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", programarResumenRapidoMetricas);
  else programarResumenRapidoMetricas();
})();
