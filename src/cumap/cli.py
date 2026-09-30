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
demo_app = typer.Typer(help="CR-005 demo report (expert KG only).")
external_app = typer.Typer(help="External benchmark datasets (CR-003 §3) — iir_face only for now.")

app.add_typer(data_app, name="data")
app.add_typer(demo_app, name="demo")
app.add_typer(textbook_app, name="textbook")
app.add_typer(gold_app, name="gold")
app.add_typer(labels_app, name="labels")
app.add_typer(kg_app, name="kg")
app.add_typer(student_app, name="student")
app.add_typer(diagnose_app, name="diagnose")
app.add_typer(eval_app, name="eval")
app.add_typer(app_app, name="app")
app.add_typer(external_app, name="external")


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
        typer.echo(f"Planned coverage-guess LLM calls: {estimate['n_calls']} (tier: strong, model: {settings.llm.tiers['strong'].model})")
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
        typer.echo(f"Planned expert_subgraph LLM calls: {len(qids)} (tier: strong, model: {settings.llm.tiers['strong'].model})")
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
        typer.echo(f"Planned student_graph LLM calls: {len(answer_ids)} (tier: strong, model: {settings.llm.tiers['strong'].model})")
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


@gold_app.command("sample-relation-items")
def gold_sample_relation_items(
    n: int = typer.Option(100, "--n"),
    seed: int | None = typer.Option(None, "--seed"),
    min_per_family: int = typer.Option(8, "--min-per-family"),
) -> None:
    """CR-001 §7.3: sample textbook sentences for the relation-set agreement test and
    write two blank annotator sheets. No LLM call — reuses already-drafted concepts/edges.
    """
    import json as _json

    import yaml as _yaml

    from cumap.gold.sample_relation_items import (
        find_candidate_items,
        stratified_sample,
        write_relation_agreement_files,
    )
    from cumap.gold.sections import section_ids_for_question
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    interim_dir = settings.resolve(settings.paths.data_interim)
    gold_dir = settings.resolve(settings.paths.data_gold)
    registry = RelationRegistry.from_yaml(settings.resolve(settings.relation_registry))

    sections_by_id = {}
    for line in (interim_dir / "textbook_sections.jsonl").read_text().splitlines():
        row = _json.loads(line)
        sections_by_id[row["section_id"]] = row["text"]

    all_candidates = []
    for qid in settings.pilot_questions:
        expert_gold = gold_dir / "expert_pilot" / f"{qid}.yaml"
        expert_draft = interim_dir / "suggestions" / "expert" / f"{qid}.yaml"
        source = expert_gold if expert_gold.exists() else expert_draft
        if not source.exists():
            typer.echo(f"skipping {qid}: no drafted/gold expert subgraph yet (run `cumap gold suggest-expert` first)")
            continue
        data = _yaml.safe_load(source.read_text()) or {}
        concepts, edges = data.get("concepts", []), data.get("edges", [])

        q_section_ids = section_ids_for_question(gold_dir, interim_dir, qid)
        q_sections = {sid: sections_by_id[sid] for sid in q_section_ids if sid in sections_by_id}
        all_candidates += find_candidate_items(qid, q_sections, concepts, edges, registry)

    typer.echo(f"{len(all_candidates)} candidate sentence/concept-pair items found across {len(settings.pilot_questions)} pilot questions.")

    selected = stratified_sample(all_candidates, registry, n=n, seed=seed if seed is not None else settings.seed, min_per_family=min_per_family)

    from collections import Counter

    family_counts = Counter(i.predicted_family or "unknown" for i in selected)
    for family, count in sorted(family_counts.items()):
        typer.echo(f"  {family}: {count}")

    out_dir = interim_dir / "relation_agreement"
    paths = write_relation_agreement_files(selected, out_dir, registry)
    typer.echo(f"{len(selected)} items selected -> {paths['items']}")
    typer.echo(f"Blank sheets -> {paths['annotator_A']}, {paths['annotator_B']}")


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


