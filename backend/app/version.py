"""Meatapivot version info.

Single source of truth: app.__init__.__version__
"""

try:
    from app import __version__
except ImportError:  # pragma: no cover
    __version__ = "2.2.0"


def parse_version_info(v: str):
    """Parse semver string into tuple, ignoring pre-release suffixes."""
    import re
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", v)
    if not m:
        raise ValueError(f"Invalid semver: {v}")
    return tuple(int(g) for g in m.groups())


__version_info__ = parse_version_info(__version__)
