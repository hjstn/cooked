from typing import List

from dataclasses import dataclass

@dataclass
class CookedResultInternalCrawler():
    rank: int
    site: str
    urls: List[str]