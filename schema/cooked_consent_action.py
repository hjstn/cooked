from enum import Enum

class CookedConsentAction(Enum):
    """Possible actions to take on a cookie consent banner"""
    BASELINE = "none"         # Take no action
    OPT_IN   = "optIn"      # Accept all cookies
    OPT_OUT  = "optOut"    # Reject non-essential cookies