from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_head_is_investigation_revision() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "0002_investigation_id"
    revision = script.get_revision("0002_investigation_id")
    assert revision is not None
    assert revision.down_revision == "0001_initial"
    initial = script.get_revision("0001_initial")
    assert initial is not None
    assert initial.down_revision is None
