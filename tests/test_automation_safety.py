
from dexter_autonomy.core.policy_overlay import CompositeDenyPolicy
from dexter_autonomy.core.profiles import load_profiles, select_profile


def _policy() -> CompositeDenyPolicy:
    profiles = load_profiles("configs/denylist.profiles.yml")
    profile = select_profile(profiles, "medium")
    return CompositeDenyPolicy(profile)


def test_hotkey_deny():
    policy = _policy()
    allowed, _ = policy.allow_hotkey("ALT+F4")
    assert not allowed
