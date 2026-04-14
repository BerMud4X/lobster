import builtins
import click
from reader import read_file

input_ = builtins.input  # alias to allow monkeypatching in tests
from cleaner import clean
from exporter import export
from detector import get_file_type
from pipeline import Pipeline
from reporter import generate_report, save_report
from analyzer import analyze_file
from logger import logger


@click.group()
@click.version_option(version="0.3.0-alpha", prog_name="LOBSTER")
def cli():
    """LOBSTER — Data Transforming Made Easy.

    An open source ETL tool for researchers.
    """
    pass


@cli.command()
@click.option("--input", "-i", required=True, help="Path to the input file.")
def detect(input):
    """Detect the type of a file without processing it."""
    try:
        file_type = get_file_type(input)
        click.echo(f"File type: {file_type}")
        logger.info(f"CLI detect: {file_type} ({input})")
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        logger.error(f"CLI detect error: {e}")


@cli.command()
@click.option("--input", "-i", required=True, help="Path to the input file.")
@click.option("--save-pipeline", "-p", default=None, help="Save pipeline to this JSON file.")
@click.option("--report", "-r", default=None, help="Save cleaning report to this path (without extension).")
def clean_cmd(input, save_pipeline, report):
    """Read and clean a file interactively."""
    try:
        click.echo(f"\nReading: {input}")
        df = read_file(input)
        click.echo(f"Loaded: {df.shape[0]} rows x {df.shape[1]} columns")
        logger.info(f"CLI clean: file loaded {df.shape} ({input})")

        pipeline = Pipeline()
        df_before = df.copy()

        df = clean(df, pipeline=pipeline)

        if save_pipeline:
            pipeline.save(save_pipeline)

        if report:
            r = generate_report(df_before, df, pipeline.steps)
            save_report(r, report)

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        logger.error(f"CLI clean error: {e}")


@cli.command()
@click.option("--input", "-i", required=True, help="Path to the input file.")
@click.option("--format", "-f",
              type=click.Choice(["csv", "parquet", "duckdb", "sql", "mongodb"], case_sensitive=False),
              required=True, help="Export format.")
def export_cmd(input, format):
    """Read a file and export it directly to the chosen format."""
    try:
        click.echo(f"\nReading: {input}")
        df = read_file(input)
        click.echo(f"Loaded: {df.shape[0]} rows x {df.shape[1]} columns")
        logger.info(f"CLI export: file loaded {df.shape} ({input}), format={format}")

        # map format to choice number for export()
        format_map = {"csv": "1", "parquet": "2", "duckdb": "3", "sql": "4", "mongodb": "5"}
        import builtins
        original_input = builtins.input
        builtins.input = lambda _: format_map[format.lower()]
        export(df)
        builtins.input = original_input

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        logger.error(f"CLI export error: {e}")


@cli.command()
@click.option("--input", "-i", required=True, help="Path to the input file.")
@click.option("--save-pipeline", "-p", default=None, help="Save pipeline steps to this JSON file.")
@click.option("--report", "-r", default=None, help="Save cleaning report to this path (without extension).")
def run(input, save_pipeline, report):
    """Run the full ETL pipeline interactively (read → clean → export)."""
    try:
        click.echo(f"\n=== LOBSTER ETL ===")
        click.echo(f"Reading: {input}")

        result = read_file(input)

        # Multi-sheet without merge → process each sheet independently
        if isinstance(result, dict):
            for sheet_name, df in result.items():
                click.echo(f"\n--- Sheet: {sheet_name} ---")
                click.echo(f"Loaded: {df.shape[0]} rows x {df.shape[1]} columns")
                pipeline = Pipeline()
                df_before = df.copy()
                click.echo("\n=== CLEANING ===")
                df = clean(df, pipeline=pipeline)
                click.echo("\n=== EXPORT ===")
                export(df)
                if save_pipeline:
                    pipeline.save(save_pipeline.replace(".json", f"_{sheet_name}.json"))
                if report:
                    r = generate_report(df_before, df, pipeline.steps)
                    save_report(r, f"{report}_{sheet_name}")
            logger.info(f"CLI run: pipeline complete for {len(result)} sheets ({input})")
            click.echo("\n=== PIPELINE COMPLETE ===")
            return

        df = result
        click.echo(f"Loaded: {df.shape[0]} rows x {df.shape[1]} columns")
        logger.info(f"CLI run: file loaded {df.shape} ({input})")

        pipeline = Pipeline()
        df_before = df.copy()

        click.echo("\n=== CLEANING ===")
        df = clean(df, pipeline=pipeline)

        click.echo("\n=== EXPORT ===")
        export(df)

        if save_pipeline:
            pipeline.save(save_pipeline)

        if report:
            r = generate_report(df_before, df, pipeline.steps)
            save_report(r, report)

        logger.info(f"CLI run: pipeline complete ({input})")
        click.echo("\n=== PIPELINE COMPLETE ===")

    except (ValueError, FileNotFoundError) as e:
        click.echo(f"ERROR: {e}", err=True)
        logger.error(f"CLI run error: {e}")


