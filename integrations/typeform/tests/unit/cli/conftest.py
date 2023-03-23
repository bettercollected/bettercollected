from click.testing import CliRunner

import pytest


@pytest.fixture
def cli_runner():
    yield CliRunner()
