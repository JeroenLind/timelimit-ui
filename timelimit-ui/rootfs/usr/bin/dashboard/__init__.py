"""The new TimeLimit parent dashboard (rebuild; see docs/architecture/design.md).

Layers (design section 2): routes -> services -> domain | repository | client; ``sync`` holds the
sync engine. The old ``dashboardV2`` package stays until the cut-over (plan step G1).
"""
