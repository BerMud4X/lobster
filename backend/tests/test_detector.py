import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from detector import detect_file_type, verify_file, get_file_type

TEST_FILES = Path(__file__).parent / "test_files"


# --- detect_file_type ---

def test_detect_csv():
    assert detect_file_type(str(TEST_FILES / "data.csv")) == "csv"

def test_detect_excel_xlsx():
    assert detect_file_type(str(TEST_FILES / "data.xlsx")) == "excel"

def test_detect_json():
    assert detect_file_type(str(TEST_FILES / "data.json")) == "json"

def test_detect_uppercase_extension():
    assert detect_file_type("data.CSV") == "csv"

def test_detect_unsupported():
    assert detect_file_type("data.pdf") == "format not supported yet"


# --- verify_file ---

def test_verify_csv():
    assert verify_file(str(TEST_FILES / "data.csv")) == "csv"

def test_verify_excel():
    assert verify_file(str(TEST_FILES / "data.xlsx")) == "excel"

def test_verify_json():
    assert verify_file(str(TEST_FILES / "data.json")) == "json"

def test_verify_file_not_found():
    with pytest.raises(FileNotFoundError):
        verify_file("nonexistent_file.csv")


# --- get_file_type ---

def test_get_file_type_csv():
    assert get_file_type(str(TEST_FILES / "data.csv")) == "csv"

def test_get_file_type_excel():
    assert get_file_type(str(TEST_FILES / "data.xlsx")) == "excel"

def test_get_file_type_json():
    assert get_file_type(str(TEST_FILES / "data.json")) == "json"

def test_get_file_type_mismatch():
    with pytest.raises(ValueError, match="Extension does not match"):
        get_file_type(str(TEST_FILES / "fake_csv.csv"))

def test_get_file_type_unsupported():
    with pytest.raises(ValueError, match="Format not supported"):
        get_file_type(str(TEST_FILES / "data.csv").replace(".csv", ".pdf"))
