"""Shared two-party role vocabulary.

See docs/03-DATABASE-DESIGN.md SS2.5, columns `ratings.rater_role` and
`complaints.reporter_role`. Deliberately distinct from `UserRole`
(identity.py): a `User` can be an ADMIN too, but a rating or a complaint
is always framed as one of these two parties, one rating/reporting the
other -- consolidated into one enum instead of two identical ones.
"""

from enum import StrEnum


class PartyRole(StrEnum):
    PASSENGER = "PASSENGER"
    DRIVER = "DRIVER"
