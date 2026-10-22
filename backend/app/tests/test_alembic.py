from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_head_is_initial_revision() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "0001_initial"
    revision = script.get_revision("0001_initial")
    assert revision is not None
    assert revision.down_revision is None
