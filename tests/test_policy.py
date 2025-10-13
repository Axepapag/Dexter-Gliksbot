
from dexter_autonomy.core.policy_overlay import CompositeDenyPolicy
from dexter_autonomy.core.profiles import load_profiles, select_profile


def _policy() -> CompositeDenyPolicy:
    profiles = load_profiles("configs/denylist.profiles.yml")
    profile = select_profile(profiles, "medium")
    return CompositeDenyPolicy(profile)


def test_deny_process():
    policy = _policy()
    allowed, _ = policy.allow_process("shutdown.exe")
    assert not allowed


def test_allow_safe_process():
    policy = _policy()
    allowed, _ = policy.allow_process("notepad.exe")
    assert allowed
