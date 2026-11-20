from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_head_is_auth_workspaces_revision() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == "0006_auth_workspaces"
    revision = script.get_revision("0006_auth_workspaces")
    assert revision is not None
    assert revision.down_revision == "0005_drop_audit_event_uniqueness"
    previous = script.get_revision("0005_drop_audit_event_uniqueness")
    assert previous is not None
    assert previous.down_revision == "0004_audit_logs"
    previous = script.get_revision("0004_audit_logs")
    assert previous is not None
    assert previous.down_revision == "0003_action_decisions"
    initial = script.get_revision("0001_initial")
    assert initial is not None
    assert initial.down_revision is None
