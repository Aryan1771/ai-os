"""Launch reviewed system desktop entries through the user's graphical session."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

APPLICATIONS = {
    "brave": "brave-browser.desktop",
    "firefox": "firefox.desktop",
    "files": "org.gnome.Nautilus.desktop",
    "terminal": "kitty.desktop",
    "settings": "org.gnome.Settings.desktop",
}


def launch_intent(text):
    match = re.fullmatch(
        r"(?:please\s+)?(?:open|launch|start)\s+(brave|firefox|files|terminal|settings)"
        r"(?:\s+browser)?[.!]?", text.strip(), re.IGNORECASE,
    )
    return match[1].lower() if match else None


def launch_application(application: str):
    if application not in APPLICATIONS:
        return {"ok": False, "error": "Supported apps: " + ", ".join(APPLICATIONS)}
    path = Path("/usr/share/applications") / APPLICATIONS[application]
    if not path.is_file():
        return {"ok": False, "error": f"{application} is not installed with a system desktop entry."}
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return {"ok": False, "error": "No graphical session. Open Settings in your desktop session."}
    # gio launches without waiting for the application lifetime. Do not accept URLs,
    # flags, user-selected desktop files or model-generated executable strings here.
    try:
        # A GUI descendant may inherit stdio. PIPE would keep communicate()
        # waiting for the browser to close even after gio itself has exited.
        with tempfile.TemporaryFile() as diagnostic:
            result = subprocess.run(["/usr/bin/gio", "launch", str(path)],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=diagnostic, timeout=10, shell=False)
            diagnostic.seek(0)
            error = diagnostic.read(1000).decode("utf-8", errors="replace")
        return {"ok": result.returncode == 0,
                "message": f"Launch requested for {application}.",
                "error": error if result.returncode else ""}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def command_help(command: str):
    if not isinstance(command, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.+-]{0,63}", command):
        raise ValueError("Provide one command name, without options or paths")
    try:
        result = subprocess.run(["/usr/bin/man", "-P", "/usr/bin/cat", "--", command],
                                env={"PATH": "/usr/bin", "LANG": "C.UTF-8", "MANWIDTH": "90"},
                                capture_output=True, text=True, timeout=8, shell=False)
        return {"ok": result.returncode == 0, "source": f"local man page: {command}",
                "text": result.stdout[:16000], "error": result.stderr[:500]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
