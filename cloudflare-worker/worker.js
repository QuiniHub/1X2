// Cloudflare Worker — QuiniHub IA Proxy
// Rutas: /api/groq, /api/tavily, /api/football

const ESPN_LIGAS = {
  "esp.1":                  "La Liga",
  "esp.2":                  "Segunda División",
  "UEFA.CHAMPIONS":         "Champions League",
  "UEFA.EUROPA":            "Europa League",
  "UEFA.EUROPA.CONFERENCE": "Conference League",
  "eng.1":                  "Premier League",
  "ger.1":                  "Bundesliga",
  "ita.1":                  "Serie A",
  "fra.1":                  "Ligue 1",
  "por.1":                  "Primeira Liga",
  "ned.1":                  "Eredivisie",
  "FIFA.WORLD":             "Copa del Mundo",
  "swe.1":                  "Allsvenskan",
  "fin.1":                  "Veikkausliiga",
  "nor.1":                  "Eliteserien",
  "den.1":                  "Superliga Danesa",
};

const THESPORTSDB_LIGAS = {
  "La Liga":          "4335",
  "Segunda División": "4336",
  "Champions League": "4346",
  "Europa League":    "4347",
  "Premier League":   "4328",
  "Bundesliga":       "4331",
  "Serie A":          "4332",
  "Mundial 2026":     "600614",
  "Allsvenskan":      "4344",
  "Veikkausliiga":    "4430",
};

export default {
  async fetch(request, env) {
    const origin  = request.headers.get("Origin") || "";
    const allowed = "https://quinihub.github.io";
    const corsHeaders = {
      "Access-Control-Allow-Origin":  origin.startsWith(allowed) ? origin : allowed,
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    const url = new URL(request.url);

    // ── /api/groq ────────────────────────────────────────────────────────────
    if (url.pathname === "/api/groq") {
      const upstream = await fetch("https://api.groq.com/openai/v1/chat/completions", {
        method:  "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${env.GROQ_KEY}` },
        body:    request.body,
      });
      const res = new Response(upstream.body, upstream);
      Object.entries(corsHeaders).forEach(([k, v]) => res.headers.set(k, v));
      return res;
    }

    // ── /api/gemini ──────────────────────────────────────────────────────────
    if (url.pathname === "/api/gemini") {
      const body = await request.json();
      body.model = "gemini-1.5-flash";
      const upstream = await fetch("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", {
        method:  "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${env.GEMINI_KEY}` },
        body:    JSON.stringify(body),
      });
      const res = new Response(upstream.body, upstream);
      Object.entries(corsHeaders).forEach(([k, v]) => res.headers.set(k, v));
      return res;
    }

    // ── /api/tavily ──────────────────────────────────────────────────────────
    if (url.pathname === "/api/tavily") {
      const body = await request.json();
      body.api_key = env.TAVILY_KEY;
      const upstream = await fetch("https://api.tavily.com/search", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(body),
      });
      const res = new Response(upstream.body, upstream);
      Object.entries(corsHeaders).forEach(([k, v]) => res.headers.set(k, v));
      return res;
    }

    // ── /api/football ────────────────────────────────────────────────────────
    // GET /api/football?ligas=esp.1,UEFA.CHAMPIONS&dias=3
    // GET /api/football?ligas=all&dias=1   → todas las ligas
    if (url.pathname === "/api/football") {
      const ligasParam = url.searchParams.get("ligas") || "esp.1,UEFA.CHAMPIONS,UEFA.EUROPA,eng.1";
      const dias       = Math.min(parseInt(url.searchParams.get("dias") || "2"), 7);
      const ligas      = ligasParam === "all" ? Object.keys(ESPN_LIGAS) : ligasParam.split(",");

      const hoy    = new Date();
      const fechas = [];
      for (let i = dias; i >= 0; i--) {
        const d = new Date(hoy);
        d.setDate(d.getDate() - i);
        fechas.push(d.toISOString().slice(0, 10).replace(/-/g, ""));
      }

      const partidos = [];
      const enJuego  = [];

      await Promise.all(ligas.map(async (liga) => {
        const nombreLiga = ESPN_LIGAS[liga] || liga;
        await Promise.all(fechas.map(async (fecha) => {
          try {
            const r = await fetch(
              `https://site.api.espn.com/apis/site/v2/sports/soccer/${liga}/scoreboard?dates=${fecha}`,
              { headers: { "User-Agent": "QuiniHub/1X2" } }
            );
            if (!r.ok) return;
            const data = await r.json();
            for (const ev of (data.events || [])) {
              for (const comp of (ev.competitions || [])) {
                const statusName = comp?.status?.type?.name || "";
                const terminado  = ["STATUS_FINAL","STATUS_FULL_TIME","STATUS_EXTRA_TIME","STATUS_PENALTIES"].includes(statusName);
                const vivo       = ["STATUS_IN_PROGRESS","STATUS_HALFTIME"].includes(statusName);
                const comps      = comp.competitors || [];
                const home       = comps.find(c => c.homeAway === "home") || comps[0];
                const away       = comps.find(c => c.homeAway === "away") || comps[1];
                if (!home || !away) continue;
                const local     = home?.team?.displayName || "";
                const visitante = away?.team?.displayName || "";
                const sh        = home?.score;
                const sa        = away?.score;
                const fechaP    = (ev.date || "").slice(0, 10);
                const obj = { liga: nombreLiga, local, visitante, fecha: fechaP };
                if ((terminado || vivo) && sh != null && sa != null) {
                  obj.resultado = `${sh}-${sa}`;
                  obj.ganador   = parseInt(sh) > parseInt(sa) ? local : parseInt(sa) > parseInt(sh) ? visitante : "Empate";
                }
                if (vivo) {
                  obj.en_juego = true;
                  obj.minuto   = comp?.status?.displayClock || "";
                  enJuego.push(obj);
                } else if (terminado && obj.resultado) {
                  partidos.push(obj);
                }
              }
            }
          } catch (_) {}
        }));
      }));

      // Completar con TheSportsDB para cualquier liga que ESPN no devolvió
      const ligasConDatos = new Set(partidos.map(p => p.liga));
      const theSportsDBLigasFaltantes = Object.entries(THESPORTSDB_LIGAS)
        .filter(([nombre]) => !ligasConDatos.has(nombre));

      await Promise.all(theSportsDBLigasFaltantes.map(async ([nombre, id]) => {
        try {
          const r = await fetch(`https://www.thesportsdb.com/api/v1/json/3/eventspastleague.php?id=${id}`);
          if (!r.ok) return;
          const data = await r.json();
          for (const e of (data.events || [])) {
            const status = e.strStatus || "";
            const terminado = ["Match Finished","FT","AOT","AP","finished"].includes(status);
            if (!terminado) continue;
            const hg = e.intHomeScore, ag = e.intAwayScore;
            if (hg == null || ag == null) continue;
            partidos.push({
              liga:       nombre,
              local:      e.strHomeTeam || "",
              visitante:  e.strAwayTeam || "",
              resultado:  `${hg}-${ag}`,
              ganador:    parseInt(hg) > parseInt(ag) ? e.strHomeTeam : parseInt(ag) > parseInt(hg) ? e.strAwayTeam : "Empate",
              fecha:      e.dateEvent || "",
            });
          }
        } catch (_) {}
      }));

      const respData = {
        actualizado_en: new Date().toISOString(),
        en_juego:       enJuego,
        resultados:     partidos.slice(-200),
      };

      return new Response(JSON.stringify(respData), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    return new Response("Not found", { status: 404, headers: corsHeaders });
  },
};
