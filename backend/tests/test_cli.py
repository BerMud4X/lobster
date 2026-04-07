import pytest
import sys
import pandas as pd
from pathlib import Path
from unittest.mock import patch
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
    assert "0.3.0-alpha" in result.output


# --- analyze ---

FAKE_DF = pd.DataFrame([{
    "patient_id": "P001",
    "session": "Seance 1",
    "exercise_num": 1,
    "exercise_name": "Knee locking",
    "code": "KnL",
    "code_base": "Functional",
    "muscles": "Gluteus maximus",
    "assistance": "parallel bars",
    "repetitions": None,
    "time": None,
}])

def test_analyze_help():
    result = runner.invoke(cli, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.output
    assert "--provider" in result.output
    assert "--output" in result.output

@patch("cli.analyze_file", return_value=FAKE_DF)
def test_analyze_runs(mock_analyze):
    result = runner.invoke(cli, [
        "analyze", "--input", str(TEST_FILES / "test_patient.xlsx"),
        "--provider", "Mistral", "--model", "open-mistral-7b"
    ])
    assert result.exit_code == 0
    assert "Knee locking" in result.output
    mock_analyze.assert_called_once()

@patch("cli.analyze_file", return_value=FAKE_DF)
def test_analyze_saves_output(mock_analyze, tmp_path):
    out = tmp_path / "result.csv"
    result = runner.invoke(cli, [
        "analyze", "--input", str(TEST_FILES / "test_patient.xlsx"),
        "--provider", "Mistral", "--model", "open-mistral-7b",
        "--output", str(out)
    ])
    assert result.exit_code == 0
    assert out.exists()
    assert "Saved to" in result.output

@patch("cli.analyze_file", return_value=pd.DataFrame())
def test_analyze_empty_result(mock_analyze):
    result = runner.invoke(cli, [
        "analyze", "--input", str(TEST_FILES / "test_patient.xlsx"),
        "--provider", "Mistral", "--model", "open-mistral-7b"
    ])
    assert result.exit_code == 0
    assert "No exercises extracted" in result.output

@patch("cli.analyze_file", side_effect=ValueError("bad file"))
def test_analyze_error(mock_analyze):
    result = runner.invoke(cli, [
        "analyze", "--input", "nonexistent.xlsx",
        "--provider", "Mistral", "--model", "open-mistral-7b"
    ])
    assert "ERROR" in result.output

def test_analyze_invalid_provider():
    result = runner.invoke(cli, [
        "analyze", "--input", str(TEST_FILES / "test_patient.xlsx"),
        "--provider", "InvalidProvider"
    ])
    assert result.exit_code != 0
