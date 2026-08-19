import tomllib
from pathlib import Path


CONFIG_PATH = Path(__file__).parent / "config.toml"

with open(CONFIG_PATH, "rb") as f:
    _raw = tomllib.load(f)


ROLE_KEYWORDS: list[str] = _raw["discovery"]["role_keywords"]
SENIORITY_BLOCK: list[str] = _raw["discovery"]["seniority_block"]
FEEDS: list[dict[str, str]] = _raw["discovery"]["feeds"]
MAX_PER_FEED: int = _raw["discovery"].get("max_per_feed", 25)
