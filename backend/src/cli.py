import click
from reader import read_file
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

        df = read_file(input)
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
@click.option("--output", "-o", default=None, help="Save extracted exercises to this CSV file.")
@click.option("--provider", "-p",
              type=click.Choice(["Mistral", "Anthropic"], case_sensitive=True),
              default=None, help="AI provider to use (default: interactive selection).")
@click.option("--model", "-m", default=None, help="Model ID to use (skips interactive selection).")
def analyze(input, output, provider, model):
    """Extract structured exercise data from a clinical file using AI."""
    try:
        df = analyze_file(input, model=model, provider=provider)

        if df.empty:
            click.echo("No exercises extracted.")
            return

        click.echo(f"\n{df.to_string(index=False)}")

        if output:
            df.to_csv(output, index=False)
            click.echo(f"\nSaved to: {output}")
            logger.info(f"CLI analyze: saved {len(df)} records to {output}")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        logger.error(f"CLI analyze error: {e}")


if __name__ == "__main__":
    cli()
