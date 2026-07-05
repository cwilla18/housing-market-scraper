# Housing Market Scraper

A small Python project to parse and analyze housing market data from JSON exports.

## Summary

This repository contains a lightweight parser that reads housing data, normalizes fields, and provides a simple programmatic API for downstream analysis or export.

## Features

- Parse local JSON data exports (example: `src/housing-parser/Json/data.json`).
- Normalize and validate housing records.
- Minimal, dependency-light design for easy integration.

## Requirements

- Python 3.10 or newer

## Quickstart

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
.venv\Scripts\Activate.ps1 # Windows PowerShell
```

2. Install dependencies (if you add any; none required by default):

```bash
pip install -r requirements.txt  # optional
```

3. Run the parser from the project root:

```bash
python -m src.housing-parser.main
```

## Project layout

- `src/housing-parser/` — package source
	- `main.py` — CLI / entry point
	- `parser.py` — parsing logic
	- `model.py` — data models
	- `config.py` — configuration helpers
	- `jsonImport.py` — JSON import utilities
	- `Json/data.json` — example dataset

## Example

Run the package to parse the example dataset and print a summary. The entrypoint currently reads `src/housing-parser/Json/data.json` by default.

## Development

- Follow the Quickstart to set up a virtualenv.
- Add a `requirements.txt` if you introduce third-party packages.

## Contributing

Contributions are welcome. Open issues for bugs or feature requests and submit pull requests for fixes.

## License

MIT License — include a LICENSE file if you intend to publish under this license.
