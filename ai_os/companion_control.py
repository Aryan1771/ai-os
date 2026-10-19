"""Human-operated stop control for this user's exact companion entry points."""
import json
import os
from pathlib import Path

import psutil


def stop():
    targets = []
    for process in psutil.process_iter(['pid', 'cmdline', 'uids']):
        try:
            if process.pid == os.getpid() or process.info['uids'].real != os.getuid():
                continue
            argv = process.info['cmdline'] or []
            module = argv[1:3] == ['-m', 'ai_os.avatar_overlay']
            script = any(Path(arg).name == 'regenos-companion' for arg in argv[:2])
            if module or script:
                process.terminate()
                targets.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    _, alive = psutil.wait_procs(targets, timeout=3)
    return {'ok': bool(targets) and not alive,
            'message': ('Companion closed.' if targets and not alive else
                        'Companion did not exit; no forced kill was sent.' if alive else
                        'No companion is visible from this environment. Run this command in your desktop terminal.')}


if __name__ == '__main__':
    print(json.dumps(stop()))
