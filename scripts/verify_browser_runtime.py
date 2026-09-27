"""Read one fixed public manual with a temporary browser profile; never submit prompts."""
import argparse
import json
import tempfile
from pathlib import Path

from ai_os.reviewed_actions import execute
from ai_os.settings_store import save_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["arch", "gnu"], default="arch")
    args = parser.parse_args()
    url = {"arch": "https://man.archlinux.org/man/bash.1.en",
           "gnu": "https://www.gnu.org/software/bash/manual/bash.html"}[args.source]
    with tempfile.TemporaryDirectory(prefix="regenos-browser-check-") as directory:
        home = Path(directory)
        save_settings({"browser_enabled": True}, home, human_confirmed=True)
        try:
            result = execute("research_page", {"url": url}, home, confirmed=True)
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)[:1000]}))
            return 1
        print(json.dumps({"ok": result["ok"], "source": result["source"],
                          "characters": len(result["text"]), "contains_bash": "Bash" in result["text"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
