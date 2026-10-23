"""CR-006: per-chapter core-periphery ("sphere") organisation of the expert KG.

Structure only, no API calls. Reads content snapshots (never modifies them) and writes
only under data/processed/kg/<run_id>/organisation/<org_id>/. Rings are a structural
view, not CR-004 tiers: never delete or demote a concept because of its ring.
"""
