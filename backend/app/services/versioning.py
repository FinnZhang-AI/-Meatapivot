"""Semantic versioning utilities for Ontology compile logs.

P0-ONT-05: Semver-based versioning for ontology compilation.
- major: breaking changes (e.g., property type changes, removed properties)
- minor: non-breaking additions (e.g., new properties, new types)
- patch: fixes / no schema change (e.g., display_name updates)
"""

from typing import Optional, Tuple


class VersionInfo:
    """Parsed semantic version."""

    def __init__(self, major: int, minor: int, patch: int):
        self.major = major
        self.minor = minor
        self.patch = patch

    @classmethod
    def parse(cls, version_str: str) -> "VersionInfo":
        """Parse a semver string like '1.2.3'."""
        parts = version_str.strip().lstrip("v").split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid semver format: {version_str}. Expected major.minor.patch")
        return cls(int(parts[0]), int(parts[1]), int(parts[2]))

    def bump_major(self) -> "VersionInfo":
        return VersionInfo(self.major + 1, 0, 0)

    def bump_minor(self) -> "VersionInfo":
        return VersionInfo(self.major, self.minor + 1, 0)

    def bump_patch(self) -> "VersionInfo":
        return VersionInfo(self.major, self.minor, self.patch + 1)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionInfo):
            return NotImplemented
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other: "VersionInfo") -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: "VersionInfo") -> bool:
        return self == other or self < other

    def __gt__(self, other: "VersionInfo") -> bool:
        return not self <= other

    def __ge__(self, other: "VersionInfo") -> bool:
        return not self < other


def compute_next_version(
    current_version: Optional[str],
    diff_snapshot: dict,
) -> Tuple[str, str]:
    """Compute next version based on schema diff.

    Args:
        current_version: Current semver string (e.g. '1.3.0') or None.
        diff_snapshot: Dict with change categories:
            - breaking: list of breaking changes
            - additions: list of non-breaking additions
            - modifications: list of minor modifications

    Returns:
        (new_version, bump_type) where bump_type is 'major'|'minor'|'patch'
    """
    current = VersionInfo.parse(current_version) if current_version else VersionInfo(0, 0, 0)

    breaking = diff_snapshot.get("breaking", [])
    additions = diff_snapshot.get("additions", [])
    modifications = diff_snapshot.get("modifications", [])

    if breaking:
        return str(current.bump_major()), "major"
    elif additions:
        return str(current.bump_minor()), "minor"
    elif modifications:
        return str(current.bump_patch()), "patch"
    else:
        # No changes — keep current version
        return str(current), "none"


def build_diff_snapshot(
    old_object_types: list,
    new_object_types: list,
) -> dict:
    """Build a diff snapshot between two sets of ObjectType definitions.

    Returns dict with keys:
        - breaking: list[str]
        - additions: list[str]
        - modifications: list[str]
    """
    old_map = {ot.get("name", str(ot.get("id"))): ot for ot in old_object_types}
    new_map = {ot.get("name", str(ot.get("id"))): ot for ot in new_object_types}

    breaking = []
    additions = []
    modifications = []

    # Check for removed types (breaking)
    for name in old_map:
        if name not in new_map:
            breaking.append(f"Removed ObjectType: {name}")

    # Check for new types (addition)
    for name in new_map:
        if name not in old_map:
            additions.append(f"Added ObjectType: {name}")
            continue

        old_ot = old_map[name]
        new_ot = new_map[name]

        # Compare properties
        old_props = {p.get("name"): p for p in old_ot.get("properties", []) if isinstance(p, dict)}
        new_props = {p.get("name"): p for p in new_ot.get("properties", []) if isinstance(p, dict)}

        # Removed properties (breaking)
        for prop_name in old_props:
            if prop_name not in new_props:
                breaking.append(f"{name}: removed property '{prop_name}'")

        # Added properties (addition)
        for prop_name in new_props:
            if prop_name not in old_props:
                additions.append(f"{name}: added property '{prop_name}'")
                continue

            # Type change (breaking)
            old_type = old_props[prop_name].get("base_type") or old_props[prop_name].get("type")
            new_type = new_props[prop_name].get("base_type") or new_props[prop_name].get("type")
            if old_type and new_type and old_type != new_type:
                breaking.append(f"{name}: property '{prop_name}' type changed from {old_type} to {new_type}")
                continue

            # Required flag change: optional -> required (breaking)
            old_required = old_props[prop_name].get("required", False)
            new_required = new_props[prop_name].get("required", False)
            if not old_required and new_required:
                breaking.append(f"{name}: property '{prop_name}' became required")

            # Any other property attribute change (modification)
            if old_props[prop_name] != new_props[prop_name]:
                modifications.append(f"{name}: property '{prop_name}' modified")

        # Compare other fields
        for field in ("display_name", "description", "icon", "neo4j_label"):
            if old_ot.get(field) != new_ot.get(field):
                modifications.append(f"{name}: {field} updated")

    return {
        "breaking": breaking,
        "additions": additions,
        "modifications": modifications,
    }