@cli.command()
@click.option("--pipeline", "-p", required=True, help="Path to the pipeline JSON file.")
@click.option("--report", "-r", default=None, help="Save cleaning report to this path (without extension).")
def replay(pipeline, report):
    """Replay a saved pipeline automatically on the same file."""
    try:
        p = Pipeline.load(pipeline)
        input_path = p.get("read_file")["file_path"]

        click.echo(f"\nReplaying pipeline on: {input_path}")
        df = read_file(input_path)
        df_before = df.copy()

        df = clean(df, pipeline=p, replay=True)
        export(df)

        if report:
            r = generate_report(df_before, df, p.steps)
            save_report(r, report)

        logger.info(f"CLI replay: complete ({input_path})")
        click.echo("\n=== REPLAY COMPLETE ===")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        logger.error(f"CLI replay error: {e}")


@cli.command()
@click.option("--input", "-i", required=True, help="Path to the clinical file (CSV or Excel).")
def analyze(input):
    """Extract structured exercise data from a clinical file using AI."""
    try:
        from pathlib import Path
        from reference_loader import load_protocol

        # Step 1 — Provider & model (always interactive, RGPD compliance)
        df, syntheses, provider, model = analyze_file(input)

        if df.empty:
            click.echo("No exercises extracted.")
            return

        click.echo(f"\n{df.to_string(index=False)}")

        # Step 2 — Save exercises CSV?
        save_csv = input_("Save extracted exercises to CSV? (yes/no): ").strip().lower()
        if save_csv == "yes":
            csv_path = input_("Output CSV path (e.g. output/exercises.csv): ").strip()
            Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(csv_path, index=False)
            click.echo(f"Saved to: {csv_path}")
            logger.info(f"CLI analyze: saved {len(df)} records to {csv_path}")

        # Step 3 — Generate report?
        gen_report = input_("Generate a report? (yes/no): ").strip().lower()
        if gen_report != "yes":
            return

        click.echo("\nReport mode:")
        click.echo("  1 - Publication  (scientific writing assistant)")
        click.echo("  2 - Clinical     (follow-up & observation record)")
        mode_choice = input_("Mode (1/2): ").strip()
        report_mode = "clinical" if mode_choice == "2" else "publication"

        click.echo("\nReport format:")
        click.echo("  1 - PDF")
        click.echo("  2 - Word (.docx)")
        fmt_choice = input_("Format (1/2): ").strip()
        report_format = "docx" if fmt_choice == "2" else "pdf"

        report_path_input = input_(f"Output path (without extension, e.g. output/report): ").strip()
        report_path = str(Path(report_path_input).with_suffix(f".{report_format}"))

        protocol = load_protocol(input) if input.endswith((".xlsx", ".xls")) else {}

        # Optional assessments file (quantitative test data) — publication mode only
        assessments_df = None
        if report_mode == "publication":
            add_assessments = input_("Add an assessments file (quantitative test results)? (yes/no): ").strip().lower()
            if add_assessments == "yes":
                a_path = input_("Path to the assessments .xlsx file: ").strip()
                from assessment_loader import load_assessments
                try:
                    assessments_df, a_meta = load_assessments(a_path, model=model, provider=provider)
                    click.echo(f"  → {a_meta['n_records']} records | {len(a_meta['tests_found'])} test(s) | {a_meta['n_patients']} patient(s)")
                except Exception as ae:
                    click.echo(f"  [Warning] Could not load assessments: {ae}", err=True)
                    logger.warning(f"Assessments load failed: {ae}")

        if report_mode == "publication":
            from publication_agent import write_publication_report
            write_publication_report(
                exercises_df=df, syntheses=syntheses, protocol=protocol,
                output_path=report_path, fmt=report_format,
                model=model, provider=provider,
                assessments_df=assessments_df,
            )
        else:
            from clinical_writer_agent import write_clinical_report
            from language_detector import detect_language_from_excel
            language = detect_language_from_excel(input)
            click.echo(f"\n[Language detected] Clinical report will be written in: {language}")
            write_clinical_report(
                exercises_df=df, syntheses=syntheses, protocol=protocol,
                output_path=report_path, fmt=report_format,
                model=model, provider=provider, language=language,
            )

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        logger.error(f"CLI analyze error: {e}")


if __name__ == "__main__":
    cli()
