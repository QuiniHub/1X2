#!/usr/bin/env python3
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

SOURCES = {
    "primera_2025_26.csv": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv",
    "segunda_2025_26.csv": "https://www.football-data.co.uk/mmz4281/2526/SP2.csv",
}

for filename, url in SOURCES.items():
    try:
        print("Descargando", url)
        DATA.joinpath(filename).write_bytes(urllib.request.urlopen(url, timeout=30).read())
        print("OK", filename)
    except Exception as e:
        print("ERROR", filename, e)