@kg_app.command("organise")
def kg_organise(
    run: str = typer.Option(..., "--run", help="KG run_id under data/processed/kg/"),
    mode: str = typer.Option("provisional", "--mode", help="provisional | principles (later)"),
    through_chapter: int | None = typer.Option(None, "--through-chapter"),
    config: str | None = typer.Option(None, "--config", help="default: configs/organisation.yaml"),
) -> None:
    """CR-006: per-chapter core-periphery organisation. Reads snapshots, writes only under
    organisation/. No API calls, so no dry run is needed."""
    from pathlib import Path

    from cumap.config import REPO_ROOT, get_settings, load_demo_slice
    from cumap.organisation.config import load_config
    from cumap.organisation.pipeline import run_organisation
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    cfg = load_config(Path(config) if config else None)
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    run_dir = REPO_ROOT / "data" / "processed" / "kg" / run
    sections = REPO_ROOT / load_demo_slice().pd.source_jsonl
    org = run_organisation(run_dir, sections, registry, cfg, mode=mode,
                           through_chapter=through_chapter, progress=typer.echo)
    typer.echo(f"org_id {org.org_id} -> {org.org_dir}")
    for r in org.chapters:
        cp = r.summary["core_periphery"]
        typer.echo(f"  ch{r.chapter}: {r.summary['n_nodes']} concepts, {r.summary['n_edges']} edges, "
                   f"core-periphery: {cp['label']} (rho {cp['rho_obs']:.3f}, z {cp['primary']['z']:.1f}, "
                   f"delta {cp['primary']['delta_rho']:.3f})")


@kg_app.command("organise-summary")
def kg_organise_summary(
    run: str = typer.Option(..., "--run"),
    org: str = typer.Option(..., "--org", help="org_id"),
    out: str | None = typer.Option(None, "--out", help="default: reports/organisation_<org>.md"),
) -> None:
    """Write the STOP 2 markdown summary for an organisation run (read-only)."""
    from pathlib import Path

    from cumap.config import REPO_ROOT, get_settings, load_demo_slice
    from cumap.organisation.config import load_config
    from cumap.organisation.inputs import load_inputs
    from cumap.organisation.summary import build_summary
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    registry = RelationRegistry.from_yaml(REPO_ROOT / settings.relation_registry)
    run_dir = REPO_ROOT / "data" / "processed" / "kg" / run
    inp = load_inputs(run_dir, REPO_ROOT / load_demo_slice().pd.source_jsonl, registry, load_config())
    text = build_summary(run_dir / "organisation" / org, inp)
    path = Path(out) if out else REPO_ROOT / "reports" / f"organisation_{org}.md"
    path.write_text(text, encoding="utf-8")
    typer.echo(f"wrote {path}")


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


@eval_app.command("relation-agreement")
def eval_relation_agreement() -> None:
    """CR-001 §7.3: score the two completed sheets in data/gold/relation_agreement/."""
    import pandas as pd

    from cumap.eval.relation_agreement import compute_agreement, write_agreement_report
    from cumap.schemas.relations import RelationRegistry

    settings = get_settings()
    gold_dir = settings.resolve(settings.paths.data_gold) / "relation_agreement"
    sheet_a_path = gold_dir / "annotator_A.csv"
    sheet_b_path = gold_dir / "annotator_B.csv"
    if not sheet_a_path.exists() or not sheet_b_path.exists():
        typer.echo(f"Both {sheet_a_path} and {sheet_b_path} must exist (the human saves completed sheets there).")
        raise typer.Exit(code=1)

    registry = RelationRegistry.from_yaml(settings.resolve(settings.relation_registry))
    sheet_a, sheet_b = pd.read_csv(sheet_a_path), pd.read_csv(sheet_b_path)
    result = compute_agreement(sheet_a, sheet_b, registry)
    report_path = write_agreement_report(result, settings.resolve(settings.paths.reports) / "m3_relation_agreement.md")

    typer.echo(f"relation κ={result['relation_kappa']:.3f}, family κ={result['family_kappa']:.3f}")
    typer.echo(f"Report -> {report_path}")


@app_app.command("review")
def app_review() -> None:
    """Launch the Streamlit gold review app (accept/edit/delete drafts, saves to data/gold/)."""
    import subprocess
    import sys

    settings = get_settings()
    app_path = settings.repo_root / "src" / "cumap" / "app" / "gold_editor.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=True)


@external_app.command("fetch")
def external_fetch(name: str = typer.Argument(..., help="Dataset name. Only 'iir_face' is implemented.")) -> None:
    """Clone an external dataset's source repo into data/raw/external/<name>/."""
    if name != "iir_face":
        typer.echo(f"'{name}' is not implemented (CR-003's other external sources are out of scope for now).")
        raise typer.Exit(code=1)

    from cumap.data.iir_face import fetch_iir_face

    settings = get_settings()
    dest_dir = settings.resolve(settings.paths.data_raw) / "external" / "iir_face"
    commit = fetch_iir_face(dest_dir)
    typer.echo(f"Fetched iir_face -> {dest_dir} at commit {commit}")


