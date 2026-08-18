from ai_os.tools.system_tools import RiskLevel, assess_command


def test_safe_read_command() -> None:
    assessment = assess_command(["uname", "-a"])
    assert assessment.risk == RiskLevel.SAFE
    assert assessment.requires_approval is False


def test_sudo_requires_approval() -> None:
    assessment = assess_command(["sudo", "pacman", "-S", "vim"])
    assert assessment.risk == RiskLevel.DESTRUCTIVE
    assert assessment.requires_approval is True


def test_root_recursive_delete_is_prohibited() -> None:
    assessment = assess_command(["rm", "-rf", "/"])
    assert assessment.risk == RiskLevel.PROHIBITED
    assert assessment.requires_approval is True


def test_pacman_query_is_safe() -> None:
    assessment = assess_command(["pacman", "-Q", "python"])
    assert assessment.risk == RiskLevel.SAFE
    assert assessment.requires_approval is False

