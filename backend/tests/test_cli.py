import pytest
import sys
from pathlib import Path
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cli import cli

TEST_FILES = Path(__file__).parent / "test_files"
runner = CliRunner()


# --- detect ---

def test_detect_csv():
    result = runner.invoke(cli, ["detect", "--input", str(TEST_FILES / "data.csv")])
    assert result.exit_code == 0
    assert "csv" in result.output

def test_detect_excel():
    result = runner.invoke(cli, ["detect", "--input", str(TEST_FILES / "data.xlsx")])
    assert result.exit_code == 0
    assert "excel" in result.output

def test_detect_json():
    result = runner.invoke(cli, ["detect", "--input", str(TEST_FILES / "data.json")])
    assert result.exit_code == 0
    assert "json" in result.output

def test_detect_mismatch():
    result = runner.invoke(cli, ["detect", "--input", str(TEST_FILES / "fake_csv.csv")])
    assert "ERROR" in result.output

def test_detect_missing_file():
    result = runner.invoke(cli, ["detect", "--input", "nonexistent.csv"])
    assert "ERROR" in result.output


# --- --help ---

def test_help():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "LOBSTER" in result.output

def test_run_help():
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0

def test_clean_help():
    result = runner.invoke(cli, ["clean", "--help"])
    assert result.exit_code == 0

def test_export_help():
    result = runner.invoke(cli, ["export", "--help"])
    assert result.exit_code == 0

def test_replay_help():
    result = runner.invoke(cli, ["replay", "--help"])
    assert result.exit_code == 0


# --- --version ---

def test_version():
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.2.0-alpha" in result.output