@external_app.command("load")
def external_load(name: str = typer.Argument(..., help="Dataset name. Only 'iir_face' is implemented.")) -> None:
    """Parse a fetched external dataset into data/interim/external/ (gitignored — third-party text)."""
    if name != "iir_face":
        typer.echo(f"'{name}' is not implemented (CR-003's other external sources are out of scope for now).")
        raise typer.Exit(code=1)

    import dataclasses as _dc

    from cumap.data.iir_face import load_iir_face

    settings = get_settings()
    raw_dir = settings.resolve(settings.paths.data_raw) / "external" / "iir_face"
    out_dir = settings.resolve(settings.paths.data_interim) / "external"
    out_dir.mkdir(parents=True, exist_ok=True)

    sections, gold = load_iir_face(raw_dir)

    sections_path = out_dir / "iir_sections.jsonl"
    with sections_path.open("w") as f:
        for section in sections:
            f.write(json.dumps(_dc.asdict(section)) + "\n")
    gold_path = out_dir / "iir_gold_concepts.csv"
    gold.to_csv(gold_path, index=False)

    n_gold = int(gold["is_gold"].sum())
    typer.echo(f"{len(sections)} sections -> {sections_path}")
    typer.echo(f"{len(gold)} candidate concepts ({n_gold} gold, majority vote) -> {gold_path}")


@external_app.command("stats")
def external_stats(name: str = typer.Argument(..., help="Dataset name. Only 'iir_face' is implemented.")) -> None:
    """Print summary stats for a loaded external dataset."""
    if name != "iir_face":
        typer.echo(f"'{name}' is not implemented (CR-003's other external sources are out of scope for now).")
        raise typer.Exit(code=1)

    import pandas as pd

    settings = get_settings()
    out_dir = settings.resolve(settings.paths.data_interim) / "external"
    sections_path = out_dir / "iir_sections.jsonl"
    gold_path = out_dir / "iir_gold_concepts.csv"
    if not sections_path.exists() or not gold_path.exists():
        typer.echo("Run `cumap external load iir_face` first.")
        raise typer.Exit(code=1)

    sections = [json.loads(line) for line in sections_path.read_text().splitlines()]
    gold = pd.read_csv(gold_path)

    by_chapter: dict[int, list[dict]] = {}
    for s in sections:
        by_chapter.setdefault(s["chapter_num"], []).append(s)

    typer.echo(f"{len(sections)} sections across {len(by_chapter)} chapters, {sum(s['word_count'] for s in sections)} words total")
    for chapter_num in sorted(by_chapter):
        chapter_sections = by_chapter[chapter_num]
        chapter_gold = gold[gold["section_id"].isin(s["section_id"] for s in chapter_sections)]
        n_gold = int(chapter_gold["is_gold"].sum())
        typer.echo(
            f"  ch{chapter_num} ({chapter_sections[0]['chapter_title']}): {len(chapter_sections)} sections, "
            f"{sum(s['word_count'] for s in chapter_sections)} words, {len(chapter_gold)} candidate / {n_gold} gold concepts"
        )


if __name__ == "__main__":
    app()


@demo_app.command("build")
def demo_build(
    run: str = typer.Option(..., "--run", help="P&D run_id under data/processed/kg/"),
    refresh_eval: bool = typer.Option(False, "--refresh-eval", help="Recompute FACE metrics"),
) -> None:
    """Build reports/demo/index.html + figures/ from saved artefacts. No LLM calls."""
    from cumap.config import load_demo_slice
    from cumap.report.build import build_report

    nlp = embed_fn = None
    if refresh_eval:
        import spacy
        from sentence_transformers import SentenceTransformer

        nlp = spacy.load("en_core_web_sm")
        model = SentenceTransformer(get_settings().embeddings.model)
        embed_fn = lambda t: model.encode(t)
    path = build_report(
        run, get_settings(), load_demo_slice(), nlp=nlp, embed_fn=embed_fn, refresh_eval=refresh_eval
    )
    typer.echo(f"wrote {path}")
