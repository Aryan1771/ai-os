"""Opt-in app usage totals; never screenshots, window titles, text, URLs or keystrokes."""
from contextlib import closing
from pathlib import Path
import sqlite3

from ai_os.config import load_raw_config, atomic_json


class ActivityMemory:
    def __init__(self, home: Path):
        self.home = home
        self.path = home / "data/private/activity.sqlite3"

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        db = sqlite3.connect(self.path, timeout=1)
        self.path.chmod(0o600)
        db.execute("CREATE TABLE IF NOT EXISTS usage(day TEXT, app TEXT, seconds INTEGER, PRIMARY KEY(day,app))")
        return db

    def record(self, application, seconds=15):
        config = load_raw_config(self.home)
        if not config["activity_memory_enabled"] or not config["memory_enabled"]:
            return
        if not isinstance(application, str) or not application.strip() or len(application) > 80 or not application.isprintable():
            return
        seconds = max(1, min(30, int(seconds)))
        with closing(self.connect()) as db, db:
            self.prune(db)
            db.execute("INSERT INTO usage VALUES(date('now'),?,?) ON CONFLICT(day,app) DO UPDATE SET seconds=seconds+excluded.seconds",
                       (application, seconds))
            # App/day cardinality is bounded even if an app publishes changing names.
            db.execute("DELETE FROM usage WHERE rowid NOT IN (SELECT rowid FROM usage ORDER BY day DESC,rowid DESC LIMIT 2000)")

    def prune(self, db):
        days = max(1, min(30, int(load_raw_config(self.home)["activity_retention_days"])))
        db.execute("DELETE FROM usage WHERE day < date('now', ?)", (f"-{days-1} days",))

    def summary(self):
        if not self.path.exists():
            return []
        with closing(self.connect()) as db, db:
            self.prune(db)
            return [{"application": row[0], "approximate_minutes": round(row[1]/60, 1)}
                    for row in db.execute("SELECT app,SUM(seconds) FROM usage GROUP BY app ORDER BY SUM(seconds) DESC LIMIT 12")]

    def clear(self):
        if self.path.exists():
            with closing(self.connect()) as db, db:
                db.execute("DELETE FROM usage")


def collect_activity(home, stop):
    from ai_os.desktop_context import read_desktop
    memory = ActivityMemory(home)
    while not stop.is_set():
        try:
            config = load_raw_config(home)
            state = "off"
            if config["activity_memory_enabled"] and config["memory_enabled"]:
                observation = read_desktop(home, metadata_only=True)
                state = "ready" if observation.get("ok") else "unavailable"
                if observation.get("ok"):
                    memory.record(observation.get("application"))
            atomic_json(home / "run/activity-status.json", {"state": state})
        except (OSError, ValueError, sqlite3.Error):
            # No private app names or database content go into error logs.
            pass
        stop.wait(15)
