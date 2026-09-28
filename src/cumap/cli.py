"""cumap CLI. Command groups are stubbed in M0 and filled in milestone by milestone."""

from __future__ import annotations

import typer

app = typer.Typer(name="cumap", help="H420020 Conceptual Understanding Mapper.")

data_app = typer.Typer(help="Download and prepare raw datasets (SAF).")
textbook_app = typer.Typer(help="Fetch and parse the Peterson & Davie textbook source.")
gold_app = typer.Typer(help="Human-gold tooling: suggestions, validation. Never writes to data/gold/.")
labels_app = typer.Typer(help="Silver relation-level labels derived from SAF feedback (M4).")
kg_app = typer.Typer(help="Expert knowledge graph construction (M5) and expected subgraphs (M6).")
student_app = typer.Typer(help="Student answer -> graph extraction (M6).")
diagnose_app = typer.Typer(help="Alignment and diagnosis of student graphs against the expert KG (M7).")
eval_app = typer.Typer(help="Evaluation, baselines and ablations (M7).")
app_app = typer.Typer(help="Streamlit review/demo apps.")

app.add_typer(data_app, name="data")
app.add_typer(textbook_app, name="textbook")
app.add_typer(gold_app, name="gold")
app.add_typer(labels_app, name="labels")
app.add_typer(kg_app, name="kg")
app.add_typer(student_app, name="student")
app.add_typer(diagnose_app, name="diagnose")
app.add_typer(eval_app, name="eval")
app.add_typer(app_app, name="app")


def _not_implemented(command: str, milestone: str) -> None:
    typer.echo(f"`{command}` is not implemented yet (lands in {milestone}).")
    raise typer.Exit(code=0)


@data_app.command("download-saf")
def data_download_saf() -> None:
    """Download SAF Communication Networks splits to data/raw/saf/."""
    _not_implemented("cumap data download-saf", "M1")


@textbook_app.command("fetch")
def textbook_fetch() -> None:
    """Clone SystemsApproach/book at a pinned commit into data/raw/textbook/pd6/."""
    _not_implemented("cumap textbook fetch", "M1")


@textbook_app.command("parse")
def textbook_parse() -> None:
    """Parse the textbook source into data/interim/textbook_sections.jsonl."""
    _not_implemented("cumap textbook parse", "M1")


@gold_app.command("validate")
def gold_validate() -> None:
    """Validate every file under data/gold/ against the schemas and relation registry."""
    _not_implemented("cumap gold validate", "M2")


@gold_app.command("suggest-expert")
def gold_suggest_expert(qid: str = typer.Option(..., "--qid")) -> None:
    """Draft an expert subgraph suggestion for a question into data/interim/suggestions/expert/."""
    _not_implemented("cumap gold suggest-expert", "M3")


@gold_app.command("suggest-student")
def gold_suggest_student(answer_id: str = typer.Option(..., "--answer-id")) -> None:
    """Draft a student graph suggestion into data/interim/suggestions/student/."""
    _not_implemented("cumap gold suggest-student", "M3")


@labels_app.command("propositions")
def labels_propositions() -> None:
    """Split reference answers into atomic propositions."""
    _not_implemented("cumap labels propositions", "M4")


@labels_app.command("from-feedback")
def labels_from_feedback() -> None:
    """Label each proposition per answer from SAF feedback (privileged; M4 only)."""
    _not_implemented("cumap labels from-feedback", "M4")


@kg_app.command("build")
def kg_build() -> None:
    """Run the expert KG construction pipeline."""
    _not_implemented("cumap kg build", "M5")


@kg_app.command("expected-subgraphs")
def kg_expected_subgraphs() -> None:
    """Map gold propositions to KG edges to build per-question expected subgraphs."""
    _not_implemented("cumap kg expected-subgraphs", "M6")


@student_app.command("extract")
def student_extract(split: str = typer.Option(..., "--split")) -> None:
    """Extract student answer graphs for a split."""
    _not_implemented("cumap student extract", "M6")


@diagnose_app.command("run")
def diagnose_run() -> None:
    """Align student graphs to expected subgraphs and produce DiagnosisRecords."""
    _not_implemented("cumap diagnose run", "M7")


@eval_app.command("run")
def eval_run() -> None:
    """Run the full evaluation report against baselines and ablations."""
    _not_implemented("cumap eval run", "M7")


@eval_app.command("silver-agreement")
def eval_silver_agreement() -> None:
    """Agreement between silver labels and human-verified labels."""
    _not_implemented("cumap eval silver-agreement", "M4")


@app_app.command("review")
def app_review() -> None:
    """Launch the Streamlit gold/KG review app."""
    _not_implemented("cumap app review", "M3")


if __name__ == "__main__":
    app()
