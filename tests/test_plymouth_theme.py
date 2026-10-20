"""Optional real upstream script interpreter checks, with mocked graphics only.

Set REGENOS_PLYMOUTH_SOURCE_DIR to a separately reviewed, flattened source subset
from upstream Plymouth 26.134.222. Tests never download, install or start anything.
The bridge compiles into pytest's temporary directory; it cannot prove boot,
Pango rendering, keyboard handling or actual display/password integration.
"""

from pathlib import Path
import os
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
THEME = ROOT / "branding" / "plymouth" / "regenos.script"


@pytest.fixture(scope="module")
def plymouth_runner(tmp_path_factory):
    location = os.environ.get("REGENOS_PLYMOUTH_SOURCE_DIR")
    if not location:
        pytest.skip("Optional upstream Plymouth source interpreter is not configured")
    source = Path(location).resolve()
    compiler = shutil.which("cc")
    if not compiler:
        pytest.skip("A C compiler is unavailable; no package is installed by these tests")
    names = (
        "script", "script-debug", "script-scan", "script-parse", "script-object",
        "script-execute", "ply-list", "ply-hashtable", "ply-bitarray",
    )
    units = [source / f"{name}.c" for name in names]
    required = units + [source / f"{name}.h" for name in names]
    required += [source / "ply-utils.h", source / "ply-logger.h",
                 source / "script-lib-math.script"]
    assert all(path.is_file() for path in required), "Incomplete reviewed source subset"
    binary = tmp_path_factory.mktemp("plymouth-script-check") / "runner"
    build = subprocess.run(
        [compiler, "-D_GNU_SOURCE", "-std=gnu11", "-I", str(source),
         str(FIXTURES / "plymouth_script_runner.c"), *map(str, units),
         "-lm", "-o", str(binary)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert build.returncode == 0, build.stderr
    return binary, source


def run_contract(runner, tmp_path, checks, *, setup=""):
    binary, source = runner
    program = tmp_path / "contract.script"
    program.write_text(
        (source / "script-lib-math.script").read_text()
        + "\n" + (FIXTURES / "plymouth_graphics_mocks.script").read_text()
        + "\n" + setup + "\n" + THEME.read_text() + "\n" + checks,
        encoding="utf-8",
    )
    result = subprocess.run(
        [str(binary), str(program)], capture_output=True, text=True,
        timeout=5, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "errors=0" in result.stdout


def test_password_masking_backspace_prompt_and_normal_cleanup(plymouth_runner, tmp_path):
    run_contract(plymouth_runner, tmp_path, '''
on_password("Unlock test volume", 4);
Check(state.mode == "password" && state.answer == "****", "legacy password masking");
Check(prompt.sprite.image.text == "Unlock test volume", "native prompt is retained");
Check(answer.sprite.opacity == 1, "password feedback is visible");
on_refresh();
Check(dot.sprite[0].opacity == 0, "animation pauses during prompt");
on_password("Unlock test volume", 1);
Check(state.answer == "*", "backspace removes old bullets");
on_password("", -5);
Check(state.answer == "" && state.prompt == "Enter passphrase", "empty negative count safe");
on_password("Unlock test volume", 100000);
Check(state.answer.Length() == 64, "visual allocation is bounded");
on_prompt("Unlock test volume", "PUBLIC-SECRET-TEST", 1);
Check(state.answer.Length() == 18, "modern secret prompt is masked");
Check(mock.secret_rendered == 0, "secret never becomes a rendered image");
on_prompt(NULL, NULL, 1);
Check(state.answer == "", "null secret input remains safe");
on_normal();
Check(state.answer == "" && state.prompt == "", "normal drops input state");
Check(answer.sprite.opacity == 0 && prompt.sprite.opacity == 0, "normal hides entry sprites");
''')


def test_questions_latest_messages_and_quit_cleanup(plymouth_runner, tmp_path):
    run_contract(plymouth_runner, tmp_path, '''
on_question("Choose a recovery slot", "slot A");
Check(state.mode == "question" && state.answer == "slot A", "question entry remains visible");
on_prompt("Choose a recovery slot", "slot B", 0);
Check(answer.sprite.image.text == "slot B", "modern nonsecret prompt is visible");
on_message("Earlier status");
on_message("Latest failure");
on_hide_message("Earlier status");
Check(state.message == "Latest failure" && message.sprite.opacity == 1, "old hide keeps current failure");
on_normal();
Check(state.message == "Latest failure", "normal does not discard failure text");
on_hide_message("Latest failure");
Check(message.sprite.opacity == 0 && state.message == "", "matching hide clears message");
on_question(NULL, "");
Check(state.prompt == "Input required" && state.answer == "_", "empty question fallback");
on_quit();
on_refresh();
Check(state.answer == "" && state.prompt == "" && state.message == "", "quit drops displayed input");
Check(answer.sprite.opacity == 0 && dot.sprite[0].opacity == 0, "quit remains still");
''')


def test_smallest_display_resize_and_long_prompt_fit(plymouth_runner, tmp_path):
    run_contract(plymouth_runner, tmp_path, '''
Check(view.width == 1280 && view.height == 720, "fit smallest head");
Check(brand.sprite.image.GetWidth() <= 192, "logo has bounded size");
mock.width[1] = 480;
mock.height[1] = 320;
mock.x = -120;
mock.y = -80;
on_hotplug();
Check(view.width == 480 && view.height == 320, "hotplug recomputes fit");
Check(brand.sprite.image.GetHeight() <= 80, "small display logo fits");
Check(brand.sprite.x >= view.x - view.width / 2, "logo stays inside left edge");
Check(brand.sprite.x + brand.sprite.image.GetWidth() <= view.x + view.width / 2, "logo stays inside right edge");
on_question("Long public test prompt that must remain within the active display instead of overflowing into its neighbours", "test answer");
Check(prompt.sprite.image.GetWidth() <= view.width * 0.88, "long prompt fits width");
Check(prompt.sprite.image.GetHeight() <= view.height * 0.11, "long prompt fits height");
mock.width[1] = 640;
mock.height[1] = 480;
on_refresh();
Check(view.width == 640 && state.mode == "question", "resize preserves active prompt");
Check(prompt.sprite.opacity == 1 && answer.sprite.opacity == 1, "resize redraws prompt");
''')


def test_missing_optional_art_keeps_wordmark_and_prompts(plymouth_runner, tmp_path):
    run_contract(plymouth_runner, tmp_path, '''
Check(brand.sprite.opacity == 0, "missing logo remains hidden");
Check(title.sprite.opacity == 1 && title.sprite.image.text == "REgenOS", "text identity fallback");
on_password("Unlock test volume", 2);
on_refresh();
Check(answer.sprite.image.text == "**", "prompts do not depend on optional art");
on_normal();
on_refresh();
Check(dot.sprite[0].opacity == 0, "missing dot image remains safe");
''', setup="mock.missing_logo = 1; mock.missing_dot = 1;")


def test_progress_is_bounded_and_keyboard_is_left_to_plymouth(plymouth_runner, tmp_path):
    run_contract(plymouth_runner, tmp_path, '''
Check(Math.Int(-0.5) == -1 && Math.Clamp(2, 0, 1) == 1, "reviewed upstream math contract");
on_progress(1, -2);
Check(state.progress == 0, "negative progress is bounded");
on_progress(1, 3);
Check(state.progress == 1, "overflow progress is bounded");
on_system_update(42);
Check(state.progress > 0.4199 && state.progress < 0.4201, "system update percentage scale");
for (iteration = 0; iteration < 300; iteration++) on_refresh();
Check(state.phase >= 0 && state.phase <= 6.28318, "animation phase stays bounded");
Check(dot.sprite[0].opacity >= 0 && dot.sprite[0].opacity <= 1, "animation opacity stays bounded");
Check(on_keyboard == NULL && on_validate_input == NULL, "no input interception");
''')


def test_compact_named_wordmark_stays_above_authentication(plymouth_runner,tmp_path):
    run_contract(plymouth_runner,tmp_path, '''
Check(brand.wordmark, "compact wordmark is preferred");
Check(brand.sprite.image.GetWidth() <= 144 && brand.sprite.image.GetHeight() <= 48, "native wordmark is compact");
Check(title.sprite.opacity == 0, "name is not duplicated below the wordmark");
on_password("Unlock test volume", 3);
Check(brand.sprite.y + brand.sprite.image.GetHeight() < prompt.sprite.y, "wordmark does not obstruct the prompt");
Check(answer.sprite.opacity == 1, "masked input remains visible");
''')
