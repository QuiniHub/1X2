from pathlib import Path

path = Path("index.html")
text = path.read_text(encoding="utf-8")

old = r'''    function renderLeague() {
      const start = new Date('2026-08-14T20:00:00+02:00');
      const today = new Date();
      const days = Math.max(0, Math.ceil((start - today) / 86400000));
      qs('#daysToLeague').textContent = days;
      const primera = ['Real Madrid', 'Barcelona', 'Atlético de Madrid', 'Athletic Club', 'Villarreal', 'Betis', 'Real Sociedad', 'Valencia', 'Sevilla', 'Celta', 'Osasuna', 'Getafe', 'Rayo Vallecano', 'Mallorca', 'Girona', 'Espanyol', 'Alavés', 'Real Oviedo', 'Levante', 'Elche'];
      const primeraAsc = ['Real Oviedo', 'Levante', 'Elche'];
      const segunda = segundaTeamsFromCalendar();
      const segundaAsc = ['Racing Santander', 'Deportivo La Coruña', 'Málaga'];
      const segundaDesc = ['Leganés', 'Las Palmas', 'Valladolid'];
      const section = label => `<div style="grid-column:1/-1"><strong>${escapeHtml(label)}</strong></div>`;
      qs('#leagueTeams').innerHTML = [
        section('Primera División 2026/27'),
        ...primera.map(t => teamBadge(t, primeraAsc, [])),
        section('Segunda División 2026/27'),
        ...(segunda.length ? segunda.map(t => teamBadge(t, segundaAsc, segundaDesc)) : ['<div class="empty" style="grid-column:1/-1">Segunda División pendiente de cargar.</div>'])
      ].join('');
    }'''

new = r'''    function renderLeague() {
      const start = new Date('2026-08-14T20:00:00+02:00');
      const today = new Date();
      const days = Math.max(0, Math.ceil((start - today) / 86400000));
      qs('#daysToLeague').textContent = days;

      const primera = [
        { equipo: 'FC Barcelona' },
        { equipo: 'Real Madrid' },
        { equipo: 'Villarreal' },
        { equipo: 'Atlético de Madrid' },
        { equipo: 'Real Betis' },
        { equipo: 'Celta de Vigo' },
        { equipo: 'Real Sociedad' },
        { equipo: 'Getafe' },
        { equipo: 'Athletic Club' },
        { equipo: 'Valencia' },
        { equipo: 'Sevilla' },
        { equipo: 'Rayo Vallecano' },
        { equipo: 'Osasuna' },
        { equipo: 'Espanyol' },
        { equipo: 'Alavés' },
        { equipo: 'Levante' },
        { equipo: 'Elche' },
        { equipo: 'Racing de Santander', estado: 'Ascendido', tag: 'ok' },
        { equipo: 'Deportivo de La Coruña', estado: 'Ascendido', tag: 'ok' },
        { equipo: 'Málaga CF', estado: 'Ascendido', tag: 'ok' }
      ];

      const segunda = [
        { equipo: 'Real Oviedo', estado: 'Descendido', tag: 'bad' },
        { equipo: 'RCD Mallorca', estado: 'Descendido', tag: 'bad' },
        { equipo: 'Girona FC', estado: 'Descendido', tag: 'bad' },
        { equipo: 'UD Almería' },
        { equipo: 'UD Las Palmas' },
        { equipo: 'CD Castellón' },
        { equipo: 'FC Burgos' },
        { equipo: 'SD Eibar' },
        { equipo: 'Córdoba CF' },
        { equipo: 'Sporting de Gijón' },
        { equipo: 'AD Ceuta' },
        { equipo: 'Albacete Balompié' },
        { equipo: 'FC Andorra' },
        { equipo: 'Granada CF' },
        { equipo: 'Real Sociedad B' },
        { equipo: 'CD Leganés' },
        { equipo: 'Real Valladolid' },
        { equipo: 'Cádiz CF' },
        { equipo: 'CD Tenerife', estado: 'Ascendido', tag: 'ok' },
        { equipo: 'Eldense', estado: 'Ascendido', tag: 'ok' },
        { equipo: 'Celta Fortuna', estado: 'Ascendido', tag: 'ok' },
        { equipo: 'CD Sabadell', estado: 'Ascendido', tag: 'ok' }
      ];

      const statCells = '<td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td><td>0</td>';
      const teamCell = team => `<strong>${escapeHtml(team.equipo)}</strong>${team.estado ? ` <span class="tag ${team.tag}">${escapeHtml(team.estado)}</span>` : ''}`;
      const row = (team, idx) => `<tr><td>${idx + 1}</td><td>${teamCell(team)}</td>${statCells}</tr>`;
      const table = (title, teams) => `<section style="grid-column:1/-1;display:grid;gap:12px"><div><h3>${escapeHtml(title)}</h3><p class="subtitle">Clasificación inicial 2026/27 · todos los equipos arrancan con 0 puntos.</p></div><table><thead><tr><th>Pos</th><th>Equipo</th><th>PJ</th><th>G</th><th>E</th><th>P</th><th>GF</th><th>GC</th><th>DG</th><th>Pts</th></tr></thead><tbody>${teams.map(row).join('')}</tbody></table></section>`;

      qs('#leagueTeams').innerHTML = [
        table('LALIGA EA SPORTS 2026/27', primera),
        table('LALIGA HYPERMOTION 2026/27', segunda)
      ].join('');
    }'''

if old not in text:
    raise SystemExit("No se encontro el bloque renderLeague exacto")

updated = text.replace(old, new, 1)
if updated.count("function renderLeague()") != 1:
    raise SystemExit("renderLeague no quedo una sola vez")
for needle in ["LALIGA EA SPORTS 2026/27", "LALIGA HYPERMOTION 2026/27", "Racing de Santander", "Deportivo de La Coruña", "Málaga CF", "Real Oviedo", "RCD Mallorca", "Girona FC", "CD Tenerife", "Eldense", "Celta Fortuna", "CD Sabadell"]:
    if needle not in updated:
        raise SystemExit(f"Falta {needle}")
path.write_text(updated, encoding="utf-8")
print("renderLeague reemplazado por tablas LALIGA 26/27")
