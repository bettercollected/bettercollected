import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from settings_support import MASTER  # noqa: E402

from common.settings.keys import SectionKeys  # noqa: E402


@pytest.fixture
def keys() -> SectionKeys:
    return SectionKeys(MASTER, sections=["mail", "ai"])
