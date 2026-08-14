"""Table `admin_profiles`. Resolves docs/03-DATABASE-DESIGN.md SS6 item 2
(previously left flat/undecided) -- now explicitly tiered.
"""

from enum import StrEnum


class AdminRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    MODERATOR = "MODERATOR"
    SUPPORT = "SUPPORT"
