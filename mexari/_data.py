"""
mexari._data
============
Resolves the path to the bundled mortality CSV data file.
Municipality geometry is expected as an external GeoJSON input.
"""

from pathlib import Path

# The data/ directory lives next to this file inside the package.
_PKG_DIR = Path(__file__).parent
DEFAULT_CSV: Path = _PKG_DIR / "data" / "mortality_rates.csv"
