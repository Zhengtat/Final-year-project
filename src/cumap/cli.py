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
def gold_validate(
    registry_version: int | None = typer.Option(
        None, "--registry", help="Force this registry version's rules on every file (e.g. 1). Default: detect per-file."
    ),
) -> None:
    """Validate every file under data/gold/ against the schemas and relation registry."""
    import json as _json

    from cumap.gold.validate import validate_gold_dir

    settings = get_settings()
    gold_dir = settings.resolve(settings.paths.data_gold)
    interim_dir = settings.resolve(settings.paths.data_interim)

    sections_by_id = {}
    sections_path = interim_dir / "textbook_sections.jsonl"
    if sections_path.exists():
        for line in sections_path.read_text().splitlines():
            row = _json.loads(line)
            sections_by_id[row["section_id"]] = row["text"]

    answers_by_id = {}
    answers_path = interim_dir / "saf_answers.parquet"
    if answers_path.exists():
        import pandas as pd

        answers_df = pd.read_parquet(answers_path, columns=["answer_id", "provided_answer"])
        answers_by_id = dict(zip(answers_df["answer_id"], answers_df["provided_answer"], strict=True))

    result = validate_gold_dir(
        gold_dir, sections_by_id=sections_by_id, answers_by_id=answers_by_id, force_version=registry_version
    )
    for hint in result.hints:
        typer.echo(hint)
    if not result.issues:
        typer.echo("cumap gold validate: OK (no issues found)")
        raise typer.Exit(code=0)

    for issue in result.issues:
        typer.echo(str(issue))
    typer.echo(f"\n{len(result.issues)} issue(s) found.")
    raise typer.Exit(code=1)


@gold_app.command("sample-answers")
def gold_sample_answers() -> None:
    """Pick ~10 answers per pilot question from train, stratified by label, fixed seed."""
    import pandas as pd

    from cumap.data.saf import drop_privileged_columns
    from cumap.gold.sample_answers import sample_pilot_answers

    settings = get_settings()
    interim_dir = settings.resolve(settings.paths.data_interim)
    answers = pd.read_parquet(interim_dir / "saf_answers.parquet")
    train = answers[answers["split"] == "train"]

    sampled, notes = sample_pilot_answers(train, settings.pilot_questions, settings.seed)
    sampled = drop_privileged_columns(sampled)  # student-graph drafting must not see feedback (rule 10)

    out_path = interim_dir / "pilot_answers.csv"
    sampled.to_csv(out_path, index=False)

    typer.echo(f"{len(sampled)} answers sampled -> {out_path}")
    for note in notes:
        typer.echo(f"  note: {note}")


