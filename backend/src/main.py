from reader import read_file
from cleaner import clean
from exporter import export
from pipeline import Pipeline
from reporter import generate_report, save_report


def main():
    print("=== LOBSTER ETL ===")

    # check if user wants to replay an existing pipeline
    mode = input("New pipeline or replay? (new/replay): ").strip().lower()

    if mode == 'replay':
        pipeline_path = input("Pipeline file path (.json): ").strip()
        pipeline = Pipeline.load(pipeline_path)
        file_path = pipeline.get("read_file")["file_path"]
        print(f"\nReplaying pipeline on: {file_path}")
    else:
        pipeline = Pipeline()
        file_path = input("Enter the path to your file: ").strip()

    # step 1 — read
    print("\n=== STEP 1: Reading file ===")
    try:
        result = read_file(file_path)
        pipeline.record("read_file", {"file_path": file_path})
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}")
        return

    # Multi-sheet without merge → process each sheet independently
    if isinstance(result, dict):
        for sheet_name, df in result.items():
            print(f"\n--- Sheet: {sheet_name} | Shape: {df.shape} ---")
            df_before = df.copy()
            sheet_pipeline = Pipeline()
            sheet_pipeline.record("read_file", {"file_path": file_path, "sheet": sheet_name})

            print("\n=== STEP 2: Cleaning data ===")
            df = clean(df, pipeline=sheet_pipeline, replay=(mode == 'replay'))

            print("\n=== STEP 3: Exporting data ===")
            export(df)

            save_p = input("\nSave pipeline for this sheet? (yes/no): ").strip().lower()
            if save_p == 'yes':
                p_path = input(f"Pipeline output path for '{sheet_name}': ").strip()
                sheet_pipeline.save(p_path)

            save_r = input("\nGenerate cleaning report for this sheet? (yes/no): ").strip().lower()
            if save_r == 'yes':
                report = generate_report(df_before, df, sheet_pipeline.steps)
                r_path = input("Report output path without extension: ").strip()
                save_report(report, r_path)

        print("\n=== PIPELINE COMPLETE ===")
        return

    df = result
    print(f"File loaded successfully. Shape: {df.shape}")

    # snapshot before cleaning
    df_before = df.copy()

    # step 2 — clean
    print("\n=== STEP 2: Cleaning data ===")
    df = clean(df, pipeline=pipeline, replay=(mode == 'replay'))

    # step 3 — export
    print("\n=== STEP 3: Exporting data ===")
    export(df)

    # save pipeline
    save_p = input("\nSave pipeline for future replay? (yes/no): ").strip().lower()
    if save_p == 'yes':
        p_path = input("Pipeline output path (e.g. output/pipeline.json): ").strip()
        pipeline.save(p_path)

    # generate report
    save_r = input("\nGenerate cleaning report? (yes/no): ").strip().lower()
    if save_r == 'yes':
        report = generate_report(df_before, df, pipeline.steps)
        r_path = input("Report output path without extension (e.g. output/report): ").strip()
        save_report(report, r_path)

    print("\n=== PIPELINE COMPLETE ===")


if __name__ == "__main__":
    main()
