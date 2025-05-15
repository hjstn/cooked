from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from .consent_action import ConsentAction

@dataclass
class CookieConsentResult:
    """Result of cookie consent collection for a single URL"""
    url: str
    popup_found: bool
    action_taken: Optional[ConsentAction] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    cmp_detected: Optional[str] = None
    cookies: Optional[Set[str]] = None
