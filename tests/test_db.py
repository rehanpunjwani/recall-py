from pathlib import Path

from tokenguard.store.db import CURRENT_SCHEMA_VERSION, connect, get_schema_version, migrate


def test_migrate_to_current(tmp_path: Path) -> None:
    db = tmp_path / "tg.db"
    conn = connect(db)
    migrate(conn)
    assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
    conn.close()
