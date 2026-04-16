<p align="center">
  <img src="backend/logo/Logo.png" alt="LOBSTER Logo" width="400"/>
</p>

<h1 align="center">LOBSTER</h1>
<h3 align="center">Data Transforming Made Easy</h3>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License MIT"/></a>
  <img src="https://img.shields.io/badge/version-0.4.2--alpha-orange.svg" alt="Version"/>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/status-alpha-red.svg" alt="Status"/>
  <img src="https://img.shields.io/badge/tests-276%20passed-brightgreen.svg" alt="Tests"/>
  <img src="https://img.shields.io/badge/docker-ready-blue.svg" alt="Docker"/>
</p>

---

## What is LOBSTER?

LOBSTER is an open source ETL tool designed for researchers to clean, transform and export data without writing code.

It guides you step by step through the full data pipeline — from raw file detection to clean, export-ready data — with full reproducibility in mind.

---

## Features

### Detection

- Auto file type detection — CSV, Excel (.xlsx, .xls), JSON
- Magic bytes verification — ensures file content matches its extension
- Encoding auto-detection with manual fallback

### Reading

- CSV with automatic encoding detection
- Excel with multi-sheet selection and optional merge
- JSON with automatic nested structure flattening
- Double-entry table detection (index column)

### Cleaning (Interactive)

- Replace zeros with NaN
- Handle missing values (drop rows/cols, fill with mean/median/mode/custom)
- Remove duplicates
- Fix column types (int, float, str, datetime)
- Trim whitespace
- Standardize case (lowercase / uppercase / titlecase)

### Pipeline & Reproducibility

- Save pipeline steps to JSON
- Replay pipeline automatically on new data — no re-configuration needed
- Full before/after cleaning report (text, JSON or HTML)

### Export

- CSV (sorted, UTF-8)
- Parquet (Data Lake)
- DuckDB (Data Warehouse)
- SQL — PostgreSQL / MySQL / SQLite
- MongoDB

### CLI

- Full command-line interface powered by `click`
- `lobster run` — full pipeline interactively
- `lobster detect` — detect file type only
- `lobster clean` — read and clean interactively
- `lobster export` — read and export directly
- `lobster replay` — replay a saved pipeline automatically

### AI Exercise Analyzer

- Extracts structured exercise data from free-text clinical notes using a **7-agent pipeline**
- **Agent 1 — Extractor:** identifies exercises, muscles, objectives, series, reps, duration, assistance
- **Agent 2 — Reviewer:** clinically validates Agent 1's output, auto-corrects or retries if rejected (max 2x)
- **Agent 3 — Synthesis:** produces a per-session clinical summary (dominant objective, intensity, narrative, recommendations)
- **Agent 4 — Publication Writer:** drafts a scientific publication (abstract, context, interventions, results, discussion) with automatic figures
- **Agent 5 — Clinical Writer:** drafts a clinical follow-up & observation record per patient
- **Agent 6 — Schema Detector:** absorbs heterogeneous assessment Excel layouts and standardizes them to a canonical long format
- **Agent 7 — Stats Writer:** interprets pre-computed statistical results into Methods + Results narrative (never invents numbers)
- **Research protocol support:** declare primary + secondary objectives once, AI validates each exercise against them
- Multi-provider support: **Mistral AI** (EU, RGPD compliant ✅) and **Anthropic Claude** (US ⚠️)
- BYOK model — bring your own API key, zero data transit through LOBSTER servers
- Fully interactive flow — RGPD notice, provider/model, report mode and format all confirmed at runtime

### Report generation

- Automatic figures generated from data (not AI): objective distribution, top muscles, code_base pie chart, volume progression
- Figures exported as standalone `.svg` + embedded in reports as `.png`
- Reports exported as `.pdf` or `.docx` with full Unicode support (DejaVu font)
- Two modes: **publication** (one combined report) or **clinical** (one report per patient)

### Quantitative assessments (Phase 1 — Excel only)

LOBSTER can ingest a second file containing the **assessment / evaluation results** (pre/post tests) and produce a full statistical analysis section in the publication report:

- **Heterogeneous Excel layouts supported** — patients in rows or columns, multi-level PRE/POST headers, sub-categories per muscle, missing codes (NT/NA/NC). The schema detection agent (Agent 6) absorbs whatever layout the clinician used and standardizes it to canonical long format
- **Deterministic statistics** — descriptive (mean ± std, median, IQR per timepoint) and inferential (paired t-test or Wilcoxon signed-rank, depending on data type and normality)
- **Effect sizes** — Cohen's d for parametric, r for non-parametric
- **AI never invents numbers** — Agent 7 only writes prose around pre-computed values, with explicit instructions to cite verbatim
- **Stats figures** — pre/post boxplots per test, individual change spaghetti plots, forest plot of effect sizes
- **Raw stats summary appended** so reviewers can verify every cited number

