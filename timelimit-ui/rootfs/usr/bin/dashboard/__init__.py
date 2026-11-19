"""The new TimeLimit parent dashboard (rebuild; see docs/architecture/design.md).

Layers (design section 2): routes -> services -> domain | repository | client; ``sync`` holds the
sync engine. This package is the only application (the old ``dashboardV2`` was removed in plan step G1).
"""

# The one place the version is written by hand; config.yaml must say the same (a test compares them).
__version__ = "1.0.0"
