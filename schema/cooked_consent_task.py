from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from .consent_action import ConsentAction

@dataclass
class CookedConsentTask:
    """
    Task for collecting cookie consent information from a group of websites.
    
    This represents a single site with potentially multiple URLs to check for
    cookie consent banners and interactions.
    """
    # List of URLs to check for cookie consent (if empty, will use https://{site})
    urls: List[str] 
    action: ConsentAction 