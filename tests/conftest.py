import os

import pytest

RUN_LIVE = os.getenv("RUN_LIVE_TESTS") == "1"


def pytest_collection_modifyitems(config, items):
    if RUN_LIVE:
        return
    skip_live = pytest.mark.skip(
        reason="live LLM test — set RUN_LIVE_TESTS=1 to run"
    )
    for item in items:
        if "live_llm" in item.keywords:
            item.add_marker(skip_live)
