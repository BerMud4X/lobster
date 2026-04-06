import pytest
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cleaner import (
    replace_zeros,
    handle_missing,
    remove_duplicates,
    fix_types,
    trim_whitespace,
    standardize_case,
)


# --- Fixtures ---

@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "name": ["  Alice  ", "Bob", "Charlie", "Bob"],
        "age": [30, 0, 35, 0],
        "city": ["Paris", "Lyon", " Marseille ", "Lyon"],
        "score": [0.0, 85.5, 0.0, 85.5]
    })

@pytest.fixture
def df_with_missing():
    return pd.DataFrame({
        "name": ["Alice", None, "Charlie"],
        "age": [30, 25, None],
        "city": ["Paris", "Lyon", "Marseille"]
    })


# --- replace_zeros ---

def test_replace_zeros_all(monkeypatch, sample_df):
    monkeypatch.setattr('builtins.input', lambda _: 'all')
    result = replace_zeros(sample_df.copy())
    assert result["age"].isna().sum() == 2
    assert result["score"].isna().sum() == 2

def test_replace_zeros_none(monkeypatch, sample_df):
    monkeypatch.setattr('builtins.input', lambda _: 'none')
    result = replace_zeros(sample_df.copy())
    assert (result["age"] == 0).sum() == 2

def test_replace_zeros_specific_column(monkeypatch, sample_df):
    monkeypatch.setattr('builtins.input', lambda _: 'age')
    result = replace_zeros(sample_df.copy())
    assert result["age"].isna().sum() == 2
    assert (result["score"] == 0.0).sum() == 2


# --- handle_missing ---

def test_handle_missing_drop_rows(monkeypatch, df_with_missing):
    monkeypatch.setattr('builtins.input', lambda _: 'drop_rows')
    result = handle_missing(df_with_missing.copy())
    assert len(result) == 1

def test_handle_missing_drop_cols(monkeypatch, df_with_missing):
    monkeypatch.setattr('builtins.input', lambda _: 'drop_cols')
    result = handle_missing(df_with_missing.copy())
    assert "name" not in result.columns
    assert "age" not in result.columns
    assert "city" in result.columns

def test_handle_missing_fill_custom(monkeypatch, df_with_missing):
    responses = iter(['fill', 'unknown'])
    monkeypatch.setattr('builtins.input', lambda _: next(responses))
    result = handle_missing(df_with_missing.copy())
    assert result["name"].isna().sum() == 0

def test_handle_missing_no_missing(monkeypatch):
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = handle_missing(df.copy())
    assert result.equals(df)


# --- remove_duplicates ---

def test_remove_duplicates_yes(monkeypatch, sample_df):
    monkeypatch.setattr('builtins.input', lambda _: 'yes')
    result = remove_duplicates(sample_df.copy())
    assert len(result) == 3

def test_remove_duplicates_no(monkeypatch, sample_df):
    monkeypatch.setattr('builtins.input', lambda _: 'no')
    result = remove_duplicates(sample_df.copy())
    assert len(result) == 4

def test_remove_duplicates_none(monkeypatch):
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = remove_duplicates(df.copy())
    assert len(result) == 3


# --- trim_whitespace ---

def test_trim_whitespace(sample_df):
    result = trim_whitespace(sample_df.copy())
    assert result["name"].tolist() == ["Alice", "Bob", "Charlie", "Bob"]
    assert result["city"].tolist() == ["Paris", "Lyon", "Marseille", "Lyon"]


# --- standardize_case ---

def test_standardize_case_lowercase(monkeypatch, sample_df):
    monkeypatch.setattr('builtins.input', lambda _: 'lowercase')
    result = standardize_case(sample_df.copy())
    assert result["name"].str.islower().all()

def test_standardize_case_uppercase(monkeypatch, sample_df):
    monkeypatch.setattr('builtins.input', lambda _: 'uppercase')
    result = standardize_case(sample_df.copy())
    assert result["name"].str.isupper().all()

def test_standardize_case_none(monkeypatch, sample_df):
    monkeypatch.setattr('builtins.input', lambda _: 'none')
    result = standardize_case(sample_df.copy())
    assert result["name"].tolist() == sample_df["name"].tolist()


# --- fix_types ---

def test_fix_types_no(monkeypatch, sample_df):
    monkeypatch.setattr('builtins.input', lambda _: 'no')
    result = fix_types(sample_df.copy())
    assert result.dtypes["age"] == sample_df.dtypes["age"]

def test_fix_types_convert_to_str(monkeypatch, sample_df):
    responses = iter(['yes', 'age', 'str', 'done'])
    monkeypatch.setattr('builtins.input', lambda _: next(responses))
    result = fix_types(sample_df.copy())
    assert result["age"].dtype.name in ('object', 'string', 'str')
