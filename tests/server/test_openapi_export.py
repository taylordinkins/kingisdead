from tools.export_openapi import OUT, render_schema


def test_committed_openapi_is_current():
    assert OUT.exists(), "run: uv run python tools/export_openapi.py"
    assert OUT.read_text() == render_schema()
