"""Read-only GNOME AT-SPI helper, executed with distro GI bindings.

No package imports: /usr/bin/python -I this_file.py [--metadata-only]. The parent
owns the hard timeout and never logs stdout. Password/editable subtrees are skipped.
"""
import json
import sys
import time


def unlocked(Gio):
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    reply = connection.call_sync(
        "org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "org.gnome.ScreenSaver",
        "GetActive", None, None, Gio.DBusCallFlags.NONE, 300, None,
    )
    return reply.unpack() == (False,)


def snapshot(metadata_only=False):
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi, Gio

    if not unlocked(Gio):
        return {"ok": False, "reason": "Desktop locked"}
    Atspi.set_timeout(150, 150)
    deadline = time.monotonic() + 2.5
    desktop = Atspi.get_desktop(0)
    selected = None
    for index in range(min(desktop.get_child_count(), 60)):
        if time.monotonic() > deadline:
            break
        app = desktop.get_child_at_index(index)
        try:
            for child in range(min(app.get_child_count(), 30)):
                window = app.get_child_at_index(child)
                states = window.get_state_set()
                if states.contains(Atspi.StateType.ACTIVE):
                    selected = app, window
                    break
        except Exception:
            continue
        if selected:
            break
    if selected is None:
        return {"ok": False, "reason": "No focused accessible application. Some apps do not expose AT-SPI."}
    app, window = selected
    name = (app.get_name() or "Unknown application")[:80]
    if any(word in name.casefold() for word in ("keepass", "bitwarden", "1password", "seahorse")):
        return {"ok": False, "reason": "Sensitive application excluded"}
    if metadata_only:
        return {"ok": unlocked(Gio), "application": name}
    parts = ["Application: " + name, "Window: " + (window.get_name() or "")[:250]]
    queue = [(window, 0)]
    visited = 0
    while queue and visited < 80 and time.monotonic() < deadline:
        node, depth = queue.pop(0)
        visited += 1
        try:
            interfaces = node.get_interfaces()
            if (node.get_role() == Atspi.Role.PASSWORD_TEXT
                    or any(interface.rsplit(".", 1)[-1] == "EditableText" for interface in interfaces)):
                continue
            state = node.get_state_set()
            if state.contains(Atspi.StateType.EDITABLE):
                continue
            if not state.contains(Atspi.StateType.SHOWING):
                continue
            label = (node.get_name() or "")[:250]
            if label and label not in parts:
                parts.append(label)
            text = node.get_text_iface()
            if text is not None:
                value = text.get_text(0, min(1000, text.get_character_count()))
                if value:
                    parts.append(value)
            if sum(map(len, parts)) >= 6000:
                break
            if depth < 5:
                for i in range(min(20, node.get_child_count())):
                    queue.append((node.get_child_at_index(i), depth + 1))
        except Exception:
            continue
    if not unlocked(Gio):
        return {"ok": False, "reason": "Desktop locked during observation"}
    return {"ok": True, "application": name, "text": "\n".join(parts)[:6000]}


if __name__ == "__main__":
    try:
        result = snapshot("--metadata-only" in sys.argv[1:])
    except Exception:
        result = {"ok": False, "reason": "GNOME accessibility unavailable. Check session access and distro AT-SPI/GI packages."}
    print(json.dumps(result))
