"""Streamlit gold review app (BUILD_PLAN M3 task 4).

Shows the source text (textbook sections, or a student's answer) next to the
LLM-drafted graph; a human accepts/edits/deletes/adds items and clicks Save.
This file is the ONLY place in the codebase that writes to data/gold/, and only
ever in response to a human clicking a Save button while this app is running
(CLAUDE.md rule 2 — the pipeline code itself never writes there).

Run with: cumap app review
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from cumap.config import get_settings
from cumap.gold.sections import section_ids_for_question
from cumap.gold.validate import verify_quote
from cumap.schemas.edges import Evidence, ExpertEdge, QuestionLink, Validation
from cumap.schemas.enums import MatchType
from cumap.schemas.nodes import Concept, ConceptMention
from cumap.schemas.relations import RelationRegistry
from cumap.schemas.student import EvidenceSpan, StudentEdge

st.set_page_config(page_title="cumap gold editor", layout="wide")

settings = get_settings()
interim_dir = settings.resolve(settings.paths.data_interim)
gold_dir = settings.resolve(settings.paths.data_gold)
registry = RelationRegistry.from_yaml(settings.repo_root / "configs" / "relations_v0.yaml")


@st.cache_data
def load_sections() -> dict[str, str]:
    path = interim_dir / "textbook_sections.jsonl"
    sections = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        sections[row["section_id"]] = row["text"]
    return sections


@st.cache_data
def load_questions() -> pd.DataFrame:
    return pd.read_csv(interim_dir / "saf_questions.csv")


def load_yaml_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def reviewer_name() -> str:
    return st.sidebar.text_input("Reviewer name (for validation.reviewer)", value="ZT")


st.sidebar.title("cumap gold editor")
mode = st.sidebar.radio("Mode", ["Expert graphs", "Student graphs"])
reviewer = reviewer_name()

# ---------------------------------------------------------------------------
if mode == "Expert graphs":
    st.title("Expert subgraph review")

    qid = st.sidebar.selectbox("Pilot question", settings.pilot_questions)
    questions = load_questions()
    qrow = questions[questions["question_id"] == qid].iloc[0]

    gold_path = gold_dir / "expert_pilot" / f"{qid}.yaml"
    draft_path = interim_dir / "suggestions" / "expert" / f"{qid}.yaml"
    source_path = gold_path if gold_path.exists() else draft_path
    st.caption(f"Loaded from: `{source_path.relative_to(settings.repo_root)}`" + (" (already in data/gold/)" if gold_path.exists() else " (model draft, not yet reviewed)"))

    data = load_yaml_dict(source_path)
    concepts = data.get("concepts", [])
    edges = data.get("edges", [])
    rejected = data.get("rejected", [])

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Question")
        st.write(qrow["question"])
        st.subheader("Reference answer")
        st.write(qrow["reference_answer"])
        st.subheader("Textbook section(s)")
        for sid in section_ids_for_question(gold_dir, interim_dir, qid):
            with st.expander(f"Section {sid}", expanded=False):
                st.text(load_sections().get(sid, "(section not found)"))

    with right:
        st.subheader(f"Concepts ({len(concepts)})")
        concepts_df = pd.DataFrame(
            [
                {
                    "concept_id": c["concept_id"],
                    "canonical_name": c["canonical_name"],
                    "node_type": c["node_type"],
                    "definition": c.get("definition", ""),
                    "evidence_quote": c["mentions"][0]["quote"] if c.get("mentions") else "",
                    "delete": False,
                }
                for c in concepts
            ]
        )
        edited_concepts = st.data_editor(concepts_df, num_rows="dynamic", key="concepts_editor", use_container_width=True)

        st.subheader(f"Edges ({len(edges)})")
        edges_df = pd.DataFrame(
            [
                {
                    "edge_id": e["edge_id"],
                    "source_id": e["source_id"],
                    "relation": e["relation"],
                    "target_id": e["target_id"],
                    "polarity": e["polarity"],
                    "modality": e["modality"],
                    "conditions": ", ".join(e.get("conditions", [])),
                    "criticality": e["criticality"],
                    "statement": e["statement"],
                    "evidence_quote": e["evidence"][0]["quote"] if e.get("evidence") else "",
                    "chain_id": e.get("chain_id") or "",
                    "delete": False,
                }
                for e in edges
            ]
        )
        edited_edges = st.data_editor(edges_df, num_rows="dynamic", key="edges_editor", use_container_width=True)

        if rejected:
            with st.expander(f"⚠️ {len(rejected)} rejected by the drafter (evidence not verified / unknown concept)"):
                st.json(rejected)

    if st.button("Validate + Save to data/gold/expert_pilot/", type="primary"):
        errors = []
        section_ids = section_ids_for_question(gold_dir, interim_dir, qid)
        combined_text = "\n\n".join(load_sections().get(sid, "") for sid in section_ids)

        final_concepts = []
        for _, row in edited_concepts.iterrows():
            if row["delete"]:
                continue
            if not verify_quote(row["evidence_quote"], combined_text):
                errors.append(f"Concept {row['concept_id']}: evidence quote not found in section text")
                continue
            final_concepts.append(
                Concept(
                    concept_id=row["concept_id"],
                    canonical_name=row["canonical_name"],
                    node_type=row["node_type"],
                    definition=row["definition"] or None,
                    mentions=[ConceptMention(section_id=section_ids[0], role="defined", quote=row["evidence_quote"])],
                    validation=Validation(status="accepted", reviewer=reviewer),
                )
            )

        final_edges = []
        for _, row in edited_edges.iterrows():
            if row["delete"]:
                continue
            if row["relation"] not in registry:
                errors.append(f"Edge {row['edge_id']}: unknown relation {row['relation']!r}")
                continue
            if not verify_quote(row["evidence_quote"], combined_text):
                errors.append(f"Edge {row['edge_id']}: evidence quote not found in section text")
                continue
            final_edges.append(
                ExpertEdge(
                    edge_id=row["edge_id"],
                    source_id=row["source_id"],
                    target_id=row["target_id"],
                    relation=row["relation"],
                    layer=registry.get(row["relation"]).layer,
                    polarity=row["polarity"],
                    modality=row["modality"],
                    conditions=[c.strip() for c in row["conditions"].split(",") if c.strip()],
                    statement=row["statement"],
                    criticality=row["criticality"],
                    question_links=[QuestionLink(question_id=qid, role="required", weight=1.0, source="reference_answer")],
                    chain_id=row["chain_id"] or None,
                    evidence=[Evidence(source="Peterson & Davie 6e", section_id=section_ids[0], quote=row["evidence_quote"])],
                    validation=Validation(status="accepted", reviewer=reviewer),
                    origin="textbook",
                )
            )

        if errors:
            st.error("Not saved. Fix these first:\n\n" + "\n".join(f"- {e}" for e in errors))
        else:
            gold_path.parent.mkdir(parents=True, exist_ok=True)
            gold_path.write_text(
                yaml.safe_dump(
                    {
                        "concepts": [c.model_dump(mode="json") for c in final_concepts],
                        "edges": [e.model_dump(mode="json") for e in final_edges],
                    },
                    sort_keys=False,
                    allow_unicode=True,
                )
            )
            st.success(f"Saved {len(final_concepts)} concepts, {len(final_edges)} edges -> {gold_path}")

# ---------------------------------------------------------------------------
else:
    st.title("Student graph review")

    pilot_answers_path = interim_dir / "pilot_answers.csv"
    if not pilot_answers_path.exists():
        st.warning("Run `cumap gold sample-answers` first.")
        st.stop()
    pilot_answers = pd.read_csv(pilot_answers_path)

    qid = st.sidebar.selectbox("Pilot question", settings.pilot_questions)
    q_answers = pilot_answers[pilot_answers["question_id"] == qid]
    answer_id = st.sidebar.selectbox(
        "Answer",
        q_answers["answer_id"],
        format_func=lambda aid: f"{aid} ({q_answers[q_answers['answer_id'] == aid].iloc[0]['verification_feedback']})",
    )
    arow = q_answers[q_answers["answer_id"] == answer_id].iloc[0]

    questions = load_questions()
    qrow = questions[questions["question_id"] == qid].iloc[0]

    gold_expert_path = gold_dir / "expert_pilot" / f"{qid}.yaml"
    draft_expert_path = interim_dir / "suggestions" / "expert" / f"{qid}.yaml"
    expert_source = gold_expert_path if gold_expert_path.exists() else draft_expert_path
    expert_data = load_yaml_dict(expert_source)
    expert_edges = expert_data.get("edges", [])

    gold_path = gold_dir / "student_pilot" / f"{answer_id}.yaml"
    draft_path = interim_dir / "suggestions" / "student" / f"{answer_id}.yaml"
    source_path = gold_path if gold_path.exists() else draft_path
    st.caption(f"Loaded from: `{source_path.relative_to(settings.repo_root)}`" + (" (already in data/gold/)" if gold_path.exists() else " (model draft, not yet reviewed)"))

    data = load_yaml_dict(source_path)
    edges = data.get("edges", [])
    rejected = data.get("rejected", [])
    prior_missing = set(data.get("missing_expected_edges", []))

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Question")
        st.write(qrow["question"])
        st.info("Only the student's answer is shown here — never the grader's feedback (rule 10).")
        st.subheader(f"Student answer ({arow['verification_feedback']}, score {arow['score']})")
        st.write(arow["provided_answer"])
        st.subheader("Expert edges for this question")
        st.dataframe(
            pd.DataFrame([{"edge_id": e["edge_id"], "statement": e["statement"], "criticality": e["criticality"]} for e in expert_edges]),
            use_container_width=True,
        )

    with right:
        st.subheader(f"Student edges ({len(edges)})")
        edges_df = pd.DataFrame(
            [
                {
                    "source_id": e["source_id"],
                    "relation": e["relation"],
                    "target_id": e["target_id"],
                    "polarity": e["polarity"],
                    "modality": e["modality"],
                    "stance": e["stance"],
                    "evidence_quote": e["evidence_span"]["text"],
                    "match_type": e.get("match_type") or "",
                    "delete": False,
                }
                for e in edges
            ]
        )
        edited_edges = st.data_editor(
            edges_df,
            num_rows="dynamic",
            key="student_edges_editor",
            use_container_width=True,
            column_config={
                "match_type": st.column_config.SelectboxColumn(options=[""] + [m.value for m in MatchType]),
            },
        )

        if rejected:
            with st.expander(f"⚠️ {len(rejected)} rejected by the drafter (evidence not verified)"):
                st.json(rejected)

        st.subheader("Missing expected edges")
        missing = st.multiselect(
            "Expert edges the student's answer does NOT cover",
            options=[e["edge_id"] for e in expert_edges],
            default=[e for e in prior_missing if e in {ex["edge_id"] for ex in expert_edges}],
        )

    if st.button("Validate + Save to data/gold/student_pilot/", type="primary"):
        errors = []
        answer_text = arow["provided_answer"]
        final_edges = []
        for _, row in edited_edges.iterrows():
            if row["delete"]:
                continue
            if not verify_quote(row["evidence_quote"], answer_text):
                errors.append(f"Edge {row['source_id']}->{row['target_id']}: evidence quote not found in answer text")
                continue
            start = answer_text.find(row["evidence_quote"])
            final_edges.append(
                StudentEdge(
                    source_id=row["source_id"],
                    relation=row["relation"],
                    target_id=row["target_id"],
                    polarity=row["polarity"],
                    modality=row["modality"],
                    response_id=answer_id,
                    question_id=qid,
                    evidence_span=EvidenceSpan(
                        start=max(start, 0), end=max(start, 0) + len(row["evidence_quote"]), text=row["evidence_quote"]
                    ),
                    stance=row["stance"],
                    extraction_confidence=1.0,
                    link_confidence=1.0,
                    match_type=row["match_type"] or None,
                )
            )

        if errors:
            st.error("Not saved. Fix these first:\n\n" + "\n".join(f"- {e}" for e in errors))
        else:
            gold_path.parent.mkdir(parents=True, exist_ok=True)
            gold_path.write_text(
                yaml.safe_dump(
                    {
                        "edges": [e.model_dump(mode="json") for e in final_edges],
                        "missing_expected_edges": missing,
                    },
                    sort_keys=False,
                    allow_unicode=True,
                )
            )
            st.success(f"Saved {len(final_edges)} edges, {len(missing)} missing-expected -> {gold_path}")
