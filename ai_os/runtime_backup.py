"""Private, bounded backups before runtime configuration or memory migrations."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


def backup_runtime(home: Path) -> Path:
    root = home / "backups"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    target = Path(tempfile.mkdtemp(prefix="pre-migration-", dir=root))
    for name in ("config.json", "habit_engine.json", "slang_vocab.json"):
        source = home / name
        if source.is_file():
            shutil.copy2(source, target / name)
            (target / name).chmod(0o600)
    source = home / "data/private/conversations.sqlite3"
    if source.is_file():
        destination = target / "conversations.sqlite3"
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with (
            closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src,
            closing(sqlite3.connect(destination)) as dst,
        ):
            src.backup(dst)
    return target


if __name__ == "__main__":
    from ai_os.config import AI_OS_HOME

    print(backup_runtime(AI_OS_HOME))
