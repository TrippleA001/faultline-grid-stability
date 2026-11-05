# Faultline: IEEE 39-bus Stability and Load-Shedding Lab

**Faultline** rebuilds the machine-learning half of an MSc
power-systems study. An electrical engineer simulated fault scenarios on the IEEE 39-bus (New England)
system in **PSS/E**; I took the exported data, audited it, wrote the engineer's load-shedding rule down as
code, and measured honestly what machine learning can add.

Method basis: [Abdul Wahab & Mohamed (2012)](https://doi.org/10.1155/2012/410461), *Area-based COI-referred
rotor angle index for transient stability assessment and control of power systems*, Abstract and Applied
Analysis, 410461.

## The short version

| | First ML pass (Colab notebook) | This rebuild |
|---|---|---|
| Stability classifier | LSTM, rows split at random: **93% accuracy, macro-F1 0.12**; never caught an unstable area | Leave-one-scenario-out: logistic regression, **micro-F1 0.51** vs 0.00 for always-stable |
| Load-shedding targets | LSTM regressor on 38 outputs, **R² 0.54** | The engineer's rule as code, **R² 0.999** (67 impossible readings set aside) |
| Data | Used as exported | 14 issues found and logged; 5 scenarios flagged for the engineer |

The headline accuracy was a class-imbalance artefact: 94% of rows are steady-state copies labelled
*stable*. The regression targets turned out to be arithmetic: **shed MW = load-shedding factor × base load**,
with the factor ≈ 0.8 × bus voltage deviation.

## What the audit found

All checks run automatically in `scripts/build_dataset.py` and are shown on the app's Data Audit page.

- **A duplicated file.** `Power System 5.csv` is byte-for-byte identical to `Power System 4.csv`, so the
  "Area 4 alone" scenario is missing, and a naive evaluation scores Sim 4 against its own twin.
- **Two scenarios with identical voltages but different labels** (sims 47 and 51).
- **Labels that break the scenario pattern.** The 56 runs enumerate the base case, each single area and every
  pair of areas; sims 5, 30 and 48 do not fit.
- **Physically impossible values.** Bus 26 has shedding factors up to 11 (a fraction cannot exceed 1); bus 12
  sheds up to 93 MW from a 7.5 MW load.
- **A spreadsheet fill-series artefact.** Bus 28's factor counts 0, 1, 2, 3… before the fault in 55 files.
- **Smaller issues.** Encoding debris (`Â`) in numeric cells, a value pasted into the wrong column, header
  typos, gaps in the time grid.
- **A validation that passed.** All 19 base-case loads match the standard IEEE 39-bus case exactly.

Each finding becomes a question on the Data Audit page for the engineer. That loop, data science raising
specific and checkable questions for the domain expert, is the point of the project.

## App

| Page | Purpose |
|------|---------|
| **Overview** | The story in three findings, the worst post-fault snapshot on the one-line diagram, who did what |
| **Grid Explorer** | Step through any scenario: bus voltages on the diagram, recorded vs predicted unstable areas, shedding per bus |
| **Load Shedding** | The recovered rule, checked against every post-fault reading |
| **Model Lab** | The accuracy trap, leave-one-scenario-out leaderboard, early-warning window, every scenario out of sample |
| **Data Audit** | Every finding, its severity and action, and the questions for the engineer |

## Stack

Streamlit · Plotly · scikit-learn · pandas · pyarrow

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Processed data and model outputs are committed, so the app runs immediately. To rebuild from the raw
PSS/E exports in `data/raw/`:

```bash
python scripts/build_dataset.py
python scripts/train_models.py
```

## Repository layout

```
app.py                  Streamlit entry point
pages/                  five app pages
src/config.py           paths, IEEE 39-bus reference data, scenario design
src/data.py             loading, cleaning and the automated audit
src/physics.py          the engineer's shedding rule as code
src/model.py            features, leave-one-scenario-out evaluation, the accuracy-trap experiment
src/charts.py           Plotly figures, including the one-line diagram
scripts/                build_dataset.py, train_models.py
tests/                  pytest suite (data, physics, evaluation protocol)
data/raw/               56 PSS/E CSV exports and the base-case workbook
data/processed/         cleaned parquet and audit.json
models/                 metrics.json, out-of-sample predictions, final model
```

## Roadmap

1. **Tier 1, this repo:** honest analysis of the PSS/E study.
2. **Tier 2:** rebuild the case in the open-source [ANDES](https://github.com/CURENT/andes) simulator,
   validate it against the PSS/E results, and generate thousands of fault scenarios.
3. **Tier 3:** a graph neural network over the grid topology for stability assessment; reinforcement-learning
   load shedding as a stretch goal.

## Credits

PSS/E modelling and simulations: an electrical-engineering MSc graduate (the domain expert).
Data science, audit and app: AbdulSamad.
