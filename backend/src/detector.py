from pathlib import Path
from logger import logger


def detect_file_type(file_path):
    """Detects the file type based on its extension."""
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext == '.csv':
        logger.info(f"Extension detected: csv ({file_path})")
        return 'csv'
    elif ext in ('.xlsx', '.xls'):
        logger.info(f"Extension detected: excel ({file_path})")
        return 'excel'
    elif ext == '.json':
        logger.info(f"Extension detected: json ({file_path})")
        return 'json'
    else:
        logger.warning(f"Unsupported extension '{ext}' for file: {file_path}")
        return 'format not supported yet'


def verify_file(file_path):
    """Verifies that the file exists and its content matches its extension."""
    if not Path(file_path).is_file():
        logger.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"File not found or is not a file: {file_path}")

    with open(file_path, 'rb') as f:
        header = f.read(4)

    if header.startswith(b'PK\x03\x04'):
        logger.info(f"Magic bytes match: excel ({file_path})")
        return 'excel'
    elif header.startswith(b'\x7B') or header.startswith(b'\x5B'):
        logger.info(f"Magic bytes match: json ({file_path})")
        return 'json'
    else:
        logger.info(f"No magic bytes found, assuming csv ({file_path})")
        return 'csv'


def get_file_type(file_path):
    """Combines detect_file_type and verify_file to confirm extension matches content."""
    ext_type = detect_file_type(file_path)
    if ext_type == 'format not supported yet':
        logger.error(f"Format not supported: {file_path}")
        raise ValueError(f"Format not supported: {file_path}")

    content_type = verify_file(file_path)

    if ext_type != content_type:
        logger.error(f"Extension mismatch — extension says '{ext_type}' but content says '{content_type}': {file_path}")
        raise ValueError(f"Extension does not match file content: {file_path}")

    logger.info(f"File type confirmed: {ext_type} ({file_path})")
    return ext_type


# Example usage
if __name__ == "__main__":
    files = [
        "../tests/test_files/data.csv",
        "../tests/test_files/data.json",
        "../tests/test_files/data.xlsx",
        "../tests/test_files/fake_csv.csv",
    ]

    for f in files:
        try:
            result = get_file_type(f)
            print(f"{f} → {result}")
        except Exception as e:
            print(f"{f} → ERROR: {e}")
