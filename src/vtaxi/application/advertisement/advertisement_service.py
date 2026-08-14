"""`AdvertisementService` -- a driver's published listing: management,
seat counters, cross-domain eligibility checks, and status-machine
transitions.

Every method opens its own Unit of Work via the injected factory and is
therefore independently atomic, same discipline as every service so far.
Nothing here imports SQLAlchemy, Aiogram, or FastAPI -- only `ports.py`
(structural Protocols) and the ORM classes themselves for typing (see
`application/identity/ports.py`'s docstring for why that's not a
"framework independent" violation in this project).

Status machine (`AdvertisementStatus`: DRAFT/ACTIVE/FULL/CLOSED/CANCELLED/
EXPIRED) as implemented here:

    DRAFT --activate--> ACTIVE <--activate-- FULL
      |  \\--deactivate--/  |  \\--deactivate--/
      |                     |
      +---------close-------+-------close------> CLOSED (terminal)
      |                     |
      +--------delete-------+------delete------> CANCELLED --restore--> DRAFT
      |                     |
      +--------(sweep)------+-----expire-------> EXPIRED (terminal)

`CLOSED`/`EXPIRED` are terminal: no method ever transitions out of them.
`FULL -> ACTIVE` via `activate_advertisement()` is deliberately allowed
(seats may have freed up) -- the brief's "FULL advertisements cannot
become ACTIVE automatically" blocks an *automatic* side effect of a seat
counter changing, not this explicit, re-validated call. `CANCELLED` is
this service's stand-in for "deleted": `Advertisement` has no
`SoftDeleteMixin` by design (see models/advertisement.py's docstring --
"this table's own status enum already covers 'is this gone'"), so
`delete_advertisement()`/`restore_advertisement()` map onto this same
status column rather than a `deleted_at` column or a real `DELETE`.

Seat counters (`available_seats`/`reserved_seats`) only ever move by the
four dedicated methods below -- "Only manage seat counters," per this
step's own brief: no method here creates, reads, or references a
`Booking` (that domain does not exist yet).
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.core.domain.result import Failure
from vtaxi.domain.advertisement.exceptions import (
    AdvertisementAlreadyActiveError,
    AdvertisementCancelledError,
    AdvertisementClosedError,
    AdvertisementDirectionNotEligibleError,
    AdvertisementDriverNotEligibleError,
    AdvertisementExpiredError,
    AdvertisementFullError,
    AdvertisementInsufficientSeatsError,
    AdvertisementInvalidDataError,
    AdvertisementInvalidStatusTransitionError,
    AdvertisementNotFoundError,
    AdvertisementSeatLimitExceededError,
    AdvertisementVehicleNotEligibleError,
)
from vtaxi.infrastructure.database.enums import (
    AdvertisementStatus,
    DriverApprovalStatus,
    DriverAvailabilityStatus,
    VerificationStatus,
)
from vtaxi.infrastructure.database.models.advertisement import Advertisement

from .ports import AdvertisementUnitOfWork

# `expires_at` is a required column with a `departure_time < expires_at`
# CHECK constraint (models/advertisement.py); the brief does not specify a
# default expiry window, so a caller of `create_advertisement()` who omits
# `expires_at` gets one computed this far past `departure_time`.
_DEFAULT_EXPIRY_BUFFER = timedelta(hours=1)


def _as_aware_utc(value: datetime) -> datetime:
    """Every timestamp in this system is UTC by convention
    (infrastructure/database/types.py), but SQLite -- used for this
    project's empirical verification, since no Postgres/Docker sandbox is
    available -- does not round-trip `tzinfo` through a
    `DateTime(timezone=True)` column the way PostgreSQL does: a value read
    back from it comes back naive. A naive value is therefore always
    safely re-interpreted as UTC before comparing it against
    `datetime.now(UTC)`.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class AdvertisementService:
    def __init__(self, uow_factory: UnitOfWorkFactory[AdvertisementUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # --- Advertisement Validation (private helpers) -----------------------
    # Each returns `Failure | None` and is shared by the public `validate_*`
    # wrapper below *and* by `create_advertisement()`/`activate_advertisement()`
    # -- same pattern as `VehicleService._document_completeness_violation`,
    # avoiding the `Result[None]`-vs-`Result[Advertisement]` covariance
    # mismatch mypy would otherwise flag.

    def _departure_time_violation(self, departure_time: datetime) -> Failure | None:
        if _as_aware_utc(departure_time) <= datetime.now(UTC):
            return fail(AdvertisementInvalidDataError, "Departure time cannot be in the past.")
        return None

    async def _vehicle_ineligibility(
        self, vehicle_id: uuid.UUID, driver_profile_id: uuid.UUID, uow: AdvertisementUnitOfWork
    ) -> Failure | None:
        vehicle = await uow.vehicles.get_by_id(vehicle_id)
        if vehicle is None:
            return fail(AdvertisementVehicleNotEligibleError, "The given vehicle does not exist.")
        if vehicle.deleted_at is not None:
            return fail(AdvertisementVehicleNotEligibleError, "This vehicle has been deleted.")
        if vehicle.driver_profile_id != driver_profile_id:
            return fail(
                AdvertisementVehicleNotEligibleError,
                "This vehicle does not belong to the given driver.",
            )
        if vehicle.verification_status != VerificationStatus.APPROVED:
            return fail(
                AdvertisementVehicleNotEligibleError, "This vehicle has not been approved yet."
            )
        return None

    async def _driver_ineligibility(
        self, driver_profile_id: uuid.UUID, uow: AdvertisementUnitOfWork
    ) -> Failure | None:
        driver = await uow.drivers.get_by_id(driver_profile_id)
        if driver is None:
            return fail(AdvertisementDriverNotEligibleError, "The given driver does not exist.")
        if driver.deleted_at is not None:
            return fail(
                AdvertisementDriverNotEligibleError, "This driver's profile has been deleted."
            )
        if driver.availability_status == DriverAvailabilityStatus.BANNED:
            return fail(AdvertisementDriverNotEligibleError, "This driver is banned.")
        if driver.approval_status != DriverApprovalStatus.APPROVED:
            return fail(
                AdvertisementDriverNotEligibleError, "This driver has not been approved yet."
            )
        return None

    async def _direction_ineligibility(
        self, direction_id: uuid.UUID, uow: AdvertisementUnitOfWork
    ) -> Failure | None:
        direction = await uow.geography.get_direction(direction_id)
        if direction is None:
            return fail(
                AdvertisementDirectionNotEligibleError, "The given direction does not exist."
            )
        if not direction.is_active:
            return fail(
                AdvertisementDirectionNotEligibleError,
                "This direction is not currently active.",
            )
        return None

    async def _pickup_location_violation(
        self,
        pickup_area_id: uuid.UUID,
        destination_area_id: uuid.UUID,
        uow: AdvertisementUnitOfWork,
    ) -> Failure | None:
        if pickup_area_id == destination_area_id:
            return fail(
                AdvertisementInvalidDataError, "Pickup and destination areas cannot be the same."
            )
        if await uow.geography.get_by_id(pickup_area_id) is None:
            return fail(AdvertisementInvalidDataError, "The given pickup area does not exist.")
        if await uow.geography.get_by_id(destination_area_id) is None:
            return fail(AdvertisementInvalidDataError, "The given destination area does not exist.")
        return None

    # --- Advertisement Validation (public) --------------------------------

    async def validate_departure_time(self, departure_time: datetime) -> Result[None]:
        violation = self._departure_time_violation(departure_time)
        return violation if violation is not None else Result.ok(None)

    async def validate_vehicle(
        self, vehicle_id: uuid.UUID, driver_profile_id: uuid.UUID
    ) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._vehicle_ineligibility(vehicle_id, driver_profile_id, uow)
            return violation if violation is not None else Result.ok(None)

    async def validate_driver(self, driver_profile_id: uuid.UUID) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._driver_ineligibility(driver_profile_id, uow)
            return violation if violation is not None else Result.ok(None)

    async def validate_direction(self, direction_id: uuid.UUID) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._direction_ineligibility(direction_id, uow)
            return violation if violation is not None else Result.ok(None)

    async def validate_pickup_location(
        self, pickup_area_id: uuid.UUID, destination_area_id: uuid.UUID
    ) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._pickup_location_violation(
                pickup_area_id, destination_area_id, uow
            )
            return violation if violation is not None else Result.ok(None)

    # --- Advertisement Management ------------------------------------------

    async def create_advertisement(
        self,
        *,
        driver_profile_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        direction_id: uuid.UUID,
        pickup_area_id: uuid.UUID,
        destination_area_id: uuid.UUID,
        current_latitude: Any,
        current_longitude: Any,
        departure_time: datetime,
        price: Any,
        total_seats: int,
        expires_at: datetime | None = None,
        currency_code: str = "UZS",
        estimated_arrival_time: datetime | None = None,
        notes: str | None = None,
        is_priority: bool = False,
    ) -> Result[Advertisement]:
        departure_violation = self._departure_time_violation(departure_time)
        if departure_violation is not None:
            return departure_violation

        if expires_at is None:
            expires_at = departure_time + _DEFAULT_EXPIRY_BUFFER
        elif expires_at <= departure_time:
            return fail(AdvertisementInvalidDataError, "expires_at must be after departure_time.")

        async with self._uow_factory() as uow:
            violation = await self._vehicle_ineligibility(vehicle_id, driver_profile_id, uow)
            if violation is not None:
                return violation
            violation = await self._driver_ineligibility(driver_profile_id, uow)
            if violation is not None:
                return violation
            violation = await self._direction_ineligibility(direction_id, uow)
            if violation is not None:
                return violation
            violation = await self._pickup_location_violation(
                pickup_area_id, destination_area_id, uow
            )
            if violation is not None:
                return violation

            try:
                advertisement = await uow.advertisements.create(
                    driver_profile_id=driver_profile_id,
                    vehicle_id=vehicle_id,
                    direction_id=direction_id,
                    pickup_area_id=pickup_area_id,
                    destination_area_id=destination_area_id,
                    current_latitude=current_latitude,
                    current_longitude=current_longitude,
                    departure_time=departure_time,
                    estimated_arrival_time=estimated_arrival_time,
                    price=price,
                    currency_code=currency_code,
                    total_seats=total_seats,
                    available_seats=total_seats,
                    reserved_seats=0,
                    expires_at=expires_at,
                    notes=notes,
                    is_priority=is_priority,
                )
            except ValueError as exc:
                return fail(AdvertisementInvalidDataError, str(exc))
            return Result.ok(advertisement)

    async def get_advertisement(self, advertisement_id: uuid.UUID) -> Result[Advertisement]:
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            return Result.ok(advertisement)

    async def advertisement_exists(self, advertisement_id: uuid.UUID) -> Result[bool]:
        async with self._uow_factory() as uow:
            return Result.ok(await uow.advertisements.get_by_id(advertisement_id) is not None)

    async def update_advertisement(
        self, advertisement_id: uuid.UUID, **fields: Any
    ) -> Result[Advertisement]:
        """Only a `DRAFT` advertisement may be edited -- once published
        (`ACTIVE`/`FULL`) or finalized (`CLOSED`/`CANCELLED`/`EXPIRED`),
        callers close/cancel and republish instead. A narrower rule than
        strictly required by the brief, chosen to avoid a per-field
        transition matrix (e.g. "price is editable while ACTIVE but
        `total_seats` is not") the brief never specifies.
        """
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            if advertisement.advertisement_status != AdvertisementStatus.DRAFT:
                return fail(
                    AdvertisementInvalidStatusTransitionError,
                    "Only a DRAFT advertisement can be edited.",
                )
            try:
                updated = await uow.advertisements.update(advertisement, **fields)
            except ValueError as exc:
                return fail(AdvertisementInvalidDataError, str(exc))
            return Result.ok(updated)

    async def activate_advertisement(self, advertisement_id: uuid.UUID) -> Result[Advertisement]:
        """Requires an approved vehicle, an active (approved, not banned)
        driver, and a valid (active) direction -- re-checked here, not
        just at `create_advertisement()` time, since any of the three can
        change after the advertisement was created. Allowed from `DRAFT`
        and `FULL` (see module docstring for why `FULL -> ACTIVE` here is
        not the "automatic" transition the brief forbids); refused from
        `CLOSED`/`CANCELLED`/`EXPIRED` (terminal) and from `ACTIVE`
        (already active).
        """
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)

            status = advertisement.advertisement_status
            if status == AdvertisementStatus.ACTIVE:
                return fail(AdvertisementAlreadyActiveError)
            if status == AdvertisementStatus.CLOSED:
                return fail(AdvertisementClosedError)
            if status == AdvertisementStatus.CANCELLED:
                return fail(AdvertisementCancelledError)
            if status == AdvertisementStatus.EXPIRED:
                return fail(AdvertisementExpiredError)
            if advertisement.available_seats <= 0:
                return fail(AdvertisementFullError, "No available seats to activate with.")

            violation = self._departure_time_violation(advertisement.departure_time)
            if violation is not None:
                return violation
            violation = await self._vehicle_ineligibility(
                advertisement.vehicle_id, advertisement.driver_profile_id, uow
            )
            if violation is not None:
                return violation
            violation = await self._driver_ineligibility(advertisement.driver_profile_id, uow)
            if violation is not None:
                return violation
            violation = await self._direction_ineligibility(advertisement.direction_id, uow)
            if violation is not None:
                return violation

            updated = await uow.advertisements.update(
                advertisement,
                advertisement_status=AdvertisementStatus.ACTIVE,
                published_at=advertisement.published_at or datetime.now(UTC),
            )
            return Result.ok(updated)

    async def deactivate_advertisement(self, advertisement_id: uuid.UUID) -> Result[Advertisement]:
        """`ACTIVE`/`FULL` -> `DRAFT`: pause the listing without cancelling
        it. A no-op success from `DRAFT` (idempotent, same convention as
        `VehicleService.deactivate_vehicle`); refused from the three
        terminal states.
        """
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)

            status = advertisement.advertisement_status
            if status == AdvertisementStatus.DRAFT:
                return Result.ok(advertisement)
            if status == AdvertisementStatus.CLOSED:
                return fail(AdvertisementClosedError)
            if status == AdvertisementStatus.CANCELLED:
                return fail(AdvertisementCancelledError)
            if status == AdvertisementStatus.EXPIRED:
                return fail(AdvertisementExpiredError)

            updated = await uow.advertisements.update(
                advertisement, advertisement_status=AdvertisementStatus.DRAFT
            )
            return Result.ok(updated)

    async def close_advertisement(self, advertisement_id: uuid.UUID) -> Result[Advertisement]:
        """`DRAFT`/`ACTIVE`/`FULL` -> `CLOSED`, a terminal, one-way state
        ("CLOSED advertisements cannot be reopened") -- distinct from
        `CANCELLED` (never happened / withdrawn) and `EXPIRED` (timed
        out): this is the driver deliberately ending the listing. Does
        not touch `started_at`/`completed_at` -- those mirror the future
        `Trip` aggregate's own lifecycle and are that domain's field to
        set, not this one's (see models/advertisement.py's docstring).
        """
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)

            status = advertisement.advertisement_status
            if status == AdvertisementStatus.CLOSED:
                return fail(AdvertisementClosedError)
            if status == AdvertisementStatus.CANCELLED:
                return fail(AdvertisementCancelledError)
            if status == AdvertisementStatus.EXPIRED:
                return fail(AdvertisementExpiredError)

            updated = await uow.advertisements.update(
                advertisement, advertisement_status=AdvertisementStatus.CLOSED
            )
            return Result.ok(updated)

    async def expire_advertisement(self, advertisement_id: uuid.UUID) -> Result[Advertisement]:
        """`DRAFT`/`ACTIVE`/`FULL` -> `EXPIRED`, once `expires_at` has
        actually passed -- the manual equivalent of what the not-yet-built
        expiry sweep worker would call per row from
        `get_expired_advertisements()`. A no-op success if already
        `EXPIRED`; refused for the other two terminal states.
        """
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)

            status = advertisement.advertisement_status
            if status == AdvertisementStatus.EXPIRED:
                return Result.ok(advertisement)
            if status == AdvertisementStatus.CLOSED:
                return fail(AdvertisementClosedError)
            if status == AdvertisementStatus.CANCELLED:
                return fail(AdvertisementCancelledError)
            if datetime.now(UTC) < _as_aware_utc(advertisement.expires_at):
                return fail(
                    AdvertisementInvalidDataError,
                    "This advertisement has not reached its expiry time yet.",
                )

            updated = await uow.advertisements.update(
                advertisement, advertisement_status=AdvertisementStatus.EXPIRED
            )
            return Result.ok(updated)

    async def delete_advertisement(self, advertisement_id: uuid.UUID) -> Result[None]:
        """`Advertisement` has no `SoftDeleteMixin` (see module docstring);
        "delete" maps onto `advertisement_status = CANCELLED` instead of a
        `deleted_at` column or a real `DELETE`. Idempotent if already
        `CANCELLED`; refused for the other two terminal states (a
        `CLOSED`/`EXPIRED` advertisement is already "gone" for a
        different reason and does not become `CANCELLED` after the fact).
        """
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)

            status = advertisement.advertisement_status
            if status == AdvertisementStatus.CANCELLED:
                return Result.ok(None)
            if status == AdvertisementStatus.CLOSED:
                return fail(AdvertisementClosedError)
            if status == AdvertisementStatus.EXPIRED:
                return fail(AdvertisementExpiredError)

            await uow.advertisements.update(
                advertisement, advertisement_status=AdvertisementStatus.CANCELLED
            )
            return Result.ok(None)

    async def restore_advertisement(self, advertisement_id: uuid.UUID) -> Result[Advertisement]:
        """The inverse of `delete_advertisement`: `CANCELLED -> DRAFT`.
        Idempotent no-op (returns the advertisement unchanged) if it is
        not currently `CANCELLED` -- there is nothing to restore, same
        convention as `VehicleService.restore_vehicle`. Refuses to restore
        into a departure time that has already passed.
        """
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            if advertisement.advertisement_status != AdvertisementStatus.CANCELLED:
                return Result.ok(advertisement)
            if _as_aware_utc(advertisement.departure_time) <= datetime.now(UTC):
                return fail(
                    AdvertisementInvalidDataError,
                    "Cannot restore: departure time has already passed.",
                )

            updated = await uow.advertisements.update(
                advertisement, advertisement_status=AdvertisementStatus.DRAFT
            )
            return Result.ok(updated)

    # --- Seat Management -----------------------------------------------
    # "Do NOT perform booking operations. Only manage seat counters." --
    # no method below knows what a Booking is; each is a self-contained
    # counter mutation guarded only by the seat-count invariants
    # (never negative, never over `total_seats`).

    async def has_available_seats(
        self, advertisement_id: uuid.UUID, *, count: int = 1
    ) -> Result[bool]:
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            return Result.ok(advertisement.available_seats >= count)

    async def is_full(self, advertisement_id: uuid.UUID) -> Result[bool]:
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            return Result.ok(advertisement.available_seats <= 0)

    async def reserve_seats(self, advertisement_id: uuid.UUID, count: int) -> Result[Advertisement]:
        """`available_seats -= count`, `reserved_seats += count` (a soft
        hold -- docs/03-DATABASE-DESIGN.md SS2.4's two-phase reservation).
        Only from `ACTIVE`: an unpublished (`DRAFT`) or finalized
        advertisement does not accept reservations even if its counters
        would otherwise allow it. Sets `FULL` automatically the moment
        `available_seats` reaches `0` -- the one *automatic* transition
        the brief's business rules describe.
        """
        if count <= 0:
            raise ValueError("count must be positive")
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            if advertisement.advertisement_status != AdvertisementStatus.ACTIVE:
                return fail(
                    AdvertisementInvalidStatusTransitionError,
                    "Seats can only be reserved on an ACTIVE advertisement.",
                )
            if count > advertisement.available_seats:
                return fail(
                    AdvertisementInsufficientSeatsError,
                    f"Only {advertisement.available_seats} seat(s) are available.",
                )

            new_available = advertisement.available_seats - count
            updates: dict[str, Any] = {
                "available_seats": new_available,
                "reserved_seats": advertisement.reserved_seats + count,
            }
            if new_available == 0:
                updates["advertisement_status"] = AdvertisementStatus.FULL
            updated = await uow.advertisements.update(advertisement, **updates)
            return Result.ok(updated)

    async def release_reserved_seats(
        self, advertisement_id: uuid.UUID, count: int
    ) -> Result[Advertisement]:
        """The inverse of `reserve_seats`: `reserved_seats -= count`,
        `available_seats += count`. Allowed regardless of status -- a
        pending hold must be releasable even if the advertisement became
        `CLOSED`/`EXPIRED` in the meantime, or seats would be stranded in
        `reserved_seats` forever. Does not automatically return `FULL` to
        `ACTIVE` (see module docstring / `activate_advertisement`).
        """
        if count <= 0:
            raise ValueError("count must be positive")
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            if count > advertisement.reserved_seats:
                return fail(
                    AdvertisementInsufficientSeatsError,
                    f"Only {advertisement.reserved_seats} seat(s) are currently reserved.",
                )

            updated = await uow.advertisements.update(
                advertisement,
                reserved_seats=advertisement.reserved_seats - count,
                available_seats=advertisement.available_seats + count,
            )
            return Result.ok(updated)

    async def consume_reserved_seats(
        self, advertisement_id: uuid.UUID, count: int
    ) -> Result[Advertisement]:
        """Permanently removes `count` seats from `reserved_seats` without
        returning them to `available_seats` -- the "driver accepts" half
        of docs/03-DATABASE-DESIGN.md SS2.4's two-phase reservation worked
        example ("driver accepts A -> available=2 reserved=0 -- 2 seats
        now permanently gone").

        Added in Step 8.5 for `BookingService.accept_booking()` (via
        `synchronize_available_seats()`): none of this module's original
        four seat-counter methods do this -- `release_reserved_seats`
        gives the seats back to `available`, and `decrease_available_seats`
        requires `ACTIVE` status, which a `FULL` advertisement (the very
        case an accepted reservation usually created) would fail. Allowed
        regardless of status, same reasoning as `release_reserved_seats`:
        a decision on a pending hold must always be actionable.
        """
        if count <= 0:
            raise ValueError("count must be positive")
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            if count > advertisement.reserved_seats:
                return fail(
                    AdvertisementInsufficientSeatsError,
                    f"Only {advertisement.reserved_seats} seat(s) are currently reserved.",
                )

            updated = await uow.advertisements.update(
                advertisement, reserved_seats=advertisement.reserved_seats - count
            )
            return Result.ok(updated)

    async def decrease_available_seats(
        self, advertisement_id: uuid.UUID, count: int
    ) -> Result[Advertisement]:
        """Direct `available_seats -= count`, `reserved_seats` untouched --
        for a permanent reduction that never was a soft hold (e.g. the
        driver manually offers one fewer seat). Same `ACTIVE`-only guard
        and automatic-`FULL` behavior as `reserve_seats`.
        """
        if count <= 0:
            raise ValueError("count must be positive")
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            if advertisement.advertisement_status != AdvertisementStatus.ACTIVE:
                return fail(
                    AdvertisementInvalidStatusTransitionError,
                    "Available seats can only be decreased on an ACTIVE advertisement.",
                )
            if count > advertisement.available_seats:
                return fail(
                    AdvertisementInsufficientSeatsError,
                    f"Only {advertisement.available_seats} seat(s) are available.",
                )

            new_available = advertisement.available_seats - count
            updates: dict[str, Any] = {"available_seats": new_available}
            if new_available == 0:
                updates["advertisement_status"] = AdvertisementStatus.FULL
            updated = await uow.advertisements.update(advertisement, **updates)
            return Result.ok(updated)

    async def increase_available_seats(
        self, advertisement_id: uuid.UUID, count: int
    ) -> Result[Advertisement]:
        """The inverse of `decrease_available_seats`. Allowed regardless
        of status, same reasoning as `release_reserved_seats`. Guarded so
        `available_seats + reserved_seats` never exceeds `total_seats`.
        """
        if count <= 0:
            raise ValueError("count must be positive")
        async with self._uow_factory() as uow:
            advertisement = await uow.advertisements.get_by_id(advertisement_id)
            if advertisement is None:
                return fail(AdvertisementNotFoundError)
            projected = advertisement.available_seats + advertisement.reserved_seats + count
            if projected > advertisement.total_seats:
                return fail(
                    AdvertisementSeatLimitExceededError,
                    f"Cannot exceed total_seats ({advertisement.total_seats}).",
                )

            updated = await uow.advertisements.update(
                advertisement, available_seats=advertisement.available_seats + count
            )
            return Result.ok(updated)

    # --- Queries -----------------------------------------------------------

    async def get_active_advertisements(self) -> Result[Sequence[Advertisement]]:
        async with self._uow_factory() as uow:
            advertisements = await uow.advertisements.list_all_active()
            return Result.ok(advertisements)

    async def get_driver_advertisements(
        self, driver_profile_id: uuid.UUID
    ) -> Result[Sequence[Advertisement]]:
        async with self._uow_factory() as uow:
            advertisements = await uow.advertisements.list_by_driver_profile_id(driver_profile_id)
            return Result.ok(advertisements)

    async def get_direction_advertisements(
        self, direction_id: uuid.UUID
    ) -> Result[Sequence[Advertisement]]:
        async with self._uow_factory() as uow:
            advertisements = await uow.advertisements.list_by_direction(direction_id)
            return Result.ok(advertisements)

    async def get_available_advertisements(
        self, direction_id: uuid.UUID
    ) -> Result[Sequence[Advertisement]]:
        """`ACTIVE` advertisements on this direction that still have at
        least one available seat -- filtered here, in the service, rather
        than via a new repository method: "available" is not a stored
        column/status, just a runtime property of `available_seats`.
        """
        async with self._uow_factory() as uow:
            advertisements = await uow.advertisements.list_active_by_direction(direction_id)
            available = [ad for ad in advertisements if ad.available_seats > 0]
            return Result.ok(available)

    async def get_expired_advertisements(self) -> Result[Sequence[Advertisement]]:
        """Candidates for the expiry sweep -- `ACTIVE`/`FULL` advertisements
        whose `expires_at` has already passed, not rows already sitting in
        `EXPIRED` status (see `AdvertisementRepository.list_expiring`).
        """
        async with self._uow_factory() as uow:
            advertisements = await uow.advertisements.list_expiring(before=datetime.now(UTC))
            return Result.ok(advertisements)


__all__ = ["AdvertisementService"]
