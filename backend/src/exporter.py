from pathlib import Path
from logger import logger


def export_csv(df):
    """Exports the DataFrame to a sorted CSV file."""
    print(f"\nAvailable columns: {df.columns.tolist()}")
    sort_col = input("Sort by which column? (or press Enter to skip): ").strip()

    if sort_col and sort_col in df.columns:
        order = input("Ascending or descending? (asc/desc): ").strip().lower()
        ascending = order != 'desc'
        df = df.sort_values(by=sort_col, ascending=ascending)

    output_path = input("Output file path (e.g. output/data_clean.csv): ").strip()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8')
    logger.info(f"CSV exported to: {output_path}")
    print(f"CSV saved to: {output_path}")


def export_parquet(df):
    """Exports the DataFrame to a Parquet file (Data Lake)."""
    output_path = input("Output file path (e.g. output/data.parquet): ").strip()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info(f"Parquet exported to: {output_path}")
    print(f"Parquet saved to: {output_path}")


def export_duckdb(df):
    """Exports the DataFrame to a DuckDB database (Data Warehouse)."""
    import duckdb

    db_path = input("DuckDB file path (e.g. output/warehouse.duckdb): ").strip()
    table_name = input("Table name: ").strip()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(db_path)
    con.execute(f"DROP TABLE IF EXISTS {table_name}")
    con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
    con.close()
    logger.info(f"DuckDB export: table '{table_name}' at {db_path}")
    print(f"Data saved to DuckDB table '{table_name}' at: {db_path}")


def export_sql(df):
    """Exports the DataFrame to a SQL database (PostgreSQL, MySQL, SQLite)."""
    from sqlalchemy import create_engine

    print("Available databases: postgresql / mysql / sqlite")
    db_type = input("Database type: ").strip().lower()

    if db_type == 'sqlite':
        db_path = input("SQLite file path (e.g. output/data.db): ").strip()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        connection_string = f"sqlite:///{db_path}"
    elif db_type == 'postgresql':
        host = input("Host (e.g. localhost): ").strip()
        port = input("Port (default 5432): ").strip() or "5432"
        db = input("Database name: ").strip()
        user = input("Username: ").strip()
        password = input("Password: ").strip()
        connection_string = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    elif db_type == 'mysql':
        host = input("Host (e.g. localhost): ").strip()
        port = input("Port (default 3306): ").strip() or "3306"
        db = input("Database name: ").strip()
        user = input("Username: ").strip()
        password = input("Password: ").strip()
        connection_string = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
    else:
        print(f"Database type '{db_type}' not supported.")
        return

    table_name = input("Table name: ").strip()
    if_exists = input("If table exists (replace / append / fail): ").strip().lower()

    engine = create_engine(connection_string)
    df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    logger.info(f"SQL export: table '{table_name}' in {db_type}")
    print(f"Data saved to '{table_name}' in {db_type} database.")


def export_mongodb(df):
    """Exports the DataFrame to a MongoDB collection."""
    from pymongo import MongoClient

    uri = input("MongoDB URI (e.g. mongodb://localhost:27017): ").strip()
    db_name = input("Database name: ").strip()
    collection_name = input("Collection name: ").strip()

    client = MongoClient(uri)
    db = client[db_name]
    collection = db[collection_name]

    records = df.to_dict(orient='records')
    collection.insert_many(records)
    client.close()
    logger.info(f"MongoDB export: {len(records)} records into collection '{collection_name}'")
    print(f"Data inserted into MongoDB collection '{collection_name}' ({len(records)} records).")


def export(df):
    """Orchestrates the export pipeline based on user choice."""
    print("\n=== EXPORT ===")
    print("Available formats:")
    print("  1 - CSV")
    print("  2 - Parquet (Data Lake)")
    print("  3 - DuckDB (Data Warehouse)")
    print("  4 - SQL (PostgreSQL / MySQL / SQLite)")
    print("  5 - MongoDB")

    choice = input("\nChoose a format (1-5): ").strip()
    logger.info(f"Export format chosen: {choice}")

    if choice == '1':
        export_csv(df)
    elif choice == '2':
        export_parquet(df)
    elif choice == '3':
        export_duckdb(df)
    elif choice == '4':
        export_sql(df)
    elif choice == '5':
        export_mongodb(df)
    else:
        logger.warning(f"Invalid export choice: {choice}")
        print(f"Invalid choice: {choice}")


if __name__ == "__main__":
    from reader import read_file
    from cleaner import clean

    df = read_file("../tests/test_files/data.csv")
    df = clean(df)
    export(df)
