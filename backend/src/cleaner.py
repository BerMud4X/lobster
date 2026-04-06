import pandas as pd
from logger import logger


def summarize(df):
    """Prints a data quality summary of the DataFrame."""
    print(f"\nShape: {df.shape[0]} rows x {df.shape[1]} columns")
    print("\nColumn types:")
    print(df.dtypes)
    print("\nMissing values:")
    print(df.isnull().sum())
    print(f"\nDuplicates: {df.duplicated().sum()}")


def replace_zeros(df, pipeline=None, replay=False):
    """Asks the user which columns should have zeros replaced with NaN."""
    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    if not numeric_cols:
        print("No numeric columns found.")
        return df

    if replay and pipeline and pipeline.has("replace_zeros"):
        params = pipeline.get("replace_zeros")
        selected = params["columns"]
        print(f"[Replay] Replace zeros in: {selected}")
    else:
        print(f"\nNumeric columns: {numeric_cols}")
        choice = input("Which columns should have zeros replaced by NaN? (all / column names separated by commas / none): ")
        if choice.strip().lower() == 'none':
            return df
        elif choice.strip().lower() == 'all':
            selected = numeric_cols
        else:
            selected = [c.strip() for c in choice.split(',')]

    df[selected] = df[selected].replace(0, pd.NA)
    logger.info(f"Zeros replaced by NaN in columns: {selected}")
    print(f"Zeros replaced by NaN in: {selected}")
    if pipeline:
        pipeline.record("replace_zeros", {"columns": selected})
    return df


def handle_missing(df, pipeline=None, replay=False):
    """Asks the user how to handle missing values."""
    missing = df.isnull().sum()
    missing = missing[missing > 0]

    if missing.empty:
        logger.info("No missing values found.")
        print("\nNo missing values found.")
        return df

    if replay and pipeline and pipeline.has("handle_missing"):
        params = pipeline.get("handle_missing")
        choice = params["method"]
        fill_value = params.get("fill_value")
        print(f"[Replay] Handle missing: {choice}")
    else:
        print(f"\nMissing values:\n{missing}")
        choice = input("How to handle missing values? (drop_rows / drop_cols / fill): ").strip().lower()
        fill_value = None

    if choice == 'drop_rows':
        df = df.dropna()
        print("Rows with missing values dropped.")
    elif choice == 'drop_cols':
        df = df.dropna(axis=1)
        print("Columns with missing values dropped.")
    elif choice == 'fill':
        if not fill_value:
            fill_value = input("Fill with (mean / median / mode / or a custom value): ").strip().lower()
        if fill_value == 'mean':
            df = df.fillna(df.mean(numeric_only=True))
        elif fill_value == 'median':
            df = df.fillna(df.median(numeric_only=True))
        elif fill_value == 'mode':
            df = df.fillna(df.mode().iloc[0])
        else:
            df = df.fillna(fill_value)
        print(f"Missing values filled with: {fill_value}")

    logger.info(f"Missing values handled: method='{choice}', fill_value='{fill_value}'")
    if pipeline:
        pipeline.record("handle_missing", {"method": choice, "fill_value": fill_value})
    return df


def remove_duplicates(df, pipeline=None, replay=False):
    """Asks the user if duplicate rows should be removed."""
    count = df.duplicated().sum()
    if count == 0:
        logger.info("No duplicates found.")
        print("\nNo duplicates found.")
        return df

    if replay and pipeline and pipeline.has("remove_duplicates"):
        params = pipeline.get("remove_duplicates")
        choice = params["remove"]
        print(f"[Replay] Remove duplicates: {choice}")
    else:
        print(f"\n{count} duplicate row(s) found.")
        choice = input("Remove duplicates? (yes/no): ").strip().lower()

    if choice == 'yes':
        df = df.drop_duplicates()
        logger.info("Duplicates removed.")
        print("Duplicates removed.")

    if pipeline:
        pipeline.record("remove_duplicates", {"remove": choice})
    return df


