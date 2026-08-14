"""See docs/03-DATABASE-DESIGN.md SS2.1, table `users`."""

from enum import StrEnum


class UserRole(StrEnum):
    PASSENGER = "PASSENGER"
    DRIVER = "DRIVER"
    ADMIN = "ADMIN"
