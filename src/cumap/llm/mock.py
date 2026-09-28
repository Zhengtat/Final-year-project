"""Mock LLM backend: returns fixture JSON instead of calling any API.

Selected via CUMAP_LLM_BACKEND=mock. Tests always force this backend so no test
needs network access or an API key.
"""

from __future__ import annotations

import json
from pathlib import Path


class FixtureNotFoundError(FileNotFoundError):
    pass


def load_fixture(fixtures_dir: Path, task: str, fixture_name: str = "default") -> dict:
    """Read tests/fixtures/llm/<task>/<fixture_name>.json and return the parsed dict.

    The fixture holds the raw JSON that would sit in `response.output_parsed`
    (i.e. the schema's fields), plus an optional "_usage" block for token counts.
    """
    path = fixtures_dir / task / f"{fixture_name}.json"
    if not path.exists():
        raise FixtureNotFoundError(
            f"No mock fixture at {path}. Add one under tests/fixtures/llm/{task}/."
        )
    return json.loads(path.read_text())
