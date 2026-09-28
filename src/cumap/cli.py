"""cumap CLI. Command groups are stubbed in M0 and filled in milestone by milestone."""

from __future__ import annotations

import dataclasses
import json

import typer

from cumap.config import get_settings

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
    """Download SAF Communication Networks splits to data/raw/saf/, build interim tables."""
    from cumap.data.saf import (
        add_stable_ids,
        build_question_table,
        download_saf,
        load_all_splits,
    )

    settings = get_settings()
    raw_dir = settings.resolve(settings.paths.data_raw) / "saf"
    interim_dir = settings.resolve(settings.paths.data_interim)
    interim_dir.mkdir(parents=True, exist_ok=True)

    paths = download_saf(raw_dir, loose_search_dir=settings.repo_root / "data")
    for split, path in sorted(paths.items()):
        typer.echo(f"{split}: {path}")

    all_answers = add_stable_ids(load_all_splits(raw_dir))
    all_answers.to_parquet(interim_dir / "saf_answers.parquet", index=False)
    build_question_table(all_answers).to_csv(interim_dir / "saf_questions.csv", index=False)
    typer.echo(f"{len(all_answers)} answers, {all_answers['question_id'].nunique()} distinct questions.")


@data_app.command("eda")
def data_eda() -> None:
    """Generate reports/m1_eda_saf.md from the downloaded SAF splits."""
    from cumap.data.eda import generate_eda_report

    settings = get_settings()
    raw_dir = settings.resolve(settings.paths.data_raw) / "saf"
    out_path = settings.resolve(settings.paths.reports) / "m1_eda_saf.md"
    generate_eda_report(raw_dir, out_path)
    typer.echo(f"EDA report -> {out_path}")


@textbook_app.command("fetch")
def textbook_fetch() -> None:
    """Clone SystemsApproach/book at a pinned commit into data/raw/textbook/pd6/."""
    from cumap.textbook.fetch import fetch_textbook, record_pinned_commit

    settings = get_settings()
    clone_dir = settings.resolve(settings.textbook.clone_dir)
    commit = fetch_textbook(clone_dir, settings.textbook.repo_url)

    config_path = settings.repo_root / "configs" / "default.yaml"
    record_pinned_commit(config_path, commit)
    typer.echo(f"Cloned to {clone_dir} at commit {commit}")


@textbook_app.command("parse")
def textbook_parse() -> None:
    """Parse the textbook source into data/interim/textbook_sections.jsonl."""
    from cumap.textbook.parse import parse_textbook

    settings = get_settings()
    clone_dir = settings.resolve(settings.textbook.clone_dir)
    sections = parse_textbook(clone_dir)

    interim_dir = settings.resolve(settings.paths.data_interim)
    interim_dir.mkdir(parents=True, exist_ok=True)
    out_path = interim_dir / "textbook_sections.jsonl"
    with out_path.open("w") as f:
        for section in sections:
            f.write(json.dumps(dataclasses.asdict(section)) + "\n")
    typer.echo(f"{len(sections)} sections -> {out_path}")


@textbook_app.command("coverage")
def textbook_coverage(
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int | None = typer.Option(None, "--limit"),
) -> None:
    """Top-5 sections per question (embeddings) + an LLM full/partial/none coverage guess."""
    import json as _json

    from cumap.data.saf import load_all_splits
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt
    from cumap.textbook.coverage import (
        Section,
        estimate_coverage_guess_cost,
        run_coverage_guess,
        top_k_sections_per_question,
        write_question_section_map,
    )

    settings = get_settings()
    interim_dir = settings.resolve(settings.paths.data_interim)
    raw_dir = settings.resolve(settings.paths.data_raw) / "saf"

    questions = (
        load_all_splits(raw_dir)[["question", "reference_answer"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    from cumap.data.ids import question_id as qid_fn

    questions["question_id"] = questions["question"].map(qid_fn)

    sections_path = interim_dir / "textbook_sections.jsonl"
    sections = [Section(**_json.loads(line)) for line in sections_path.read_text().splitlines()]
    sections_by_id = {s.section_id: s for s in sections}

    typer.echo(f"Embedding {len(questions)} questions and {len(sections)} sections locally...")
    matches = top_k_sections_per_question(questions, sections, settings.embeddings.model)

    if dry_run:
        estimate = estimate_coverage_guess_cost(
            questions,
            matches,
            sections_by_id,
            assumed_usd_per_1k_input_tokens=settings.llm.assumed_usd_per_1k_input_tokens,
            assumed_usd_per_1k_output_tokens=settings.llm.assumed_usd_per_1k_output_tokens,
        )
        typer.echo(f"Planned coverage-guess LLM calls: {estimate['n_calls']}")
        typer.echo(f"Estimated input tokens: {estimate['est_input_tokens']}")
        typer.echo(f"Estimated output tokens: {estimate['est_output_tokens']}")
        typer.echo(f"Estimated cost (PLACEHOLDER pricing): ${estimate['est_usd']}")
        write_question_section_map(matches, None, interim_dir / "suggestions" / "question_section_map.csv")
        typer.echo("Dry run: wrote embedding-only top-5 CSV, did NOT call the LLM.")
        raise typer.Exit(code=0)

    client = LLMClient(settings)
    prompt_template = load_prompt(settings.resolve(settings.paths.prompts), "coverage_guess", "v1")
    coverage_df = run_coverage_guess(
        client, questions, matches, sections_by_id, prompt_template=prompt_template, limit=limit
    )
    write_question_section_map(
        matches, coverage_df, interim_dir / "suggestions" / "question_section_map.csv"
    )
    typer.echo(f"Wrote coverage guesses for {len(coverage_df)} questions.")


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
