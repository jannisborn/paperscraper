import asyncio
import logging
import re
import sys
from typing import Dict, Iterable, Literal, Union

import httpx
from semanticscholar import SemanticScholar

from ..utils import optional_async
from .entity import Paper, Researcher
from .utils import check_overlap, doi_pattern

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

ModeType = Literal[MODES := ("paper", "author")]


class SelfLinkClient:
    def __init__(self, entity: str, mode: ModeType = "paper") -> None:
        if self.mode == "paper":
            self.object = Paper(entity)

        elif mode == "author":
            self.object = Researcher(entity)

    def extract_self_citations(self):
        self.object.self_citations()

    def extract_self_references(self):
        self.object.self_references()

    def extract(self):
        self.extract_self_citations()
        self.extract_self_references()

    def get_result(self):
        return self.object.get_result()