### Cohort analysis (multi-patient)

Automatically activated when the input file contains 2 or more patient sheets:

- Descriptive statistics across the cohort: means ± std for sessions/patient, exercises/patient, volume/session
- Aggregated objective and muscle distributions across all patients
- Per-patient breakdown table
- Additional figures: exercises per patient, volume boxplot across patients, objectives heatmap
- Dedicated **Cohort Analysis** section in the publication report

### Cost estimation & confirmation

Before any AI processing, the tool estimates the total API cost based on:

- Number of rows, sessions, and patients in the validated input
- Provider and model selected (pricing table updatable in `cost_estimator.py`)
- Per-agent token averages (extractor, reviewer, synthesis, publication, clinical)

If the estimate exceeds **$1.00**, the user is asked to confirm before proceeding — protects against expensive accidental runs (especially with Anthropic models).

### Audit trail / provenance log

Every AI call is logged to a timestamped JSONL file in `output/audit/audit_<timestamp>.jsonl`:

- Agent name, provider, model, full prompt, raw response, parsed result
- ISO timestamp + session ID for every entry
- One JSON object per line — easy to grep, replay, or analyse

Critical for **scientific reproducibility**: any extracted data point can be traced back to the exact prompt and response that produced it.

### Pre-flight data validation (no AI, no token cost)

A deterministic validator runs **before any AI call** to catch issues early and save API costs:

- Drops rows with empty/NaN exercise cells
- Drops exact duplicate rows
- Flags very short exercise descriptions (<5 chars)
- Flags missing patient IDs and missing session columns
- Blocks the pipeline if no exercise column is found or the file is empty
- Prints a clear summary per sheet (rows kept vs removed, warnings, critical errors)

### Automatic language detection (clinical mode only)

The clinical report mode auto-detects the language of the input notes and writes the full document in that language:

- Supported: French, English, Spanish, Italian, German, Portuguese, Dutch (via `langdetect`)
- Default fallback: English, if detection is ambiguous
- Applied **only** to the clinical report — publication mode stays in English (scientific standard)
- Detection runs on the exercise descriptions before AI calls, then forced in the prompt

### Infrastructure

- Structured logging to `logs/lobster.log`
- 276 unit tests (pytest, with CI on GitHub Actions)
- Docker ready — includes MongoDB and PostgreSQL services

---

## Project Structure

```
LOBSTER/
├── Dockerfile
├── docker-compose.yml
├── LICENSE
├── README.md
├── requirements.txt
├── pyproject.toml
└── backend/
    ├── src/
    │   ├── main.py                    # Entry point (interactive ETL)
    │   ├── cli.py                     # CLI entry point (click)
    │   ├── detector.py                # File type detection & verification
    │   ├── reader.py                  # File reading (CSV, Excel, JSON)
    │   ├── cleaner.py                 # Interactive cleaning pipeline
    │   ├── exporter.py                # Multi-format export
    │   ├── pipeline.py                # Pipeline save & replay
    │   ├── reporter.py                # Cleaning report generation
    │   ├── analyzer.py                # AI analyzer entry point
    │   ├── agent_orchestrator.py      # Chains Agents 1 → 2 → 3
    │   ├── exercise_extractor.py      # Agent 1 — AI extraction (Mistral + Anthropic)
    │   ├── reviewer_agent.py          # Agent 2 — Clinical review & correction
    │   ├── synthesis_agent.py         # Agent 3 — Per-session synthesis
    │   ├── publication_agent.py       # Agent 4 — Scientific publication writer
    │   ├── clinical_writer_agent.py   # Agent 5 — Clinical follow-up writer
    │   ├── cohort_analyzer.py         # Multi-patient cohort statistics
    │   ├── language_detector.py       # Auto language detection (clinical mode)
    │   ├── data_validator.py          # Pre-flight data validation (no AI)
    │   ├── cost_estimator.py          # Pre-flight API cost estimation
    │   ├── audit_logger.py            # JSONL audit trail of all AI calls (thread-safe)
    │   ├── prompt_cache.py            # Content-addressed response cache (TTL 30d)
    │   ├── assessment_loader.py       # Loads heterogeneous assessment Excel files
    │   ├── assessment_schema_agent.py # Agent 6 — schema detection (AI)
    │   ├── statistical_analyzer.py    # Deterministic stats engine (scipy/statsmodels)
    │   ├── stats_figures.py           # Stats figures (boxplot, change, forest plot)
    │   ├── stats_writer_agent.py      # Agent 7 — narrative stats interpretation (AI)
    │   ├── report_figures.py          # Shared figures (matplotlib → SVG + PNG)
    │   ├── report_exporter.py         # Shared report exporter (.pdf / .docx)
    │   ├── reference_loader.py        # Exercise, muscle, objective & protocol loader
    │   └── logger.py                  # Logging configuration
    ├── references/
    │   └── exercises_reference.xlsx   # Exercise, muscle & objective reference data
    ├── templates/
    │   └── template_patient.xlsx      # Downloadable patient file template
    └── tests/
        ├── test_detector.py
        ├── test_cleaner.py
        ├── test_pipeline.py
        ├── test_reporter.py
        ├── test_cli.py
        ├── test_analyzer.py
        ├── test_exercise_extractor.py
        ├── test_reviewer_agent.py
        ├── test_synthesis_agent.py
        ├── test_cohort_analyzer.py
        ├── test_language_detector.py
        ├── test_data_validator.py
        ├── test_cost_estimator.py
        ├── test_audit_logger.py
        ├── test_prompt_cache.py
        ├── test_parallelism.py
        ├── test_integration_orchestrator.py
        ├── test_assessment_loader.py
        ├── test_statistical_analyzer.py
        ├── test_stats_figures.py
        ├── test_report_figures.py
        ├── test_report_exporter.py
        └── test_files/
```

