"""docker-compose.infisical.yml must pass through every setting config.py reads.

Compose only forwards the variables an override lists, so a setting missing there would sit at its
default for anyone running Docker through Infisical, with nothing to say it had been dropped.
"""

from pathlib import Path

import pytest
import yaml

from config import Settings

OVERRIDE = Path(__file__).resolve().parents[2] / "docker-compose.infisical.yml"


def test_infisical_override_passes_through_every_setting():
    # The backend image only contains backend/, so the compose files are absent inside a container.
    if not OVERRIDE.exists():
        pytest.skip("compose override not present (running inside the backend image)")

    listed = set(yaml.safe_load(OVERRIDE.read_text())["services"]["backend"]["environment"])
    declared = {field.validation_alias for field in Settings.model_fields.values()}

    missing = sorted(declared - listed)
    assert not missing, f"add to {OVERRIDE.name}: {', '.join(missing)}"
