# trigger after workflow exists
from pathlib import Path

path = Path("index.html")
text = path.read_text(encoding="utf-8")
original = text

old_filter = ".filter(r => Number(r.jornada) >= 61 && (historyAciertos(r) > 0 || Number(r.partidos_comparados || 0) > 0 || arr(r.detalle_partidos).length > 0))"
new_filter = ".filter(r => Number(r.jornada) >= 70 && (historyAciertos(r) > 0 || Number(r.partidos_comparados || 0) > 0 || arr(r.detalle_partidos).length > 0))"

old_balance = "qs('#historyBalance').innerHTML = `<div><span>Total invertido IA</span><strong>${eur(totalInvertido)}</strong></div><div><span>Total cobrado</span><strong>${eur(totalCobrado)}</strong></div><div><span>Balance neto</span><strong>${eur(totalCobrado - totalInvertido)}</strong></div>`;"
new_balance = "qs('#historyBalance').innerHTML = `<div><span>Total premios cobrados</span><strong>${eur(totalCobrado)}</strong></div>`;"

old_coste_metric = "        metric('Coste boleto', eur(coste.importeTotal)),\n"
old_apuestas_metric = "        metric('Apuestas', coste.apuestas || '-')\n"

checks = [old_filter, old_balance, old_coste_metric, old_apuestas_metric]
missing = [item for item in checks if item not in text]
if missing:
    raise SystemExit("No se encontraron anclas exactas: " + repr(missing))

text = text.replace(old_filter, new_filter, 1)
text = text.replace(old_balance, new_balance, 1)
text = text.replace(old_coste_metric, "", 1)
text = text.replace(old_apuestas_metric, "", 1)

if text == original:
    raise SystemExit("No hubo cambios")
if text.count(new_filter) != 1:
    raise SystemExit("Filtro J70 no quedo una sola vez")
if text.count(new_balance) != 1:
    raise SystemExit("Balance simplificado no quedo una sola vez")
if "metric('Coste boleto'" in text or "metric('Apuestas'" in text:
    raise SystemExit("Metricas eliminadas siguen presentes")

path.write_text(text, encoding="utf-8")
print("index.html parcheado con 3 cambios quirurgicos")
