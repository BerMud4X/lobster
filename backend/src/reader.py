import pandas as pd
import chardet
import json

from detector import get_file_type
from logger import logger


def _check_index(df, file_path, read_func, **kwargs):
    """Checks if the first column looks like an index and asks the user."""
    if df.iloc[:, 0].is_unique:
        print(f"\nPreview:\n{df.head(3)}")
        choice = input("The first column looks like an index. Use it as index? (yes/no): ")
        if choice.strip().lower() == 'yes':
            logger.info(f"User chose to use first column as index: {file_path}")
            return read_func(file_path, index_col=0, **kwargs)
    return df


def read_csv(file_path):
    """Reads a CSV file with automatic encoding detection."""
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read())
        encoding = result['encoding']

    if encoding is None:
        logger.warning(f"Encoding not detected for: {file_path}")
        encoding = input("Encoding not detected. Enter encoding manually (e.g. utf-8, latin-1): ")
        logger.info(f"User provided encoding: {encoding}")
    else:
        logger.info(f"Encoding detected: {encoding} ({file_path})")

    try:
        df = pd.read_csv(file_path, encoding=encoding)
        logger.info(f"CSV loaded successfully: {df.shape} ({file_path})")
    except UnicodeDecodeError:
        logger.warning(f"UnicodeDecodeError with encoding '{encoding}' for: {file_path}")
        encoding = input(f"Failed with encoding '{encoding}'. Enter encoding manually (e.g. utf-8, latin-1): ")
        logger.info(f"User provided fallback encoding: {encoding}")
        df = pd.read_csv(file_path, encoding=encoding)
        logger.info(f"CSV loaded with fallback encoding: {df.shape} ({file_path})")

    return _check_index(df, file_path, pd.read_csv, encoding=encoding)


def read_excel(file_path):
    """Reads an Excel file with sheet selection and optional merge."""
    xl = pd.ExcelFile(file_path)
    sheets = xl.sheet_names
    logger.info(f"Excel file opened. Sheets available: {sheets} ({file_path})")

    print(f"Available sheets: {sheets}")
    choice = input("Which sheets do you want to load? (all / or sheet names separated by commas): ")

    if choice.strip().lower() == 'all':
        selected_sheets = sheets
    else:
        selected_sheets = [s.strip() for s in choice.split(',')]

    logger.info(f"Sheets selected: {selected_sheets}")

    dataframes = {}
    for sheet in selected_sheets:
        df = xl.parse(sheet)
        df = _check_index(df, file_path, xl.parse, sheet_name=sheet)
        dataframes[sheet] = df
        logger.info(f"Sheet '{sheet}' loaded: {df.shape}")

    if len(dataframes) == 1:
        return list(dataframes.values())[0]

    merge = input("Do you want to merge all sheets into a single DataFrame? (yes/no): ")
    if merge.strip().lower() == 'yes':
        logger.info("User chose to merge all sheets.")
        return pd.concat(dataframes.values(), ignore_index=True)
    else:
        logger.info("User chose to keep sheets separate.")
        return dataframes


def read_json(file_path):
    """Reads a JSON file and flattens nested structures automatically."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        df = pd.json_normalize(data)
        logger.info(f"JSON loaded and normalized: {df.shape} ({file_path})")
        return df
    except ValueError as e:
        logger.error(f"JSON read error: {e} ({file_path})")
        print(f"JSON read error: {e}")
        choice = input("Do you want to continue? (yes/no): ")
        if choice.strip().lower() != 'yes':
            return None
        raise


def read_file(file_path):
    """Orchestrates file reading based on detected file type."""
    file_type = get_file_type(file_path)
    logger.info(f"Starting read for file type: {file_type} ({file_path})")
    if file_type == 'csv':
        return read_csv(file_path)
    elif file_type == 'excel':
        return read_excel(file_path)
    elif file_type == 'json':
        return read_json(file_path)
    else:
        logger.error(f"Format not supported: {file_path}")
        raise ValueError(f"Format not supported: {file_path}")


if __name__ == "__main__":
    files = [
        "../tests/test_files/data.csv",
        "../tests/test_files/data.xlsx",
        "../tests/test_files/data.json",
        "../tests/test_files/data_nested.json",
    ]

    for f in files:
        print(f"\n--- {f} ---")
        try:
            df = read_file(f)
            print(df)
        except Exception as e:
            print(f"ERROR: {e}")
