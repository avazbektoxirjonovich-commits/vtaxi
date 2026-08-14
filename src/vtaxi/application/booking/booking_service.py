"""`BookingService` -- a passenger's reservation request against an
Advertisement: management, the PENDING/RESERVED/ACCEPTED/COMPLETED (or
REJECTED/CANCELLED/EXPIRED) status machine, and seat synchronization with
the Advertisement domain.

Every method opens its own Unit of Work via the injected factory and is
therefore independently atomic, same discipline as every service so far.
Nothing here imports SQLAlchemy, Aiogram, or FastAPI -- only `ports.py`
(structural Protocols) and the ORM classes themselves for typing (see
`application/identity/ports.py`'s docstring for why that's not a
"framework independent" violation in this project).

**First cross-service dependency in this codebase.** Every prior service
(Identity, Geography, Vehicle, Advertisement) only ever depended on its
own Unit of Work. This step's own brief is explicit: "BookingService MUST
communicate with AdvertisementService." `BookingService` is therefore
constructor-injected with a live `AdvertisementService` instance (Step
8.4) in addition to its own `UnitOfWorkFactory`, and every seat-counter
mutation is delegated to it (`synchronize_reserved_seats`/
`synchronize_available_seats`/`rollback_reserved_seats` below) rather than
writing to `uow.advertisements` directly -- `uow.advertisements` on this
service's own Unit of Work is read-only (see ports.py).

**Known consistency trade-off, not hidden**: because the Booking-row
mutation (this service's own Unit of Work) and the Advertisement seat
mutation (`AdvertisementService`'s own, separate Unit of Work) are two
independent transactions, not one atomic unit spanning both tables, a
crash between the two calls can leave them momentarily inconsistent
(e.g. seats released but the booking still shows RESERVED). This is
mitigated by ordering -- the seat-synchronization call always happens
*first*; if it fails, the booking row is never touched, so the only
gap is "seats already moved, booking row update still pending," never
the reverse. Closing that gap for real (a saga/outbox, or a shared
transaction) is future hardening, not something to build here: the
booking-row update that follows a successful seat sync only ever writes
internally-computed, constraint-satisfying values, so in practice it does
not fail.

Seat counters are moved by four methods total, only three of which are
new in this step -- `synchronize_reserved_seats`/`synchronize_available_
seats`/`rollback_reserved_seats` -- thin wrappers around
`AdvertisementService.reserve_seats`/`consume_reserved_seats`/
`release_reserved_seats` respectively. `consume_reserved_seats` itself was
added to `AdvertisementService` in this same step (see that module's
docstring) -- a genuine capability gap discovered only once Booking's
accept-flow needed to permanently consume a held reservation, something
none of Step 8.4's original four seat methods could do without also
requiring `ACTIVE` status (which a `FULL` advertisement -- the very case
an accepted reservation usually created -- would fail).

Reservation timeout ("prepare architecture, no scheduler yet"):
`reserve_seat()` takes a `timeout` parameter (default 10 minutes) and
sets `reserved_until` accordingly; `expire_booking()` is the manual
transition a future sweep worker would call once `reserved_until` has
passed, and `get_expired_bookings()` is that worker's future candidate
query -- no background job is implemented here, mirroring
`AdvertisementService.expire_advertisement()`'s identical shape.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from vtaxi.application.advertisement import AdvertisementService
from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.core.domain.result import Failure
from vtaxi.domain.booking.exceptions import (
    BookingAdvertisementNotBookableError,
    BookingAlreadyExistsError,
    BookingInsufficientSeatsError,
    BookingInvalidDataError,
    BookingInvalidStatusTransitionError,
    BookingNotFoundError,
    BookingPassengerNotEligibleError,
    BookingSelfBookingError,
)
from vtaxi.infrastructure.database.enums import AdvertisementStatus, BookingStatus, PassengerStatus
from vtaxi.infrastructure.database.models.advertisement import Advertisement
from vtaxi.infrastructure.database.models.booking import Booking

from .ports import BookingUnitOfWork

# The DB's own `requested_seats <= 10` CHECK constraint (models/booking.py),
# mirrored here so a bad request fails with a `Result`, not a raw
# `IntegrityError`.
_MAX_REQUESTED_SEATS = 10

# "Prepare support for: 5 minutes, 10 minutes, configurable timeout" --
# 10 minutes is the default; any caller of `reserve_seat()` may pass a
# different `timedelta` (e.g. `timedelta(minutes=5)`) instead.
_DEFAULT_RESERVATION_TIMEOUT = timedelta(minutes=10)


def _as_aware_utc(value: datetime) -> datetime:
    """Same SQLite-vs-PostgreSQL `tzinfo` round-trip fix as
    `application/advertisement/advertisement_service.py`'s helper of the
    same name -- duplicated locally rather than imported, since it is a
    private module-level helper, not part of that module's public API.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class BookingService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory[BookingUnitOfWork],
        advertisement_service: AdvertisementService,
    ) -> None:
        self._uow_factory = uow_factory
        self._advertisement_service = advertisement_service

    # --- Booking Validation (private helpers) -------------------------
    # Each returns `Failure | None` (or, for a fetch, `Advertisement |
    # Failure`) and is shared by the public `validate_*` wrappers below
    # *and* by `create_booking()` -- same pattern as
    # `AdvertisementService._vehicle_ineligibility`, avoiding the
    # `Result[None]`-vs-`Result[Booking]` covariance mismatch mypy would
    # otherwise flag.

    async def _passenger_ineligibility(
        self, passenger_profile_id: uuid.UUID, uow: BookingUnitOfWork
    ) -> Failure | None:
        passenger = await uow.passengers.get_by_id(passenger_profile_id)
        if passenger is None:
            return fail(BookingPassengerNotEligibleError, "The given passenger does not exist.")
        if passenger.deleted_at is not None:
            return fail(
                BookingPassengerNotEligibleError, "This passenger's profile has been deleted."
            )
        if passenger.passenger_status == PassengerStatus.BANNED:
            return fail(BookingPassengerNotEligibleError, "This passenger has been banned.")
        return None

    async def _fetch_advertisement(
        self, advertisement_id: uuid.UUID, uow: BookingUnitOfWork
    ) -> Advertisement | Failure:
        advertisement = await uow.advertisements.get_by_id(advertisement_id)
        if advertisement is None:
            return fail(
                BookingAdvertisementNotBookableError, "The given advertisement does not exist."
            )
        return advertisement

    def _advertisement_bookability(self, advertisement: Advertisement) -> Failure | None:
        if advertisement.advertisement_status != AdvertisementStatus.ACTIVE:
            return fail(
                BookingAdvertisementNotBookableError,
                f"This advertisement is {advertisement.advertisement_status.value} "
                "and is not accepting bookings.",
            )
        return None

    def _seat_request_violation(
        self, advertisement: Advertisement, requested_seats: int
    ) -> Failure | None:
        if requested_seats <= 0:
            raise ValueError("requested_seats must be positive")
        if requested_seats > _MAX_REQUESTED_SEATS:
            return fail(
                BookingInvalidDataError,
                f"Cannot request more than {_MAX_REQUESTED_SEATS} seats.",
            )
        if requested_seats > advertisement.available_seats:
            return fail(
                BookingInsufficientSeatsError,
                f"Only {advertisement.available_seats} seat(s) are available "
                "on this advertisement.",
            )
        return None

    async def _self_booking_violation(
        self, advertisement: Advertisement, passenger_profile_id: uuid.UUID, uow: BookingUnitOfWork
    ) -> Failure | None:
        passenger = await uow.passengers.get_by_id(passenger_profile_id)
        driver = await uow.drivers.get_by_id(advertisement.driver_profile_id)
        if passenger is not None and driver is not None and passenger.user_id == driver.user_id:
            return fail(BookingSelfBookingError)
        return None

    async def _duplicate_booking_violation(
        self, passenger_profile_id: uuid.UUID, advertisement_id: uuid.UUID, uow: BookingUnitOfWork
    ) -> Failure | None:
        existing = await uow.bookings.find_active_by_passenger_and_advertisement(
            passenger_profile_id, advertisement_id
        )
        if existing is not None:
            return fail(BookingAlreadyExistsError)
        return None

    # --- Booking Validation (public) -----------------------------------

    async def validate_passenger(self, passenger_profile_id: uuid.UUID) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._passenger_ineligibility(passenger_profile_id, uow)
            return violation if violation is not None else Result.ok(None)

    async def validate_advertisement(self, advertisement_id: uuid.UUID) -> Result[None]:
        async with self._uow_factory() as uow:
            result = await self._fetch_advertisement(advertisement_id, uow)
            if isinstance(result, Failure):
                return result
            violation = self._advertisement_bookability(result)
            return violation if violation is not None else Result.ok(None)

    async def validate_seat_request(
        self, advertisement_id: uuid.UUID, requested_seats: int
    ) -> Result[None]:
        async with self._uow_factory() as uow:
            result = await self._fetch_advertisement(advertisement_id, uow)
            if isinstance(result, Failure):
                return result
            violation = self._seat_request_violation(result, requested_seats)
            return violation if violation is not None else Result.ok(None)

    async def validate_booking(
        self,
        passenger_profile_id: uuid.UUID,
        advertisement_id: uuid.UUID,
        requested_seats: int,
    ) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._passenger_ineligibility(passenger_profile_id, uow)
            if violation is not None:
                return violation

            result = await self._fetch_advertisement(advertisement_id, uow)
            if isinstance(result, Failure):
                return result
            advertisement = result

            violation = self._advertisement_bookability(advertisement)
            if violation is not None:
                return violation
            violation = self._seat_request_violation(advertisement, requested_seats)
            if violation is not None:
                return violation
            violation = await self._self_booking_violation(advertisement, passenger_profile_id, uow)
            if violation is not None:
                return violation
            violation = await self._duplicate_booking_violation(
                passenger_profile_id, advertisement_id, uow
            )
            if violation is not None:
                return violation
            return Result.ok(None)

    # --- Booking Management ---------------------------------------------

    async def create_booking(
        self,
        *,
        passenger_profile_id: uuid.UUID,
        advertisement_id: uuid.UUID,
        requested_seats: int,
        passenger_comment: str | None = None,
    ) -> Result[Booking]:
        """Inserts a `PENDING` booking -- no seat is held yet (see module
        docstring on `Booking`'s two-phase model): `reserve_seat()` is the
        explicit next step that actually synchronizes with
        `AdvertisementService`.
        """
        async with self._uow_factory() as uow:
            violation = await self._passenger_ineligibility(passenger_profile_id, uow)
            if violation is not None:
                return violation

            result = await self._fetch_advertisement(advertisement_id, uow)
            if isinstance(result, Failure):
                return result
            advertisement = result

            violation = self._advertisement_bookability(advertisement)
            if violation is not None:
                return violation
            violation = self._seat_request_violation(advertisement, requested_seats)
            if violation is not None:
                return violation
            violation = await self._self_booking_violation(advertisement, passenger_profile_id, uow)
            if violation is not None:
                return violation
            violation = await self._duplicate_booking_violation(
                passenger_profile_id, advertisement_id, uow
            )
            if violation is not None:
                return violation

            try:
                booking = await uow.bookings.create(
                    passenger_profile_id=passenger_profile_id,
                    advertisement_id=advertisement_id,
                    requested_seats=requested_seats,
                    passenger_comment=passenger_comment,
                )
            except ValueError as exc:
                return fail(BookingInvalidDataError, str(exc))
            return Result.ok(booking)

    async def get_booking(self, booking_id: uuid.UUID) -> Result[Booking]:
        async with self._uow_factory() as uow:
            booking = await uow.bookings.get_by_id(booking_id)
            if booking is None:
                return fail(BookingNotFoundError)
            return Result.ok(booking)

    async def booking_exists(self, booking_id: uuid.UUID) -> Result[bool]:
        async with self._uow_factory() as uow:
            return Result.ok(await uow.bookings.get_by_id(booking_id) is not None)

    async def cancel_booking(self, booking_id: uuid.UUID) -> Result[Booking]:
        """`PENDING`/`RESERVED` -> `CANCELLED`, passenger-initiated. Rolls
        back the held seats first if the booking was `RESERVED` --
        "Cancelled bookings MUST rollback seat counters." Idempotent if
        already `CANCELLED`; refused from `ACCEPTED`/`REJECTED`/`EXPIRED`/
        `COMPLETED` (this service does not implement post-acceptance
        cancellation, which belongs to the future Trip domain).
        """
        async with self._uow_factory() as uow:
            booking = await uow.bookings.get_by_id(booking_id)
            if booking is None:
                return fail(BookingNotFoundError)

            status = booking.booking_status
            if status == BookingStatus.CANCELLED:
                return Result.ok(booking)
            if status not in (BookingStatus.PENDING, BookingStatus.RESERVED):
                return fail(
                    BookingInvalidStatusTransitionError,
                    f"A {status.value} booking cannot be cancelled.",
                )

            if status == BookingStatus.RESERVED:
                rollback = await self.rollback_reserved_seats(
                    booking.advertisement_id, booking.requested_seats
                )
                if isinstance(rollback, Failure):
                    return rollback

            updated = await uow.bookings.update(
                booking, booking_status=BookingStatus.CANCELLED, cancelled_at=datetime.now(UTC)
            )
            return Result.ok(updated)

    async def expire_booking(self, booking_id: uuid.UUID) -> Result[Booking]:
        """`RESERVED` -> `EXPIRED`, once `reserved_until` has actually
        passed -- the manual equivalent of what the not-yet-built
        reservation-timeout sweep worker would call per row from
        `get_expired_bookings()`. Rolls back the held seats first.
        Idempotent if already `EXPIRED`.
        """
        async with self._uow_factory() as uow:
            booking = await uow.bookings.get_by_id(booking_id)
            if booking is None:
                return fail(BookingNotFoundError)

            status = booking.booking_status
            if status == BookingStatus.EXPIRED:
                return Result.ok(booking)
            if status != BookingStatus.RESERVED:
                return fail(
                    BookingInvalidStatusTransitionError,
                    f"A {status.value} booking cannot expire.",
                )
            if booking.reserved_until is None or datetime.now(UTC) < _as_aware_utc(
                booking.reserved_until
            ):
                return fail(
                    BookingInvalidDataError,
                    "This booking's reservation window has not passed yet.",
                )

            rollback = await self.rollback_reserved_seats(
                booking.advertisement_id, booking.requested_seats
            )
            if isinstance(rollback, Failure):
                return rollback

            updated = await uow.bookings.update(booking, booking_status=BookingStatus.EXPIRED)
            return Result.ok(updated)

    async def reject_booking(
        self, booking_id: uuid.UUID, *, driver_comment: str | None = None
    ) -> Result[Booking]:
        """`PENDING`/`RESERVED` -> `REJECTED`, driver-initiated. Rolls back
        the held seats first if the booking was `RESERVED`. Idempotent if
        already `REJECTED`.
        """
        async with self._uow_factory() as uow:
            booking = await uow.bookings.get_by_id(booking_id)
            if booking is None:
                return fail(BookingNotFoundError)

            status = booking.booking_status
            if status == BookingStatus.REJECTED:
                return Result.ok(booking)
            if status not in (BookingStatus.PENDING, BookingStatus.RESERVED):
                return fail(
                    BookingInvalidStatusTransitionError,
                    f"A {status.value} booking cannot be rejected.",
                )

            if status == BookingStatus.RESERVED:
                rollback = await self.rollback_reserved_seats(
                    booking.advertisement_id, booking.requested_seats
                )
                if isinstance(rollback, Failure):
                    return rollback

            updated = await uow.bookings.update(
                booking,
                booking_status=BookingStatus.REJECTED,
                rejected_at=datetime.now(UTC),
                driver_comment=driver_comment,
            )
            return Result.ok(updated)

    async def accept_booking(self, booking_id: uuid.UUID) -> Result[Booking]:
        """`RESERVED` -> `ACCEPTED`: permanently consumes the held seats
        via `synchronize_available_seats()` -- "Accepted bookings decrease
        advertisement available seats" (the decrease already happened
        when the seat was reserved; acceptance is what makes it
        permanent, per docs/03-DATABASE-DESIGN.md SS2.4's worked example
        -- see `AdvertisementService.consume_reserved_seats`). Idempotent
        if already `ACCEPTED`; a booking must be `RESERVED` first --
        this service does not allow `PENDING -> ACCEPTED` directly.
        """
        async with self._uow_factory() as uow:
            booking = await uow.bookings.get_by_id(booking_id)
            if booking is None:
                return fail(BookingNotFoundError)

            status = booking.booking_status
            if status == BookingStatus.ACCEPTED:
                return Result.ok(booking)
            if status != BookingStatus.RESERVED:
                return fail(
                    BookingInvalidStatusTransitionError,
                    "Only a RESERVED booking can be accepted.",
                )

            sync = await self.synchronize_available_seats(
                booking.advertisement_id, booking.requested_seats
            )
            if isinstance(sync, Failure):
                return sync

            updated = await uow.bookings.update(
                booking, booking_status=BookingStatus.ACCEPTED, accepted_at=datetime.now(UTC)
            )
            return Result.ok(updated)

    # --- Passenger Actions -----------------------------------------------

    async def reserve_seat(
        self,
        booking_id: uuid.UUID,
        *,
        reservation_timeout: timedelta = _DEFAULT_RESERVATION_TIMEOUT,
    ) -> Result[Booking]:
        """`PENDING` -> `RESERVED`: the passenger's requested seats move
        from `available` to `reserved` on the Advertisement via
        `synchronize_reserved_seats()`, and `reserved_until` is set to
        `now + reservation_timeout` (default 10 minutes -- see module
        docstring on "prepare architecture" for reservation timeouts).
        Parameter named `reservation_timeout`, not `timeout`: ruff's
        ASYNC109 flags a bare `timeout` parameter on an async function as
        easily confused with `asyncio.timeout()`'s cancellation scope,
        which this is not.
        """
        async with self._uow_factory() as uow:
            booking = await uow.bookings.get_by_id(booking_id)
            if booking is None:
                return fail(BookingNotFoundError)
            if booking.booking_status != BookingStatus.PENDING:
                return fail(
                    BookingInvalidStatusTransitionError,
                    "Only a PENDING booking can reserve a seat.",
                )

            sync = await self.synchronize_reserved_seats(
                booking.advertisement_id, booking.requested_seats
            )
            if isinstance(sync, Failure):
                return sync

            updated = await uow.bookings.update(
                booking,
                booking_status=BookingStatus.RESERVED,
                reserved_until=datetime.now(UTC) + reservation_timeout,
            )
            return Result.ok(updated)

    async def release_reserved_seat(self, booking_id: uuid.UUID) -> Result[Booking]:
        """The Passenger-Actions-vocabulary name for giving up a held
        reservation specifically: delegates to `cancel_booking()` (which
        also accepts `PENDING`), restricted here to `RESERVED` only, so a
        passenger-facing caller can express "release the seat I reserved"
        without needing to know `cancel_booking()` covers a broader set
        of starting states.
        """
        async with self._uow_factory() as uow:
            booking = await uow.bookings.get_by_id(booking_id)
            if booking is None:
                return fail(BookingNotFoundError)
            if booking.booking_status != BookingStatus.RESERVED:
                return fail(
                    BookingInvalidStatusTransitionError,
                    "Only a RESERVED booking has a held seat to release.",
                )
        return await self.cancel_booking(booking_id)

    async def request_booking(
        self,
        *,
        passenger_profile_id: uuid.UUID,
        advertisement_id: uuid.UUID,
        requested_seats: int,
        passenger_comment: str | None = None,
    ) -> Result[Booking]:
        """The Passenger-Actions-vocabulary name for `create_booking()` --
        same operation, same signature; kept as a separate method purely
        because the brief names both explicitly.
        """
        return await self.create_booking(
            passenger_profile_id=passenger_profile_id,
            advertisement_id=advertisement_id,
            requested_seats=requested_seats,
            passenger_comment=passenger_comment,
        )

    # --- Driver Actions ------------------------------------------------

    async def approve_booking(self, booking_id: uuid.UUID) -> Result[Booking]:
        """The Driver-Actions-vocabulary name for `accept_booking()`."""
        return await self.accept_booking(booking_id)

    async def decline_booking(
        self, booking_id: uuid.UUID, *, driver_comment: str | None = None
    ) -> Result[Booking]:
        """The Driver-Actions-vocabulary name for `reject_booking()`."""
        return await self.reject_booking(booking_id, driver_comment=driver_comment)

    # --- Seat Synchronization --------------------------------------------
    # Every method below is a thin wrapper around one `AdvertisementService`
    # (Step 8.4) seat-counter method -- `BookingService` never writes to
    # `uow.advertisements` itself (see module docstring). A lower-level
    # failure is propagated via `isinstance(result, Failure)`, not
    # `result.is_failure`: `result` here is typed `Result[Advertisement]`,
    # and mypy cannot narrow a `Result[Advertisement]` to `Failure` from a
    # property check, only from an `isinstance` check against the
    # concrete class -- `Failure` extends `Result[Any]`, so the narrowed
    # value type-checks as a return value for any `Result[T]`, including
    # this method's own `Result[None]`.

    async def synchronize_reserved_seats(
        self, advertisement_id: uuid.UUID, count: int
    ) -> Result[None]:
        """HOLD phase: moves `count` seats from `available` to `reserved`
        on the Advertisement -- delegates to `AdvertisementService.
        reserve_seats()`.
        """
        result = await self._advertisement_service.reserve_seats(advertisement_id, count)
        if isinstance(result, Failure):
            return result
        return Result.ok(None)

    async def synchronize_available_seats(
        self, advertisement_id: uuid.UUID, count: int
    ) -> Result[None]:
        """COMMIT phase: permanently consumes `count` reserved seats --
        delegates to `AdvertisementService.consume_reserved_seats()`.
        """
        result = await self._advertisement_service.consume_reserved_seats(advertisement_id, count)
        if isinstance(result, Failure):
            return result
        return Result.ok(None)

    async def rollback_reserved_seats(
        self, advertisement_id: uuid.UUID, count: int
    ) -> Result[None]:
        """UNDO phase: moves `count` seats back from `reserved` to
        `available` -- delegates to `AdvertisementService.
        release_reserved_seats()`.
        """
        result = await self._advertisement_service.release_reserved_seats(advertisement_id, count)
        if isinstance(result, Failure):
            return result
        return Result.ok(None)

    # --- Queries -----------------------------------------------------------

    async def get_passenger_bookings(
        self, passenger_profile_id: uuid.UUID
    ) -> Result[Sequence[Booking]]:
        async with self._uow_factory() as uow:
            bookings = await uow.bookings.list_by_passenger_profile_id(passenger_profile_id)
            return Result.ok(bookings)

    async def get_driver_bookings(self, driver_profile_id: uuid.UUID) -> Result[Sequence[Booking]]:
        async with self._uow_factory() as uow:
            bookings = await uow.bookings.list_by_driver_profile_id(driver_profile_id)
            return Result.ok(bookings)

    async def get_active_bookings(self) -> Result[Sequence[Booking]]:
        async with self._uow_factory() as uow:
            bookings = await uow.bookings.list_active()
            return Result.ok(bookings)

    async def get_reserved_bookings(self) -> Result[Sequence[Booking]]:
        async with self._uow_factory() as uow:
            bookings = await uow.bookings.list_reserved()
            return Result.ok(bookings)

    async def get_expired_bookings(self) -> Result[Sequence[Booking]]:
        async with self._uow_factory() as uow:
            bookings = await uow.bookings.list_expiring(before=datetime.now(UTC))
            return Result.ok(bookings)


__all__ = ["BookingService"]
