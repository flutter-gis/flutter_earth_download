"""
Manifest management for tracking processed tiles and mosaics.
"""
import os
import csv
import json
from datetime import datetime
from typing import List

from .config import MANIFEST_CSV


def manifest_init(path: str = MANIFEST_CSV):
    """Initialize manifest CSV file with headers."""
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["year", "month", "mosaic", "cog", "tiles", "provenance_json", "timestamp"])


def manifest_append(year: int, month: int, mosaic: str, cog: str, tiles: List[str], 
                   prov_json: str, path: str = MANIFEST_CSV):
    """Append entry to manifest CSV."""
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([year, month, mosaic, cog, json.dumps(tiles), prov_json, datetime.utcnow().isoformat()])

