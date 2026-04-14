import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from report_exporter import export_docx, export_pdf, export_report, _get_dejavu_fonts


def _make_fake_figure(tmp_path: Path, name: str = "test") -> tuple[Path, Path]:
    """Create a tiny SVG + PNG pair for embedding tests."""
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 4, 2])
    svg = tmp_path / f"{name}.svg"
    png = tmp_path / f"{name}.png"
    fig.savefig(svg, format="svg")
    fig.savefig(png, format="png")
    plt.close(fig)
    return svg, png


SAMPLE_SECTIONS = [
    {"heading": "Abstract", "body": "Étude sur la rééducation post-AVC — résumé structuré."},
    {"heading": "Methods", "body": "Trois séances de physiothérapie ont été analysées."},
]


# --- Fonts ---

def test_dejavu_fonts_exist():
    regular, bold, italic = _get_dejavu_fonts()
    assert Path(regular).exists()
    assert Path(bold).exists()
    assert Path(italic).exists()


# --- .docx ---

def test_export_docx_creates_file(tmp_path):
    out = tmp_path / "report.docx"
    result = export_docx(SAMPLE_SECTIONS, {}, out, title="Test Report")
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0

def test_export_docx_with_figures(tmp_path):
    svg, png = _make_fake_figure(tmp_path)
    out = tmp_path / "report.docx"
    export_docx(SAMPLE_SECTIONS, {"test": (svg, png)}, out, title="With Figures")
    assert out.exists()

def test_export_docx_creates_parent_dir(tmp_path):
    out = tmp_path / "deep" / "nested" / "report.docx"
    export_docx(SAMPLE_SECTIONS, {}, out)
    assert out.exists()


# --- .pdf ---

def test_export_pdf_creates_file(tmp_path):
    out = tmp_path / "report.pdf"
    result = export_pdf(SAMPLE_SECTIONS, {}, out, title="Test PDF")
    assert result == out
    assert out.exists()

def test_export_pdf_handles_unicode(tmp_path):
    """Unicode characters (—, é, à) should not raise."""
    sections = [{"heading": "Résumé", "body": "Séance — intensité modérée. Référence à l'étude."}]
    out = tmp_path / "unicode.pdf"
    export_pdf(sections, {}, out, title="Rééducation — Étude clinique")
    assert out.exists()

def test_export_pdf_with_figures(tmp_path):
    svg, png = _make_fake_figure(tmp_path)
    out = tmp_path / "report.pdf"
    export_pdf(SAMPLE_SECTIONS, {"vol": (svg, png)}, out)
    assert out.exists()


# --- export_report dispatcher ---

def test_export_report_dispatches_pdf(tmp_path):
    out = tmp_path / "r.pdf"
    result = export_report(SAMPLE_SECTIONS, {}, out, fmt="pdf")
    assert result.suffix == ".pdf"
    assert result.exists()

def test_export_report_dispatches_docx(tmp_path):
    out = tmp_path / "r.docx"
    result = export_report(SAMPLE_SECTIONS, {}, out, fmt="docx")
    assert result.suffix == ".docx"
    assert result.exists()

def test_export_report_adds_extension_if_missing(tmp_path):
    out = str(tmp_path / "report_noext")
    result = export_report(SAMPLE_SECTIONS, {}, out, fmt="pdf")
    assert result.suffix == ".pdf"
    assert result.exists()