---

## Getting Started

### Option 1 — Local

**Prerequisites:** Python 3.12+, pip

```bash
git clone https://github.com/BerMud4X/lobster.git
cd lobster
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd backend/src
python main.py
```

### CLI Usage

```bash
cd backend/src

# Run the full ETL pipeline interactively (read → clean → export)
python cli.py run --input path/to/file.csv

# Detect file type only
python cli.py detect --input path/to/file.csv

# Read and clean interactively, save pipeline and report
python cli.py clean --input path/to/file.csv --save-pipeline output/pipeline.json --report output/report

# Export directly to a format
python cli.py export --input path/to/file.csv --format csv

# Replay a saved pipeline automatically
python cli.py replay --pipeline output/pipeline.json

# Show all commands
python cli.py --help
```

### AI Analyzer Usage

#### Excel file format

Download the template to get started: [template_patient.xlsx](backend/templates/template_patient.xlsx)

The file must contain:

- **One sheet per patient** (named with the patient ID, e.g. `P001`) with columns: `patient_id`, `session`, `date`, `exercise`
- **One optional `protocole` sheet** for research protocol context:

| champ           | valeur                                            |
| --------------- | ------------------------------------------------- |
| protocole       | Rééducation neurologique post-AVC phase subaiguë  |
| obj_principal   | FUNC                                              |
| obj_secondaires | STR, LOAD                                         |

If the `protocole` sheet is present, the AI agents will use it to assign and validate therapeutic objectives. If absent, the pipeline runs without protocol context.

#### Commands

A single command runs the whole pipeline — everything else is fully interactive:

```bash
cd backend/src
python cli.py analyze --input path/to/clinical_notes.xlsx
```

The CLI will interactively ask:

1. **Provider & model** (RGPD notice shown every time)
2. **Sheet selection** (if multi-sheet Excel)
3. **Save exercises to CSV?** — yes/no, then output path
4. **Generate a report?** — yes/no, then:
   - **Mode** — publication (scientific) or clinical (follow-up)
   - **Format** — PDF or Word (.docx)
   - **Output path**

Outputs produced:

- **Structured exercise table** (CSV) — one row per exercise with: patient ID, session, exercise name, code, code_base, objective, protocol objectives, muscles (top 3), assistance, series, repetitions, duration, review decision and confidence score
- **Per-session clinical summary** printed to console (from Agent 3)
- **Final report** (PDF or DOCX) generated by Agent 4 or 5 with automatic figures
- **Standalone figures** (`.svg`) in a `figures/` subfolder — ready to drop into a publication

### API Keys (AI Analyzer)

Create a `.env` file at the project root:

