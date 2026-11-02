"""Limits of the workspace library of reusable sections (docs/reusable-sections.md)."""

# questions of one section, group children included
QUESTIONS_PER_SECTION = 50
CONTAINERS_PER_SECTION = 10
SECTIONS_PER_WORKSPACE = 200
# the serialised content (fields + containers) of one version
CONTENT_BYTES_MAX = 200_000
# the current version and the ones before it, kept for the diff
VERSIONS_KEPT = 10
NAME_MAX = 100
DESCRIPTION_MAX = 500
