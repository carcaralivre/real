# real

When was the US dollar really at its most expensive in Brazil? This page shows the dollar in Brazilian reais since the Real Plan (July 1994), adjusted by the IPCA (Brazil's consumer price index) to today's money, with presidential terms and the events behind the big swings.

**Page:** https://carcaralivre.github.io/real/

## What the chart shows

- **IPCA-adjusted:** the average rate of each month, brought to today's reais by Brazil's accumulated inflation.
- **IPCA-adjusted, net of US inflation:** the real exchange rate, which also removes the dollar's own loss of purchasing power.
- **Nominal:** the rate at the time.
- The last point is the most recent daily rate (PTAX selling rate).

Each line can be toggled on and off and the period can be narrowed; the axes adjust automatically.

## How the data is updated

The workflow `.github/workflows/update.yml` runs every day at 18:23 Brasília time. It executes `scripts/update.py`, which fetches the series, recomputes everything and writes `docs/data.json`. If anything changed, the file is committed to the repository and the page is republished on GitHub Pages. If a source fails, the previous data is kept.

Sources, all free and without API keys:

| Data | Source | Series |
| --- | --- | --- |
| Commercial USD/BRL (selling), monthly average | Central Bank of Brazil, SGS | 3698 |
| Commercial USD/BRL (selling), daily rate | Central Bank of Brazil, SGS | 1 |
| IPCA, monthly change | Central Bank of Brazil, SGS | 433 |
| US consumer price index | FRED (St. Louis Fed) | CPIAUCSL |

## Running locally

```sh
python3 scripts/update.py          # updates docs/data.json (standard library only)
python3 -m http.server -d docs     # serves the page at http://localhost:8000
```

## Manual adjustments

Presidential terms and events live in two lists at the top of the script in `docs/index.html` (`PRES` and `EVENTS`). To add an event, append a row with the month (`YYYY-MM`) and the text.

## License

[MIT](LICENSE).
