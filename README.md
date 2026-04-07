<p align="center">
  <img src="backend/logo/Logo.png" alt="LOBSTER Logo" width="400"/>
</p>

<h1 align="center">LOBSTER</h1>
<h3 align="center">Data Transforming Made Easy</h3>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License MIT"/></a>
  <img src="https://img.shields.io/badge/version-0.1.0--alpha-orange.svg" alt="Version"/>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/status-alpha-red.svg" alt="Status"/>
</p>

---

## What is LOBSTER?

LOBSTER is an open source ETL tool designed for researchers to clean, transform and export data without writing code.

It guides you step by step through the full data pipeline — from raw file detection to clean, export-ready data — with full reproducibility in mind.

---

## Features

- **Auto file detection** — CSV, Excel (.xlsx, .xls), JSON
- **Content verification** — magic bytes check to ensure file integrity
- **Interactive cleaning** — replace zeros, handle missing values, remove duplicates, fix types, trim whitespace, standardize case
- **Nested JSON support** — automatic flattening of complex structures
- **Multi-sheet Excel** — select and merge sheets interactively
- **Reproducible pipelines** — save and replay cleaning steps automatically
- **Cleaning report** — before/after comparison in text, JSON or HTML
- **Multi-destination export** — CSV, Parquet (Data Lake), DuckDB (Data Warehouse), SQL (PostgreSQL / MySQL / SQLite), MongoDB

---

## Project Structure

```
LOBSTER/
├── LICENSE
├── README.md
├── requirements.txt
├── backend/
│   ├── src/
│   │   ├── main.py         # Entry point
│   │   ├── detector.py     # File type detection
│   │   ├── reader.py       # File reading
│   │   ├── cleaner.py      # Interactive cleaning
│   │   ├── exporter.py     # Multi-format export
│   │   ├── pipeline.py     # Pipeline save & replay
│   │   ├── reporter.py     # Cleaning report generation
│   │   └── logger.py       # Logging configuration
│   └── tests/
│       ├── test_detector.py
│       ├── test_cleaner.py
│       ├── test_pipeline.py
│       ├── test_reporter.py
│       └── test_files/
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
git clone https://github.com/your-username/lobster.git
cd lobster
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run

```bash
cd backend/src
python main.py
```

---

## Running Tests

```bash
cd backend/tests
python -m pytest -v
```

---

## Roadmap

- [ ] Desktop GUI (v0.2.0)
- [ ] Pipeline scheduling
- [ ] SaaS version
- [ ] Plugin system for custom transformations
- [ ] Cloud export (AWS S3, Azure Blob)

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