def fix_types(df, pipeline=None, replay=False):
    """Asks the user if any column types should be changed."""
    print(f"\nCurrent column types:\n{df.dtypes}")

    if replay and pipeline and pipeline.has("fix_types"):
        conversions = pipeline.get("fix_types")["conversions"]
        print(f"[Replay] Fix types: {conversions}")
    else:
        choice = input("Do you want to change any column type? (yes/no): ").strip().lower()
        if choice != 'yes':
            return df
        conversions = {}
        while True:
            col = input("Column name (or 'done' to finish): ").strip()
            if col.lower() == 'done':
                break
            if col not in df.columns:
                print(f"Column '{col}' not found.")
                continue
            new_type = input(f"New type for '{col}' (int / float / str / datetime): ").strip().lower()
            conversions[col] = new_type

    for col, new_type in conversions.items():
        try:
            if new_type == 'datetime':
                df[col] = pd.to_datetime(df[col])
            else:
                df[col] = df[col].astype(new_type)
            print(f"Column '{col}' converted to {new_type}.")
        except Exception as e:
            print(f"Could not convert '{col}': {e}")

    if pipeline:
        pipeline.record("fix_types", {"conversions": conversions})
    return df


def trim_whitespace(df, pipeline=None):
    """Strips leading/trailing whitespace from all string columns."""
    text_cols = df.select_dtypes(include=['object', 'str']).columns.tolist()
    if not text_cols:
        print("No text columns found.")
        return df

    df[text_cols] = df[text_cols].apply(lambda col: col.str.strip())
    logger.info(f"Whitespace trimmed in columns: {text_cols}")
    print(f"Whitespace trimmed in: {text_cols}")
    if pipeline:
        pipeline.record("trim_whitespace", {"columns": text_cols})
    return df


def standardize_case(df, pipeline=None, replay=False):
    """Asks the user how to standardize the case of string columns."""
    text_cols = df.select_dtypes(include=['object', 'str']).columns.tolist()
    if not text_cols:
        print("No text columns found.")
        return df

    if replay and pipeline and pipeline.has("standardize_case"):
        choice = pipeline.get("standardize_case")["case"]
        print(f"[Replay] Standardize case: {choice}")
    else:
        print(f"\nText columns: {text_cols}")
        choice = input("Standardize case? (lowercase / uppercase / titlecase / none): ").strip().lower()

    if choice == 'none':
        return df

    for col in text_cols:
        if choice == 'lowercase':
            df[col] = df[col].str.lower()
        elif choice == 'uppercase':
            df[col] = df[col].str.upper()
        elif choice == 'titlecase':
            df[col] = df[col].str.title()

    logger.info(f"Case standardized to '{choice}' in columns: {text_cols}")
    print(f"Case standardized to '{choice}' in: {text_cols}")
    if pipeline:
        pipeline.record("standardize_case", {"case": choice})
    return df


def clean(df, pipeline=None, replay=False):
    """Orchestrates the full interactive cleaning pipeline."""
    print("\n=== DATA SUMMARY ===")
    summarize(df)

    print("\n=== STEP 1: Replace zeros with NaN ===")
    df = replace_zeros(df, pipeline, replay)

    print("\n=== STEP 2: Handle missing values ===")
    df = handle_missing(df, pipeline, replay)

    print("\n=== STEP 3: Remove duplicates ===")
    df = remove_duplicates(df, pipeline, replay)

    print("\n=== STEP 4: Fix column types ===")
    df = fix_types(df, pipeline, replay)

    print("\n=== STEP 5: Trim whitespace ===")
    df = trim_whitespace(df, pipeline)

    print("\n=== STEP 6: Standardize case ===")
    df = standardize_case(df, pipeline, replay)

    print("\n=== CLEANING COMPLETE ===")
    summarize(df)
    return df


if __name__ == "__main__":
    from reader import read_file
    df = read_file("../tests/test_files/data.csv")
    df = clean(df)
    print(df)
