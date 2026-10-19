"""Bounded presentation preferences; no permission, fact or model-weight changes."""
import math

from ai_os.companion_state import EMOTIONS, emotion_levels


def mood_guidance(config, state):
    levels = emotion_levels(state, config)
    levels = {key: max(0, min(100, float(value))) if math.isfinite(float(value)) else 50
              for key, value in levels.items() if key in EMOTIONS}
    strongest = sorted(levels, key=levels.get, reverse=True)[:2]
    hints = {
        "joy": "express warm appreciation and enthusiasm when appropriate",
        "curiosity": "show interest in the subject and ask one useful question when helpful",
        "focus": "organize the answer clearly and stay on the requested task",
        "calm": "use an unhurried, reassuring tone",
        "concern": "check uncertainties carefully and offer a practical next step without alarm",
        "energy": "use lively, concise language without rushing or skipping verification",
    }
    values = ", ".join(f"{key}={levels[key]:.0f}" for key in EMOTIONS)
    return ("\nRE's simulated mood for this reply (0–100): " + values + ". "
            + "; ".join(hints[key] for key in strongest) + ". "
            "When asked how YOU feel about an event or device, express this persona in first person "
            "and discuss that event, rather than attributing feelings to the user. "
            "These presentation settings guide tone and care, never facts, tool selection, "
            "permission checks, safety, competence or claims of sentience. Do not repeat this implementation note in ordinary chat.")