@gold_app.command("suggest-expert")
def gold_suggest_expert(
    qid: str = typer.Option(None, "--qid"),
    all_pilot: bool = typer.Option(False, "--all", help="Run for every pilot question."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int | None = typer.Option(None, "--limit"),
) -> None:
    """Draft an expert subgraph suggestion for a question into data/interim/suggestions/expert/."""
    import json as _json

    import pandas as pd

    from cumap.gold.sections import section_ids_for_question
    from cumap.gold.suggest_expert import suggest_expert_subgraph_v2, write_expert_suggestion
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    interim_dir = settings.resolve(settings.paths.data_interim)
    gold_dir = settings.resolve(settings.paths.data_gold)

    qids = settings.pilot_questions if all_pilot else [qid]
    if limit is not None:
        qids = qids[:limit]
    if dry_run:
        typer.echo(f"Planned expert_subgraph LLM calls: {len(qids)}")
        raise typer.Exit(code=0)

    questions = pd.read_csv(interim_dir / "saf_questions.csv")
    sections_by_id = {}
    for line in (interim_dir / "textbook_sections.jsonl").read_text().splitlines():
        row = _json.loads(line)
        sections_by_id[row["section_id"]] = row["text"]

    client = LLMClient(settings)
    registry = RelationRegistry.from_yaml(settings.resolve(settings.relation_registry))
    # CR-001 §7.2: switched from v1 to v2 (uses the v1 registry's families/templates/
    # near-misses, outputs part_type/dimension/surface_phrase, proposes chain links).
    prompt_template = load_prompt(settings.resolve(settings.paths.prompts), "expert_subgraph", "v2")

    for q in qids:
        qrow = questions[questions["question_id"] == q].iloc[0]
        section_ids = section_ids_for_question(gold_dir, interim_dir, q)
        draft = suggest_expert_subgraph_v2(
            client,
            prompt_template,
            registry,
            question_id=q,
            question=qrow["question"],
            reference_answer=qrow["reference_answer"],
            section_ids=section_ids,
            sections_by_id=sections_by_id,
        )
        out_path = interim_dir / "suggestions" / "expert" / f"{q}.yaml"
        write_expert_suggestion(draft, out_path)
        typer.echo(
            f"{q}: {len(draft['concepts'])} concepts, {len(draft['edges'])} edges, "
            f"{len(draft['chain_links'])} chain links, {len(draft['rejected'])} rejected -> {out_path}"
        )


@gold_app.command("suggest-student")
def gold_suggest_student(
    answer_id: str = typer.Option(None, "--answer-id"),
    all_sampled: bool = typer.Option(False, "--all", help="Run for every sampled pilot answer."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int | None = typer.Option(None, "--limit"),
) -> None:
    """Draft a student graph suggestion into data/interim/suggestions/student/."""
    import pandas as pd
    import yaml as _yaml

    from cumap.gold.suggest_student import suggest_student_graph_v2, write_student_suggestion
    from cumap.llm.client import LLMClient
    from cumap.llm.prompts import load_prompt
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    interim_dir = settings.resolve(settings.paths.data_interim)
    gold_dir = settings.resolve(settings.paths.data_gold)

    pilot_answers = pd.read_csv(interim_dir / "pilot_answers.csv")
    answer_ids = pilot_answers["answer_id"].tolist() if all_sampled else [answer_id]
    if limit is not None:
        answer_ids = answer_ids[:limit]

    if dry_run:
        total_chars = pilot_answers[pilot_answers["answer_id"].isin(answer_ids)]["provided_answer"].str.len().sum()
        est_input_tokens = int(total_chars // 4) + len(answer_ids) * 200  # + known-concepts/prompt overhead
        est_output_tokens = len(answer_ids) * 250
        cost = (
            est_input_tokens / 1000 * settings.llm.assumed_usd_per_1k_input_tokens
            + est_output_tokens / 1000 * settings.llm.assumed_usd_per_1k_output_tokens
        )
        typer.echo(f"Planned student_graph LLM calls: {len(answer_ids)}")
        typer.echo(f"Estimated input tokens: {est_input_tokens}, output tokens: {est_output_tokens}")
        typer.echo(f"Estimated cost (PLACEHOLDER pricing): ${round(cost, 4)}")
        raise typer.Exit(code=0)

    questions = pd.read_csv(interim_dir / "saf_questions.csv")
    client = LLMClient(settings)
    registry = RelationRegistry.from_yaml(settings.resolve(settings.relation_registry))
    prompt_template = load_prompt(settings.resolve(settings.paths.prompts), "student_graph", "v2")  # CR-001 §7.2

    concepts_cache: dict[str, list[dict]] = {}

    for aid in answer_ids:
        arow = pilot_answers[pilot_answers["answer_id"] == aid].iloc[0]
        qid = arow["question_id"]
        qrow = questions[questions["question_id"] == qid].iloc[0]

        if qid not in concepts_cache:
            expert_gold = gold_dir / "expert_pilot" / f"{qid}.yaml"
            expert_draft = interim_dir / "suggestions" / "expert" / f"{qid}.yaml"
            source = expert_gold if expert_gold.exists() else expert_draft
            concepts_cache[qid] = _yaml.safe_load(source.read_text())["concepts"] if source.exists() else []

        draft = suggest_student_graph_v2(
            client,
            prompt_template,
            registry,
            answer_id=aid,
            question_id=qid,
            question=qrow["question"],
            answer_text=arow["provided_answer"],
            known_concepts=concepts_cache[qid],
        )
        out_path = interim_dir / "suggestions" / "student" / f"{aid}.yaml"
        write_student_suggestion(draft, out_path)
        typer.echo(
            f"{aid}: {len(draft['edges'])} edges, {len(draft['chain_links'])} chain links, "
            f"{len(draft['rejected'])} rejected -> {out_path}"
        )


@gold_app.command("mismatch-report")
def gold_mismatch_report() -> None:
    """Tabulate match_type frequencies from data/gold/student_pilot/ -> reports/m3_mismatch_types.md."""
    from cumap.gold.mismatch_report import generate_mismatch_report

    settings = get_settings()
    gold_dir = settings.resolve(settings.paths.data_gold)
    out_path = settings.resolve(settings.paths.reports) / "m3_mismatch_types.md"
    generate_mismatch_report(gold_dir / "student_pilot", out_path)
    typer.echo(f"Mismatch report -> {out_path}")


@gold_app.command("migrate-v1")
def gold_migrate_v1(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print a summary only; don't write the proposed files or report."),
) -> None:
    """Propose v1 migrations for every data/gold/ file (read-only towards data/gold/)."""
    from cumap.gold.migrate_v1 import run_migration, write_migration_report, write_migrations
    from cumap.gold.validate import validate_gold_dir
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    gold_dir = settings.resolve(settings.paths.data_gold)
    out_dir = settings.resolve(settings.paths.data_interim) / "suggestions" / "migrations" / "v1"
    registry = RelationRegistry.from_yaml(settings.resolve(settings.relation_registry))

    migrations = run_migration(gold_dir, out_dir, registry)
    validation_under_v1 = validate_gold_dir(gold_dir, force_version=1, registry=registry)

    n_suggestions = sum(len(m.suggestions) for m in migrations)
    typer.echo(f"{len(migrations)} gold file(s) examined, {n_suggestions} suggestion(s), {len(validation_under_v1.issues)} v1 validation issue(s) on the originals.")

    if dry_run:
        typer.echo("Dry run: did not write proposed files or the report.")
        raise typer.Exit(code=0)

    write_migrations(migrations)
    report_path = write_migration_report(migrations, validation_under_v1, settings.resolve(settings.paths.reports) / "migration_v1.md")
    typer.echo(f"Proposed files -> {out_dir}")
    typer.echo(f"Report -> {report_path}")


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
    """Launch the Streamlit gold review app (accept/edit/delete drafts, saves to data/gold/)."""
    import subprocess
    import sys

    settings = get_settings()
    app_path = settings.repo_root / "src" / "cumap" / "app" / "gold_editor.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=True)


if __name__ == "__main__":
    app()
