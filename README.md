<p align="center">
  <img src="backend/logo/Logo.png" alt="LOBSTER Logo" width="400"/>
</p>

<h1 align="center">LOBSTER</h1>
<h3 align="center">Data Transforming Made Easy</h3>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License MIT"/></a>
  <img src="https://img.shields.io/badge/version-0.2.0--alpha-orange.svg" alt="Version"/>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/status-alpha-red.svg" alt="Status"/>
  <img src="https://img.shields.io/badge/tests-46%20passed-brightgreen.svg" alt="Tests"/>
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

### Infrastructure
- Structured logging to `logs/lobster.log`
- 46 unit tests (pytest)
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
    │   ├── main.py         # Entry point (interactive)
    │   ├── cli.py          # CLI entry point (click)
    │   ├── detector.py     # File type detection & verification
    │   ├── reader.py       # File reading (CSV, Excel, JSON)
    │   ├── cleaner.py      # Interactive cleaning pipeline
    │   ├── exporter.py     # Multi-format export
    │   ├── pipeline.py     # Pipeline save & replay
    │   ├── reporter.py     # Cleaning report generation
    │   └── logger.py       # Logging configuration
    └── tests/
        ├── test_detector.py
        ├── test_cleaner.py
        ├── test_pipeline.py
        ├── test_reporter.py
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

# Run the full pipeline interactively
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
- [x] 46 unit tests
- [x] Docker configuration

### v0.2.0 — Planned
- [x] CLI with click
- [ ] Desktop GUI
- [ ] Pipeline scheduling
- [ ] Cloud export (AWS S3, Azure Blob)

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
