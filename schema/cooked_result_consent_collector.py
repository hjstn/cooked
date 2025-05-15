from typing import Optional, Set

from dataclasses import dataclass, field

from schema.cooked_consent_action import CookedConsentAction

@dataclass
class CookedResultConsentCollector:
    """Result of cookie consent collection for a single URL"""
    site: str = ''
    action: CookedConsentAction = CookedConsentAction.BASELINE

    cookies: Set[str] = field(default_factory=set)
    cmps: Set[str] = field(default_factory=set)
    popups: Set[str] = field(default_factory=set)

    pages_with_cmps: int = 0
    pages_with_popups: int = 0

    success: bool = False
    error: Optional[str] = None