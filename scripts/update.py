#!/usr/bin/env python3
"""Updates docs/data.json with the US dollar in Brazilian reais, nominal and inflation-adjusted.

Sources (free, no API key):
  - Central Bank of Brazil, SGS 3698: commercial USD/BRL (selling), monthly average
  - Central Bank of Brazil, SGS 433:  IPCA, monthly change (%)
  - Central Bank of Brazil, SGS 1:    commercial USD/BRL (selling), daily rate (PTAX)
  - FRED (St. Louis Fed), CPIAUCSL: US consumer price index

Standard library only. If a source fails or returns something odd, the script
exits with an error and the previous data.json is left untouched.
"""

import csv
import datetime as dt
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "data.json"
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?formato=json&dataInicial={start}&dataFinal={end}"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL&cosd=1994-01-01"
FIRST_MONTH = (1994, 7)  # launch of the real
MIN_MONTHS = 388  # Jul 1994 to Oct 2026; the series only grows


def fetch(url, tries=5):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; real-dolar-ipca/1.0)",
                    "Accept": "application/json, text/csv, */*",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8-sig")
            if body.strip():
                return body
            last = "empty response"
        except Exception as exc:  # flaky network: try again
            last = exc
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last}")


def sgs(code, start, end):
    """Returns [(date, value)] for an SGS series."""
    url = SGS.format(code=code, start=start.strftime("%d/%m/%Y"), end=end.strftime("%d/%m/%Y"))
    rows = json.loads(fetch(url))
    out = []
    for row in rows:
        d, m, y = row["data"].split("/")
        out.append((dt.date(int(y), int(m), int(d)), float(row["valor"])))
    if not out:
        raise RuntimeError(f"SGS series {code} came back empty")
    return out


def next_month(ym):
    y, m = ym
    return (y + 1, 1) if m == 12 else (y, m + 1)


def us_cpi():
    """US CPI by month, filling unpublished months by geometric interpolation."""
    cpi = {}
    for row in csv.DictReader(io.StringIO(fetch(FRED))):
        try:
            y, m, _ = row["observation_date"].split("-")
            cpi[(int(y), int(m))] = float(row["CPIAUCSL"])
        except (KeyError, ValueError):
            continue  # month without data (e.g. Oct 2025)
    if not cpi:
        raise RuntimeError("US CPI came back empty")
    months = sorted(cpi)
    cur = months[0]
    while cur < months[-1]:
        if cur not in cpi:
            prev = max(k for k in cpi if k < cur)
            nxt = min(k for k in cpi if k > cur)
            span = (nxt[0] - prev[0]) * 12 + (nxt[1] - prev[1])
            step = (cur[0] - prev[0]) * 12 + (cur[1] - prev[1])
            cpi[cur] = cpi[prev] * (cpi[nxt] / cpi[prev]) ** (step / span)
        cur = next_month(cur)
    return cpi


def build():
    today = dt.date.today()

    usd = {(d.year, d.month): v for d, v in sgs(3698, dt.date(1994, 1, 1), today)}
    ipca_pct = {(d.year, d.month): v for d, v in sgs(433, dt.date(1994, 1, 1), today)}
    daily = sgs(1, today - dt.timedelta(days=45), today)
    cpi = us_cpi()

    # Cumulative IPCA index
    ipca_idx, level = {}, 1.0
    for ym in sorted(ipca_pct):
        level *= 1 + ipca_pct[ym] / 100
        ipca_idx[ym] = level

    base = max(ipca_idx)  # last month with published IPCA: values are in that month's reais
    last_cpi = max(cpi)
    cpi_base = cpi.get(base, cpi[last_cpi])

    months = sorted(ym for ym in usd if ym >= FIRST_MONTH)
    nominal, real_ipca, real_both = [], [], []
    for ym in months:
        i_t = ipca_idx.get(ym, ipca_idx[base])  # current month without IPCA yet: no adjustment
        c_t = cpi.get(ym, cpi[last_cpi])
        r = usd[ym] * ipca_idx[base] / i_t
        nominal.append(round(usd[ym], 4))
        real_ipca.append(round(r, 4))
        real_both.append(round(r / (cpi_base / c_t), 4))

    last_day, last_value = daily[-1]
    data = {
        "base": f"{base[0]:04d}-{base[1]:02d}",
        "months": [f"{y:04d}-{m:02d}" for y, m in months],
        "nominal": nominal,
        "ipca": real_ipca,
        "ipca_cpi": real_both,
        "latest": {"date": last_day.isoformat(), "value": round(last_value, 4)},
    }
    validate(data)
    return data


def validate(data):
    n = len(data["months"])
    if n < MIN_MONTHS:
        raise RuntimeError(f"series too short: {n} months")
    if data["months"][0] != "1994-07":
        raise RuntimeError("series does not start in Jul 1994")
    for key in ("nominal", "ipca", "ipca_cpi"):
        if len(data[key]) != n:
            raise RuntimeError(f"inconsistent length in {key}")
        if not all(0.3 < v < 100 for v in data[key]):
            raise RuntimeError(f"unexpected value in {key}")
    if not 0.3 < data["latest"]["value"] < 100:
        raise RuntimeError("latest rate out of expected range")


def main():
    data = build()
    old = None
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
            old.pop("updated", None)
        except ValueError:
            old = None
    if old == data:
        print("Nothing new: data.json unchanged.")
        return 0
    data["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"data.json updated: {len(data['months'])} months, base {data['base']}, "
          f"latest rate {data['latest']['value']} on {data['latest']['date']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
