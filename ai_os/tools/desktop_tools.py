"""Launch reviewed system desktop entries through the user's graphical session."""
import os
import configparser
import re
import secrets
import subprocess
import tempfile
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path

APPLICATIONS = {
    "brave": "brave-browser.desktop",
    "firefox": "firefox.desktop",
    "files": "org.gnome.Nautilus.desktop",
    "terminal": "kitty.desktop",
    "settings": "org.gnome.Settings.desktop",
}
MAN_ROOT = Path("/usr/share/man")
APPLICATION_ROOT = Path("/usr/share/applications")
APPLICATION_ROOTS = (
    Path.home() / ".local/share/applications",
    Path("/usr/share/applications"),
    Path.home() / ".local/share/flatpak/exports/share/applications",
    Path("/var/lib/flatpak/exports/share/applications"),
)
BROWSER_ROOTS = APPLICATION_ROOTS
BROWSER_IDS = {
    "brave": ("brave-browser.desktop", "com.brave.Browser.desktop"),
    "firefox": ("firefox.desktop", "org.mozilla.firefox.desktop"),
    "chromium": ("chromium.desktop", "org.chromium.Chromium.desktop"),
    "chrome": ("google-chrome.desktop", "google-chrome-stable.desktop"),
    "edge": ("microsoft-edge.desktop", "microsoft-edge-stable.desktop"),
}
SITE_ALIASES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "netflix": "https://www.netflix.com",
}
TEST_WEBSITES = ("https://example.org", "https://example.com", "https://www.wikipedia.org")


def open_test_website(browser: str = ""):
    """Open one benign public example when the user asks for a random/test website."""
    return open_website(secrets.choice(TEST_WEBSITES), browser)


def list_applications(query: str = ""):
    """Discover installed system desktop entries without executing their contents."""
    if not isinstance(query, str) or len(query) > 80:
        raise ValueError("Use an application name or short search term")
    applications = []
    seen = set()
    for root in APPLICATION_ROOTS:
        for path in sorted(root.glob("*.desktop")):
            if path.name in seen:
                continue
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
                entry = parser["Desktop Entry"]
                if (entry.get("Type") != "Application" or entry.get("Hidden", "false").lower() == "true"
                        or entry.get("NoDisplay", "false").lower() == "true" or not entry.get("Exec")):
                    continue
                name = entry.get("Name", path.stem)[:100]
                if query.casefold() in (name + " " + path.name).casefold():
                    applications.append({"application": path.name, "name": name})
                    seen.add(path.name)
            except (OSError, configparser.Error, KeyError, UnicodeError):
                continue
            if len(applications) >= 100:
                break
        if len(applications) >= 100:
            break
    return {"ok": True, "applications": applications}


def running_applications():
    """Read same-user process names and counts; never command lines, titles or memory."""
    import psutil
    counts = {}
    for process in psutil.process_iter(["name", "uids"]):
        try:
            if process.info["uids"].real != os.getuid():
                continue
            name = (process.info["name"] or "unknown")[:80]
            counts[name] = counts.get(name, 0) + 1
        except (psutil.Error, AttributeError):
            continue
    return {"ok": True, "programs": [{"name": name, "process_count": count}
                                     for name, count in sorted(counts.items())[:100]]}


def _browser_entry(browser: str = ""):
    """Find a known browser's desktop file without executing arbitrary entries."""
    candidates = BROWSER_IDS.get(browser.casefold(), ()) if browser else tuple(
        entry for entries in BROWSER_IDS.values() for entry in entries
    )
    for entry_id in candidates:
        for root in BROWSER_ROOTS:
            path = root / entry_id
            if path.is_file():
                return path, entry_id
    return None, ""


def _launch_browser_url(browser: str, url: str):
    path, entry_id = _browser_entry(browser)
    if path is None:
        return {"ok": False, "error": f"No installed {browser or 'supported'} browser desktop entry was found."}
    try:
        with tempfile.TemporaryFile() as diagnostic:
            result = subprocess.run(
                ["/usr/bin/gio", "launch", str(path), url], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=diagnostic, timeout=10, shell=False,
            )
            diagnostic.seek(0)
            error = diagnostic.read(1000).decode("utf-8", errors="replace")
        return {"ok": result.returncode == 0,
                "message": f"Website launch requested in {entry_id}." if result.returncode == 0 else "Browser launch failed.",
                "error": error if result.returncode else "", "browser": entry_id}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def open_website(url: str, browser: str = ""):
    """Open an HTTP(S) page in a selected or default installed browser."""
    if not isinstance(url, str) or not 1 <= len(url) <= 2048 or any(
        c.isspace() or not c.isprintable() for c in url
    ):
        raise ValueError("Provide one HTTP(S) website address")
    if "://" not in url:
        url = "https://" + url
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or "." not in parsed.hostname or "\\" in url):
        raise ValueError("Only HTTP(S) website addresses without credentials are supported")
    # Validate the port before passing to the desktop URL handler.
    _ = parsed.port
    url = urlunsplit(parsed)
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return {"ok": False, "error": "No graphical session for the browser"}
    if browser:
        if browser.casefold() not in BROWSER_IDS:
            return {"ok": False, "error": "Choose a supported installed browser: Brave, Firefox, Chromium, Chrome or Edge."}
        return _launch_browser_url(browser, url)
    try:
        with tempfile.TemporaryFile() as diagnostic:
            result = subprocess.run(
                ["/usr/bin/gio", "open", url], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=diagnostic, timeout=10, shell=False,
            )
            diagnostic.seek(0)
            error = diagnostic.read(1000).decode("utf-8", errors="replace")
        if result.returncode == 0:
            return {"ok": True, "message": "Website launch requested in the default browser."}
        # If the desktop has no working URI handler, discover and try a known,
        # installed browser entry. Never fall back to executing arbitrary names.
        for name in BROWSER_IDS:
            if _browser_entry(name)[0] is not None:
                fallback = _launch_browser_url(name, url)
                if fallback["ok"]:
                    return fallback
        return {"ok": False, "error": error or "No installed browser could open this website."}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def _manual_topics(query):
    words = query.lower().split()
    aliases = {"network": {"ip", "nmcli", "networkctl", "ss"},
               "packages": {"pacman", "makepkg", "pacman-conf"},
               "services": {"systemctl", "journalctl"},
               "audio": {"wpctl", "pw-cli", "pw-record", "pw-play"}}
    names = set().union(*(aliases.get(word, set()) for word in words))
    found = []
    for section in (1, 5, 8):
        folder = MAN_ROOT / f"man{section}"
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            name = re.sub(r"\.[1-9](?:\.(?:gz|xz|zst|bz2))?$", "", path.name)
            if name in names or any(word in name.lower() for word in words):
                found.append(f"{name} ({section}) — installed manual")
                if len(found) >= 100:
                    return sorted(found)
    return sorted(found)


