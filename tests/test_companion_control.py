from types import SimpleNamespace

from ai_os import companion_control


def test_stop_targets_only_same_user_exact_companion(monkeypatch):
    calls = []
    def process(pid, args, uid=1000):
        return SimpleNamespace(pid=pid, info={'cmdline':args,'uids':SimpleNamespace(real=uid)},
                               terminate=lambda: calls.append(pid))
    candidates = [process(10,['python','-m','ai_os.avatar_overlay']),
                  process(11,['python','-m','ai_os.ai_os_core']),
                  process(12,['python','-c','code','-m','ai_os.avatar_overlay']),
                  process(13,['python','-m','ai_os.avatar_overlay'],uid=1001)]
    monkeypatch.setattr(companion_control.os,'getuid',lambda:1000)
    monkeypatch.setattr(companion_control.os,'getpid',lambda:99)
    monkeypatch.setattr(companion_control.psutil,'process_iter',lambda fields:candidates)
    monkeypatch.setattr(companion_control.psutil,'wait_procs',lambda targets,timeout:(targets,[]))
    assert companion_control.stop()['ok']
    assert calls == [10]
