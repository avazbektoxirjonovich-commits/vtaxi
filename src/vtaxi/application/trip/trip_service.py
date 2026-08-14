"""`TripService` -- the realized journey created from an Advertisement:
management, passenger participation (`TripPassenger`), and the
SCHEDULED/READY/STARTED/IN_PROGRESS/COMPLETED (or CANCELLED) status
machine.

Every method opens its own Unit of Work via the injected factory and is
therefore independently atomic, same discipline as every service so far.
Nothing here imports SQLAlchemy, Aiogram, or FastAPI -- only `ports.py`
(structural Protocols) and the ORM classes themselves for typing (see
`application/identity/ports.py`'s docstring for why that's not a
"framework independent" violation in this project).

Status machine, as implemented here (the brief's "Trip Flow" diagram maps
onto `TripStatus`'s six values -- "CREATED" is `SCHEDULED`, the model's own
default):

    SCHEDULED --add_passenger()--> READY --start_trip()--> STARTED
       ^                              |                       |
       +------remove_passenger()------+                       |
       (only while no passengers remain)               board_passenger()
                                                      (first boarding only)
                                                                |
                                                                v
                                                          IN_PROGRESS
                                                                |
                                                          finish_trip()
                                                                v
                                                          COMPLETED (terminal)

    cancel_trip() -> CANCELLED (terminal) from any non-terminal state.

`READY`/`IN_PROGRESS` are both reached by an *automatic*, forward-only
side effect (first passenger added; first passenger boarded,
respectively) -- unlike `AdvertisementService`'s `FULL` status (Step 8.4),
nothing in this step's brief forbids this, and giving these two enum
values real meaning (rather than leaving them unreachable) is more
useful than not. `remove_passenger()` reverting `READY -> SCHEDULED` once
the passenger count returns to zero is the one auto-*backward* transition
in this service -- also not forbidden, and it keeps `trip_status` an
honest reflection of "does this trip currently have anyone attached,"
which `start_trip()` still re-verifies independently (a fresh
`list_trip_passengers` count, not merely trusting `trip_status == READY`)
precisely so that bookkeeping subtlety can never let a passenger-less
trip start.

**Two write-backs deliberately left out of this step's scope, despite
being clearly anticipated by name in two previously-approved models'
docstrings:**

1. `Advertisement.started_at`/`completed_at` mirror "the (future) Trip's
   own lifecycle timestamps" per `models/advertisement.py`'s own
   docstring ("nothing in this model sets them; that's the future
   Service Layer's job"). This step's Responsibilities/Business-Rules
   lists never mention Advertisement at all, so wiring that mirror here
   would be scope creep onto an already-approved domain, not something
   "absolutely necessary" this step's own text asks for.
2. `Booking.booking_status -> COMPLETED` once a passenger is dropped off:
   Step 8.5's Booking Flow diagram shows `ACCEPTED -> COMPLETED` as a
   valid path, and that step's own `BookingService` docstring says
   post-acceptance transitions "belong to the future Trip domain." This
   is a stronger case than (1), but still not named anywhere in *this*
   step's own Responsibilities/Business-Rules/Validation lists -- so it is
   flagged here, not built, and left for explicit approval in a future
   step rather than assumed.

Both are read-only on this service's own Unit of Work today (see
ports.py) -- closing either gap would mean either widening
`TripUnitOfWork` to read-write on that repository, or (matching Step
8.5's own precedent) injecting the owning service instead. Neither is
done here without being asked.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.core.domain.result import Failure
from vtaxi.domain.trip.exceptions import (
    TripAdvertisementNotEligibleError,
    TripAlreadyExistsError,
    TripAlreadyStartedError,
    TripBoardingInvalidTransitionError,
    TripBookingNotEligibleError,
    TripCancelledError,
    TripCompletedError,
    TripDriverNotEligibleError,
    TripInvalidStatusTransitionError,
    TripNoPassengersError,
    TripNotFoundError,
    TripPassengerNotEligibleError,
    TripPassengerNotFoundError,
    TripVehicleNotEligibleError,
)
from vtaxi.infrastructure.database.enums import (
    BoardingStatus,
    BookingStatus,
    DriverApprovalStatus,
    DriverAvailabilityStatus,
    PassengerStatus,
    TripStatus,
    VerificationStatus,
)
from vtaxi.infrastructure.database.models.advertisement import Advertisement
from vtaxi.infrastructure.database.models.booking import Booking
from vtaxi.infrastructure.database.models.trip import Trip, TripPassenger

from .ports import TripUnitOfWork

_STARTED_STATUSES = (TripStatus.STARTED, TripStatus.IN_PROGRESS)


class TripService:
    def __init__(self, uow_factory: UnitOfWorkFactory[TripUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # --- Validation (private helpers) -------------------------------------
    # Each returns `Failure | None`, or (for a fetch) the fetched row or a
    # `Failure`, and is shared by the public `validate_*` wrappers below
    # *and* by the Trip/Passenger Management methods -- same pattern as
    # `AdvertisementService._vehicle_ineligibility`, avoiding the
    # `Result[None]`-vs-`Result[Trip]` covariance mismatch mypy would
    # otherwise flag.

    async def _fetch_trip(self, trip_id: uuid.UUID, uow: TripUnitOfWork) -> Trip | Failure:
        trip = await uow.trips.get_by_id(trip_id)
        if trip is None:
            return fail(TripNotFoundError)
        return trip

    async def _fetch_advertisement(
        self, advertisement_id: uuid.UUID, uow: TripUnitOfWork
    ) -> Advertisement | Failure:
        advertisement = await uow.advertisements.get_by_id(advertisement_id)
        if advertisement is None:
            return fail(TripAdvertisementNotEligibleError)
        return advertisement

    async def _driver_ineligibility(
        self, driver_profile_id: uuid.UUID, advertisement: Advertisement, uow: TripUnitOfWork
    ) -> Failure | None:
        driver = await uow.drivers.get_by_id(driver_profile_id)
        if driver is None:
            return fail(TripDriverNotEligibleError, "The given driver does not exist.")
        if driver.deleted_at is not None:
            return fail(TripDriverNotEligibleError, "This driver's profile has been deleted.")
        if driver.availability_status == DriverAvailabilityStatus.BANNED:
            return fail(TripDriverNotEligibleError, "This driver is banned.")
        if driver.approval_status != DriverApprovalStatus.APPROVED:
            return fail(TripDriverNotEligibleError, "This driver has not been approved yet.")
        if advertisement.driver_profile_id != driver_profile_id:
            return fail(
                TripDriverNotEligibleError, "This driver does not own the given advertisement."
            )
        return None

    async def _vehicle_ineligibility(
        self, vehicle_id: uuid.UUID, uow: TripUnitOfWork
    ) -> Failure | None:
        vehicle = await uow.vehicles.get_by_id(vehicle_id)
        if vehicle is None:
            return fail(TripVehicleNotEligibleError, "The given vehicle does not exist.")
        if vehicle.deleted_at is not None:
            return fail(TripVehicleNotEligibleError, "This vehicle has been deleted.")
        if vehicle.verification_status != VerificationStatus.APPROVED:
            return fail(TripVehicleNotEligibleError, "This vehicle has not been approved yet.")
        return None

    async def _fetch_eligible_booking(
        self, booking_id: uuid.UUID, advertisement_id: uuid.UUID, uow: TripUnitOfWork
    ) -> Booking | Failure:
        booking = await uow.bookings.get_by_id(booking_id)
        if booking is None:
            return fail(TripBookingNotEligibleError, "The given booking does not exist.")
        if booking.advertisement_id != advertisement_id:
            return fail(
                TripBookingNotEligibleError,
                "This booking does not belong to the trip's advertisement.",
            )
        if booking.booking_status != BookingStatus.ACCEPTED:
            return fail(
                TripBookingNotEligibleError,
                f"Only ACCEPTED bookings can join a trip (this one is "
                f"{booking.booking_status.value}).",
            )
        return booking

    async def _passenger_ineligibility(
        self, passenger_profile_id: uuid.UUID, uow: TripUnitOfWork
    ) -> Failure | None:
        passenger = await uow.passengers.get_by_id(passenger_profile_id)
        if passenger is None:
            return fail(TripPassengerNotEligibleError, "The given passenger does not exist.")
        if passenger.deleted_at is not None:
            return fail(TripPassengerNotEligibleError, "This passenger's profile has been deleted.")
        if passenger.passenger_status == PassengerStatus.BANNED:
            return fail(TripPassengerNotEligibleError, "This passenger has been banned.")
        return None

    def _trip_modifiable_violation(self, trip: Trip) -> Failure | None:
        """`None` if the trip is not in a terminal state, a `Failure`
        otherwise -- "Completed trip cannot be modified" applies to every
        Passenger Management method below, plus `cancel_trip()`.
        """
        if trip.trip_status == TripStatus.COMPLETED:
            return fail(TripCompletedError)
        if trip.trip_status == TripStatus.CANCELLED:
            return fail(TripCancelledError)
        return None

    # --- Validation (public) ---------------------------------------------

    async def validate_trip(self, trip_id: uuid.UUID) -> Result[None]:
        async with self._uow_factory() as uow:
            result = await self._fetch_trip(trip_id, uow)
            return result if isinstance(result, Failure) else Result.ok(None)

    async def validate_driver(
        self, driver_profile_id: uuid.UUID, advertisement_id: uuid.UUID
    ) -> Result[None]:
        async with self._uow_factory() as uow:
            ad_result = await self._fetch_advertisement(advertisement_id, uow)
            if isinstance(ad_result, Failure):
                return ad_result
            violation = await self._driver_ineligibility(driver_profile_id, ad_result, uow)
            return violation if violation is not None else Result.ok(None)

    async def validate_vehicle(self, vehicle_id: uuid.UUID) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._vehicle_ineligibility(vehicle_id, uow)
            return violation if violation is not None else Result.ok(None)

    async def validate_booking(
        self, booking_id: uuid.UUID, advertisement_id: uuid.UUID
    ) -> Result[None]:
        async with self._uow_factory() as uow:
            result = await self._fetch_eligible_booking(booking_id, advertisement_id, uow)
            return result if isinstance(result, Failure) else Result.ok(None)

    async def validate_passenger(self, passenger_profile_id: uuid.UUID) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._passenger_ineligibility(passenger_profile_id, uow)
            return violation if violation is not None else Result.ok(None)

    # --- Trip Management ---------------------------------------------------

    async def create_trip(
        self, *, advertisement_id: uuid.UUID, driver_profile_id: uuid.UUID
    ) -> Result[Trip]:
        """`vehicle_id` is derived from the Advertisement (denormalized
        onto `Trip`, same as the Advertisement's own denormalization from
        `Vehicle`) -- never a separate caller-supplied parameter, so it
        can never disagree with the Advertisement it was created from.
        "Driver must own Advertisement" is enforced by
        `_driver_ineligibility`, not by omitting the parameter: the
        caller's claimed `driver_profile_id` is checked against
        `advertisement.driver_profile_id` explicitly, so the rule is
        actually falsifiable rather than true by construction.
        """
        async with self._uow_factory() as uow:
            ad_result = await self._fetch_advertisement(advertisement_id, uow)
            if isinstance(ad_result, Failure):
                return ad_result
            advertisement = ad_result

            violation = await self._driver_ineligibility(driver_profile_id, advertisement, uow)
            if violation is not None:
                return violation

            if await uow.trips.get_by_advertisement_id(advertisement_id) is not None:
                return fail(TripAlreadyExistsError)

            violation = await self._vehicle_ineligibility(advertisement.vehicle_id, uow)
            if violation is not None:
                return violation

            trip = await uow.trips.create(
                advertisement_id=advertisement_id,
                driver_profile_id=driver_profile_id,
                vehicle_id=advertisement.vehicle_id,
            )
            return Result.ok(trip)

    async def get_trip(self, trip_id: uuid.UUID) -> Result[Trip]:
        async with self._uow_factory() as uow:
            result = await self._fetch_trip(trip_id, uow)
            return result if isinstance(result, Failure) else Result.ok(result)

    async def trip_exists(self, trip_id: uuid.UUID) -> Result[bool]:
        async with self._uow_factory() as uow:
            return Result.ok(await uow.trips.get_by_id(trip_id) is not None)

    async def start_trip(self, trip_id: uuid.UUID) -> Result[Trip]:
        """`SCHEDULED`/`READY` -> `STARTED`. Re-verifies "at least one
        passenger" via a fresh `list_trip_passengers` count rather than
        trusting `trip_status == READY` alone (see module docstring).
        Refused if already started, cancelled, or completed.
        """
        async with self._uow_factory() as uow:
            result = await self._fetch_trip(trip_id, uow)
            if isinstance(result, Failure):
                return result
            trip = result

            status = trip.trip_status
            if status in _STARTED_STATUSES:
                return fail(TripAlreadyStartedError)
            if status == TripStatus.CANCELLED:
                return fail(TripCancelledError)
            if status == TripStatus.COMPLETED:
                return fail(TripCompletedError)

            passengers = await uow.trips.list_trip_passengers(trip_id)
            if not passengers:
                return fail(TripNoPassengersError)

            updated = await uow.trips.update(
                trip, trip_status=TripStatus.STARTED, started_at=datetime.now(UTC)
            )
            return Result.ok(updated)

    async def finish_trip(self, trip_id: uuid.UUID) -> Result[Trip]:
        """`STARTED`/`IN_PROGRESS` -> `COMPLETED`. Idempotent if already
        `COMPLETED`; refused if cancelled or not yet started.
        """
        async with self._uow_factory() as uow:
            result = await self._fetch_trip(trip_id, uow)
            if isinstance(result, Failure):
                return result
            trip = result

            status = trip.trip_status
            if status == TripStatus.COMPLETED:
                return Result.ok(trip)
            if status == TripStatus.CANCELLED:
                return fail(TripCancelledError)
            if status not in _STARTED_STATUSES:
                return fail(
                    TripInvalidStatusTransitionError,
                    f"A {status.value} trip must be started before it can finish.",
                )

            updated = await uow.trips.update(
                trip, trip_status=TripStatus.COMPLETED, ended_at=datetime.now(UTC)
            )
            return Result.ok(updated)

    async def cancel_trip(self, trip_id: uuid.UUID) -> Result[Trip]:
        """Any non-terminal status -> `CANCELLED`. Idempotent if already
        `CANCELLED`; refused if already `COMPLETED` ("completed trip
        cannot be modified"). "Cancelled trip cannot be started" follows
        from `start_trip()`'s own `CANCELLED` guard, not from anything
        enforced here.
        """
        async with self._uow_factory() as uow:
            result = await self._fetch_trip(trip_id, uow)
            if isinstance(result, Failure):
                return result
            trip = result

            if trip.trip_status == TripStatus.CANCELLED:
                return Result.ok(trip)
            if trip.trip_status == TripStatus.COMPLETED:
                return fail(TripCompletedError)

            updated = await uow.trips.update(trip, trip_status=TripStatus.CANCELLED)
            return Result.ok(updated)

    # --- Passenger Management ----------------------------------------------

    async def add_passenger(
        self, trip_id: uuid.UUID, booking_id: uuid.UUID
    ) -> Result[TripPassenger]:
        """Only an `ACCEPTED` booking belonging to the trip's own
        Advertisement may join (`_fetch_eligible_booking`). Only while
        the trip has not yet departed. `SCHEDULED -> READY` happens
        automatically the moment the first passenger is added (see
        module docstring).
        """
        async with self._uow_factory() as uow:
            trip_result = await self._fetch_trip(trip_id, uow)
            if isinstance(trip_result, Failure):
                return trip_result
            trip = trip_result

            violation = self._trip_modifiable_violation(trip)
            if violation is not None:
                return violation
            if trip.trip_status in _STARTED_STATUSES:
                return fail(
                    TripInvalidStatusTransitionError,
                    "Passengers cannot be added once a trip has started.",
                )

            booking_result = await self._fetch_eligible_booking(
                booking_id, trip.advertisement_id, uow
            )
            if isinstance(booking_result, Failure):
                return booking_result
            booking = booking_result

            violation = await self._passenger_ineligibility(booking.passenger_profile_id, uow)
            if violation is not None:
                return violation

            if await uow.trips.find_trip_passenger(trip_id, booking_id) is not None:
                return fail(
                    TripBookingNotEligibleError, "This booking has already been added to the trip."
                )

            trip_passenger = await uow.trips.create_trip_passenger(
                trip_id=trip_id,
                booking_id=booking_id,
                passenger_profile_id=booking.passenger_profile_id,
            )

            if trip.trip_status == TripStatus.SCHEDULED:
                await uow.trips.update(trip, trip_status=TripStatus.READY)

            return Result.ok(trip_passenger)

    async def remove_passenger(self, trip_id: uuid.UUID, booking_id: uuid.UUID) -> Result[None]:
        """Only while the trip has not yet departed. `READY -> SCHEDULED`
        happens automatically once the last remaining passenger is
        removed (see module docstring).
        """
        async with self._uow_factory() as uow:
            trip_result = await self._fetch_trip(trip_id, uow)
            if isinstance(trip_result, Failure):
                return trip_result
            trip = trip_result

            violation = self._trip_modifiable_violation(trip)
            if violation is not None:
                return violation
            if trip.trip_status in _STARTED_STATUSES:
                return fail(
                    TripInvalidStatusTransitionError,
                    "Passengers cannot be removed once a trip has started.",
                )

            trip_passenger = await uow.trips.find_trip_passenger(trip_id, booking_id)
            if trip_passenger is None:
                return fail(TripPassengerNotFoundError)

            await uow.trips.delete_trip_passenger(trip_passenger)

            remaining = await uow.trips.list_trip_passengers(trip_id)
            if not remaining and trip.trip_status == TripStatus.READY:
                await uow.trips.update(trip, trip_status=TripStatus.SCHEDULED)

            return Result.ok(None)

    async def board_passenger(
        self, trip_id: uuid.UUID, booking_id: uuid.UUID
    ) -> Result[TripPassenger]:
        """Only once the trip has departed (`STARTED`/`IN_PROGRESS`).
        Idempotent if already `BOARDED`; refused for a `NO_SHOW` ("no-show
        passenger cannot board") or already-`DROPPED_OFF` passenger.
        `STARTED -> IN_PROGRESS` happens automatically on the first
        successful boarding (see module docstring).
        """
        async with self._uow_factory() as uow:
            trip_result = await self._fetch_trip(trip_id, uow)
            if isinstance(trip_result, Failure):
                return trip_result
            trip = trip_result

            violation = self._trip_modifiable_violation(trip)
            if violation is not None:
                return violation
            if trip.trip_status not in _STARTED_STATUSES:
                return fail(
                    TripInvalidStatusTransitionError,
                    "A passenger can only board once the trip has started.",
                )

            trip_passenger = await uow.trips.find_trip_passenger(trip_id, booking_id)
            if trip_passenger is None:
                return fail(TripPassengerNotFoundError)

            if trip_passenger.boarding_status == BoardingStatus.BOARDED:
                return Result.ok(trip_passenger)
            if trip_passenger.boarding_status == BoardingStatus.NO_SHOW:
                return fail(TripBoardingInvalidTransitionError, "A no-show passenger cannot board.")
            if trip_passenger.boarding_status == BoardingStatus.DROPPED_OFF:
                return fail(
                    TripBoardingInvalidTransitionError,
                    "This passenger has already been dropped off.",
                )

            updated = await uow.trips.update_trip_passenger(
                trip_passenger,
                boarding_status=BoardingStatus.BOARDED,
                boarded_at=datetime.now(UTC),
            )

            if trip.trip_status == TripStatus.STARTED:
                await uow.trips.update(trip, trip_status=TripStatus.IN_PROGRESS)

            return Result.ok(updated)

    async def drop_off_passenger(
        self, trip_id: uuid.UUID, booking_id: uuid.UUID
    ) -> Result[TripPassenger]:
        """ "Passenger cannot be dropped off before boarding": requires
        `boarding_status == BOARDED`. Idempotent if already
        `DROPPED_OFF`.
        """
        async with self._uow_factory() as uow:
            trip_result = await self._fetch_trip(trip_id, uow)
            if isinstance(trip_result, Failure):
                return trip_result
            trip = trip_result

            violation = self._trip_modifiable_violation(trip)
            if violation is not None:
                return violation

            trip_passenger = await uow.trips.find_trip_passenger(trip_id, booking_id)
            if trip_passenger is None:
                return fail(TripPassengerNotFoundError)

            if trip_passenger.boarding_status == BoardingStatus.DROPPED_OFF:
                return Result.ok(trip_passenger)
            if trip_passenger.boarding_status != BoardingStatus.BOARDED:
                return fail(
                    TripBoardingInvalidTransitionError,
                    "A passenger must be boarded before they can be dropped off.",
                )

            updated = await uow.trips.update_trip_passenger(
                trip_passenger,
                boarding_status=BoardingStatus.DROPPED_OFF,
                dropped_off_at=datetime.now(UTC),
            )
            return Result.ok(updated)

    async def mark_no_show(
        self, trip_id: uuid.UUID, booking_id: uuid.UUID
    ) -> Result[TripPassenger]:
        """Only a still-`WAITING` passenger, and only once the trip has
        departed -- a no-show is discovered at the moment of pickup, not
        before. Idempotent if already `NO_SHOW`.
        """
        async with self._uow_factory() as uow:
            trip_result = await self._fetch_trip(trip_id, uow)
            if isinstance(trip_result, Failure):
                return trip_result
            trip = trip_result

            violation = self._trip_modifiable_violation(trip)
            if violation is not None:
                return violation
            if trip.trip_status not in _STARTED_STATUSES:
                return fail(
                    TripInvalidStatusTransitionError,
                    "A passenger can only be marked no-show once the trip has started.",
                )

            trip_passenger = await uow.trips.find_trip_passenger(trip_id, booking_id)
            if trip_passenger is None:
                return fail(TripPassengerNotFoundError)

            if trip_passenger.boarding_status == BoardingStatus.NO_SHOW:
                return Result.ok(trip_passenger)
            if trip_passenger.boarding_status != BoardingStatus.WAITING:
                return fail(
                    TripBoardingInvalidTransitionError,
                    "Only a still-waiting passenger can be marked no-show.",
                )

            updated = await uow.trips.update_trip_passenger(
                trip_passenger, boarding_status=BoardingStatus.NO_SHOW
            )
            return Result.ok(updated)

    # --- Trip Queries --------------------------------------------------

    async def get_driver_trips(self, driver_profile_id: uuid.UUID) -> Result[Sequence[Trip]]:
        async with self._uow_factory() as uow:
            trips = await uow.trips.list_by_driver_profile_id(driver_profile_id)
            return Result.ok(trips)

    async def get_passenger_trips(self, passenger_profile_id: uuid.UUID) -> Result[Sequence[Trip]]:
        async with self._uow_factory() as uow:
            trips = await uow.trips.list_by_passenger_profile_id(passenger_profile_id)
            return Result.ok(trips)

    async def get_active_trips(self) -> Result[Sequence[Trip]]:
        async with self._uow_factory() as uow:
            trips = await uow.trips.list_active()
            return Result.ok(trips)

    async def get_completed_trips(self) -> Result[Sequence[Trip]]:
        async with self._uow_factory() as uow:
            trips = await uow.trips.list_completed()
            return Result.ok(trips)


__all__ = ["TripService"]
