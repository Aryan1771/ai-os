"""Optional local speaker filtering; no recognition result grants permissions."""
from pathlib import Path
import json
import subprocess
import sys
import time

from ai_os.config import atomic_json, load_raw_config

CHECK_TIMEOUT_SECONDS = 10
MESSAGES = {
    "speaker_matched": "Enrolled voice matched.",
    "speaker_rejected": "Voice did not pass the enrolled-speaker filter; no request submitted.",
    "speaker_unavailable": "Speaker verification unavailable; no request submitted. Check local enrollment.",
    "speaker_timeout": "Speaker verification timed out; no request submitted. Check the local speaker model.",
}


def filter_utterance(audio_path: Path, home: Path) -> tuple[bool, str]:
    if not load_raw_config(home)["speaker_recognition_enabled"]:
        return True, "Speaker filtering is disabled."
    allowed, code = False, "speaker_unavailable"
    try:
        # Keep native model inference outside the recorder worker. A stalled
        # backend must not leave listening blocked indefinitely. No model data,
        # embeddings, similarity values or recordings are returned on stdout.
        result = subprocess.run(
            [sys.executable, "-m", "ai_os.speaker_identity", "--check",
             str(Path(audio_path).resolve()), "--home", str(Path(home).resolve())],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, check=False, timeout=CHECK_TIMEOUT_SECONDS, shell=False,
        )
        if result.returncode == 0 and len(result.stdout) <= 2048:
            report = json.loads(result.stdout)
            if (isinstance(report, dict) and type(report.get("allowed")) is bool
                    and report.get("code") in {"speaker_matched", "speaker_rejected", "speaker_unavailable"}
                    and report["allowed"] is (report["code"] == "speaker_matched")):
                allowed, code = report["allowed"], report["code"]
    except subprocess.TimeoutExpired:
        code = "speaker_timeout"
    except Exception:
        # Failure at this optional backend boundary always denies admission.
        pass
    # Keep recordings, transcripts, embeddings and similarity scores out of status.
    public = MESSAGES[code]
    atomic_json(home / "run/speaker-status.json", {
        "matched": bool(allowed), "code": code, "message": public, "updated": time.time(),
    })
    return bool(allowed), public
