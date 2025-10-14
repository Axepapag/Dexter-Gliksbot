"""
Common action parsing utilities.
This is a stub - AUM functionality is now merged into Dexter.
"""
from typing import Any, Dict, List


def parse_actions_fallback(text: str) -> List[Dict[str, Any]]:
    """
    Deterministic fallback parser for actions.
    NOTE: This is legacy - action extraction is now in DexterOrchestrator._parse_actions_fallback()
    """
    return []
