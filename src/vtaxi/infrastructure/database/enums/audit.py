"""See docs/03-DATABASE-DESIGN.md SS2.5, table `audit_log_entries`
(now `audit_logs`, see models/audit.py).

Superseded design: docs/03's original `AuditAction` was a closed,
domain-specific vocabulary (DRIVER_APPROVED, COMPLAINT_RESOLVED, ...) for
an admin-only log. This round repositions `AuditLog` as a general
security/business event log -- `actor_user_id` is nullable (any user, or
the system, not just admins) and gains `target_user_id` -- paired with a
generic verb (this enum) plus `entity_type`/`entity_id` on the row itself
to say *what* was created/updated/approved/etc. This scales better than an
ever-growing list of "X_APPROVED" values, one per entity type.
"""

from enum import StrEnum


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    BOOK = "BOOK"
    CANCEL = "CANCEL"
    START = "START"
    COMPLETE = "COMPLETE"
