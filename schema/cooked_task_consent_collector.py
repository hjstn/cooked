from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from .cooked_consent_action import CookedConsentAction

@dataclass
class CookedTaskConsentCollector:
    """
    Task for collecting cookie consent information from a group of websites.
    
    This represents a single site with potentially multiple URLs to check for
    cookie consent banners and interactions.
    """
    site: str
    urls: List[str] 
    action: str