def launch_intent(text):
    match = re.fullmatch(
        r"(?:please\s+)?(?:open|launch|start)\s+(brave|firefox|files|terminal|settings)"
        r"(?:\s+browser)?[.!]?", text.strip(), re.IGNORECASE,
    )
    return match[1].lower() if match else None


def website_intent(text):
    """Parse direct open-site requests so simple launches do not depend on LLM tool use."""
    if not isinstance(text, str) or len(text) > 1000:
        return None
    match = re.fullmatch(
        r"(?:(?:hey\s+re[,:]?|please|can you|could you|would you)\s+)*(?:please\s+)?(?:open|visit|go to|navigate to|load|browse to|bring up|take me to|show me)\s+(?:the\s+)?(.+?)[.!?]?",
        text.strip(), re.IGNORECASE,
    )
    if not match:
        return None
    target = match.group(1).strip().rstrip(".!?").strip()
    target = re.sub(r"\s+for me$", "", target, flags=re.IGNORECASE).strip()
    browser = ""
    browser_match = re.search(
        r"\s+(?:in|on|using)\s+(?:the\s+)?(brave|firefox|chromium|chrome|edge)(?:\s+browser)?$",
        target, re.IGNORECASE,
    )
    if browser_match:
        browser = browser_match.group(1).casefold()
        target = target[:browser_match.start()].strip()
    test_target = re.sub(r"\s+(?:to (?:test|check|see)|for (?:testing|a test)|so (?:we|I) can test)\b.*$", "", target, flags=re.I).strip()
    if re.fullmatch(r"(?:(?:a|an|any|some|one)\s+)?(?:(?:random|test|example)\s+)?(?:website|web site|webpage|web page|site|page)", test_target, re.I):
        return {"url": secrets.choice(TEST_WEBSITES), "browser": browser}
    url = SITE_ALIASES.get(target.casefold())
    if url:
        return {"url": url, "browser": browser}
    # An explicit hostname/URL is unambiguous; don't turn arbitrary phrases into search queries.
    if "." in target and " " not in target:
        try:
            candidate = target if "://" in target else "https://" + target
            parsed = urlsplit(candidate)
            if parsed.hostname and "." in parsed.hostname and parsed.scheme in {"http", "https"}:
                return {"url": candidate, "browser": browser}
        except ValueError:
            return None
    return None


def launch_application(application: str):
    if not isinstance(application, str) or not 1 <= len(application) <= 150:
        return {"ok": False, "error": "Choose an application ID from list_applications"}
    entry_id = APPLICATIONS.get(application)
    if entry_id is None:
        # A filename must be discovered in the system application directory.
        # No paths, URLs, flags or user-supplied desktop-entry contents are accepted.
        matches = list_applications(application)["applications"]
        if application not in {item["application"] for item in matches}:
            return {"ok": False, "error": "Call list_applications to discover an exact installed application ID"}
        entry_id = application
    path = next((root / entry_id for root in APPLICATION_ROOTS if (root / entry_id).is_file()),
                APPLICATION_ROOT / entry_id)
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


def find_commands(query: str):
    """Discover installed manual topics without executing candidate commands."""
    if not isinstance(query, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _+-]{0,79}", query):
        raise ValueError("Use a short command topic without options or shell syntax")
    try:
        result = subprocess.run(["/usr/bin/apropos", "--", query],
                                env={"PATH": "/usr/bin", "LANG": "C.UTF-8"},
                                capture_output=True, text=True, timeout=8, shell=False)
        if result.returncode == 16:
            topics = _manual_topics(query)
            return {"ok": bool(topics), "source": "installed manual filenames (apropos index unavailable or no match)",
                    "text": "\n".join(topics), "error": "" if topics else "No local manual topics found"}
        return {"ok": result.returncode == 0, "source": "installed manual index",
                "text": result.stdout[:12000], "error": result.stderr[:500]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}