```env
MISTRAL_API_KEY=your_mistral_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

You only need to fill in the key for the provider you want to use.

- Mistral API key: [console.mistral.ai](https://console.mistral.ai)
- Anthropic API key: [console.anthropic.com](https://console.anthropic.com)

### Option 2 — Docker

```bash
git clone https://github.com/BerMud4X/lobster.git
cd lobster
docker compose up --build
docker compose run lobster
```

> MongoDB and PostgreSQL are automatically available as export targets when using Docker.

---

## Running Tests

```bash
cd backend/tests
python -m pytest -v
```

---

## Roadmap

### v0.1.0-alpha ✅

- [x] File detection (CSV, Excel, JSON)
- [x] Interactive cleaning pipeline
- [x] Multi-format export (CSV, Parquet, DuckDB, SQL, MongoDB)
- [x] Pipeline save & replay
- [x] Cleaning report (text, JSON, HTML)
- [x] Logging
- [x] Docker configuration

### v0.3.0-alpha ✅

- [x] CLI with click
- [x] AI exercise analyzer (clinical free-text → structured data)
- [x] Multi-provider AI: Mistral (EU/RGPD) + Anthropic Claude
- [x] BYOK model (bring your own API key)
- [x] RGPD notice at provider selection
- [x] 86 unit tests

### v0.4.0-alpha ✅

- [x] 5-agent agentic pipeline (Extractor → Reviewer → Synthesis → Publication / Clinical Writer)
- [x] Agent 2: clinical review with auto-correction and retry loop
- [x] Agent 3: per-session clinical synthesis (objective, intensity, narrative, recommendations)
- [x] Agent 4: scientific publication writer (abstract, context, interventions, results, discussion)
- [x] Agent 5: clinical follow-up writer (per-patient observation record)
- [x] Automatic figures (objectives, muscles, code_base, volume) as `.svg` + embedded `.png`
- [x] PDF and DOCX export with full Unicode support (DejaVu font)
- [x] Research protocol support: primary + secondary objectives per patient file
- [x] Series/repetitions distinction in extraction
- [x] Therapeutic objectives reference (sheet `Objecif` in Excel reference)
- [x] Fully interactive CLI (one command, everything asked at runtime)
- [x] Multi-sheet ETL support without merge (main.py + CLI)
- [x] Downloadable Excel patient template
- [x] Cohort analysis: multi-patient statistics + comparative figures (boxplot, heatmap, per-patient)
- [x] Automatic language detection for clinical reports (FR/EN/ES/IT/DE/PT/NL)
- [x] Deterministic pre-flight data validation (saves API costs by catching bad data early)
- [x] Pre-flight API cost estimation with confirmation prompt above $1
- [x] Audit trail / provenance log (JSONL) — every AI call recorded for reproducibility
- [x] **Quantitative assessments (Phase 1)** — Agent 6 schema detector + deterministic stats engine + Agent 7 stats writer + auto figures (boxplot, change, forest plot)
- [x] 249 unit tests

### v0.4.2-alpha ✅

- [x] **Prompt/response cache** — content-addressed (`output/cache/*.json`), 30-day TTL, 16-char SHA256 keys. Re-running on the same input file is free (0 API calls on cache hits). Disable via `LOBSTER_CACHE=false`
- [x] **Parallel extract+review** — orchestrator uses `ThreadPoolExecutor` (default 5 workers, tunable via `LOBSTER_WORKERS`). 10 rows × 0.05s latency goes from 0.5s sequential to ~0.15s
- [x] **Per-session synthesis** — Agent 3 now called once per unique session (was once per row), saving N−1 API calls on multi-row-per-session inputs
- [x] **Thread-safe audit logger** — `Lock` around JSONL writes so parallel agent calls don't corrupt the log
- [x] **Integration test** — full orchestrator pipeline tested end-to-end with all 3 agents mocked (guards against refactor regressions)
- [x] **GitHub Actions CI** — pytest runs on every push & PR to `main`/`develop`
- [x] 276 unit tests (+27)

### v0.4.1-alpha ✅

- [x] Hotfix: `main.py` ETL flow skips the `protocole` metadata sheet instead of treating it as data
- [x] Hotfix: defensive validation of Agent 6 output (malformed AI responses no longer crash the loader)
- [x] Hotfix: `pyproject.toml` updated with all v0.4 dependencies (scipy, statsmodels, matplotlib, langdetect, python-docx, fpdf2, mistralai, anthropic, python-dotenv)
- [x] README markdown lint warnings cleaned (blanks around headings and lists)

### v0.5.0 — Planned

- [ ] Quantitative assessments (Phase 2): DOCX and PDF support (currently Excel only)
- [ ] Multi-timepoint stats: repeated-measures ANOVA, Friedman, retention analysis
- [ ] Comparison mode: intervention vs control groups in the protocole sheet
- [ ] CI/CD via GitHub Actions
- [ ] Real-world dataset validation (50+ patients, AI vs human agreement metrics)

### v1.0.0 — Future

- [ ] SaaS version
- [ ] Plugin system for custom transformations
- [ ] Multi-language support

---

## Contributing

Contributions are welcome! Please open an issue first to discuss what you would like to change.

1. Fork the project
2. Create your branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
