from enum import Enum

class ConsentAction(Enum):
    """Possible actions to take on a cookie consent banner"""
    OPT_IN = "optIn"      # Accept all cookies
    OPT_OUT = "optOut"    # Reject non-essential cookies
    BASELINE = "none"         # Take no action