"""`RatingService` -- mutual post-trip feedback between a driver and a
passenger.

Every method opens its own Unit of Work via the injected factory and is
therefore independently atomic, same discipline as every service so far.
**Zero SQLAlchemy or ORM model import, including for typing** -- see
`ports.py`'s docstring for why this step draws a stricter line than
every prior one: this module only ever references `RatingRecord`/
`TripRecord`/`BookingRecord`/`DriverProfileRecord`/`PassengerProfileRecord`
(plain structural `Protocol`s), never `vtaxi.infrastructure.database.
models.rating.Rating` or any sibling ORM class.

A new rating denormalizes `driver_profile_id`/`passenger_profile_id`
from the given `trip_id`/`booking_id` (`Trip.driver_profile_id`,
`Booking.passenger_profile_id`) rather than accepting them as separate
caller-supplied parameters -- this is what makes `rater_user_id`/
`target_user_id` derivable from real, fetched data instead of trusted
verbatim from the caller, which is what gives "users cannot rate
themselves" real teeth (same reasoning `TripService.create_trip()` gives
for deriving `vehicle_id` from its `Advertisement`, and `BookingService.
_self_booking_violation` gives for comparing two independently-fetched
`user_id`s rather than two caller-supplied ones).

Not implemented, deliberately: writing the computed average back onto
`DriverProfile.average_rating`/`PassengerProfile.average_rating`.
`calculate_average_rating()` is a pure read/compute -- `models/rating.py`'s
own docstring calls recomputing those cached aggregates "the future
Service Layer's job," but persisting them would mean a write through
Identity's own repositories (or an injected `DriverService`/
`PassengerService`, mirroring `BookingService`'s dependency on
`AdvertisementService`), and this step's brief names no such
responsibility or dependency -- flagged, not built, matching this
project's established discipline of not adding what was not asked.
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.core.domain.result import Failure
from vtaxi.domain.rating.exceptions import (
    RatingAlreadyExistsError,
    RatingBookingNotFoundError,
    RatingInvalidDataError,
    RatingNotFoundError,
    RatingSelfRatingError,
    RatingTripNotEligibleError,
)
from vtaxi.infrastructure.database.enums import PartyRole, TripStatus

from .ports import BookingRecord, RatingRecord, RatingUnitOfWork, TripRecord

_MIN_SCORE = 1
_MAX_SCORE = 5


class RatingService:
    def __init__(self, uow_factory: UnitOfWorkFactory[RatingUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # --- Validation (private helpers) -------------------------------------

    def _score_violation(self, score: int) -> Failure | None:
        if not (_MIN_SCORE <= score <= _MAX_SCORE):
            return fail(
                RatingInvalidDataError, f"score must be between {_MIN_SCORE} and {_MAX_SCORE}."
            )
        return None

    async def _fetch_completed_trip(
        self, trip_id: uuid.UUID, uow: RatingUnitOfWork
    ) -> TripRecord | Failure:
        trip = await uow.trips.get_by_id(trip_id)
        if trip is None:
            return fail(RatingTripNotEligibleError, "The given trip does not exist.")
        if trip.trip_status != TripStatus.COMPLETED:
            return fail(RatingTripNotEligibleError)
        return trip

    async def _fetch_booking(
        self, booking_id: uuid.UUID, uow: RatingUnitOfWork
    ) -> BookingRecord | Failure:
        booking = await uow.bookings.get_by_id(booking_id)
        if booking is None:
            return fail(RatingBookingNotFoundError)
        return booking

    async def _resolve_rating_parties(
        self,
        trip_id: uuid.UUID,
        booking_id: uuid.UUID,
        rater_role: PartyRole,
        uow: RatingUnitOfWork,
    ) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID] | Failure:
        """Resolves and validates every cross-domain reference a new
        rating needs. Returns `(rater_user_id, target_user_id,
        driver_profile_id, passenger_profile_id)` on success -- shared by
        `create_rating()` and `validate_rating()` so the two can never
        silently disagree about what counts as a valid rating (same
        pattern as `AdvertisementService._vehicle_ineligibility`).
        """
        trip_result = await self._fetch_completed_trip(trip_id, uow)
        if isinstance(trip_result, Failure):
            return trip_result
        trip = trip_result

        booking_result = await self._fetch_booking(booking_id, uow)
        if isinstance(booking_result, Failure):
            return booking_result
        booking = booking_result

        driver = await uow.drivers.get_by_id(trip.driver_profile_id)
        if driver is None:
            return fail(RatingTripNotEligibleError, "The trip's driver no longer exists.")
        passenger = await uow.passengers.get_by_id(booking.passenger_profile_id)
        if passenger is None:
            return fail(RatingBookingNotFoundError, "The booking's passenger no longer exists.")

        if rater_role == PartyRole.PASSENGER:
            rater_user_id, target_user_id = passenger.user_id, driver.user_id
        else:
            rater_user_id, target_user_id = driver.user_id, passenger.user_id

        if rater_user_id == target_user_id:
            return fail(RatingSelfRatingError)

        existing = await uow.ratings.list_by_booking_id(booking_id)
        if any(r.rater_role == rater_role for r in existing):
            return fail(RatingAlreadyExistsError)

        return rater_user_id, target_user_id, trip.driver_profile_id, booking.passenger_profile_id

    # --- Validation (public) ---------------------------------------------

    async def validate_rating(
        self,
        *,
        trip_id: uuid.UUID,
        booking_id: uuid.UUID,
        rater_role: PartyRole,
        score: int,
    ) -> Result[None]:
        violation = self._score_violation(score)
        if violation is not None:
            return violation
        async with self._uow_factory() as uow:
            resolved = await self._resolve_rating_parties(trip_id, booking_id, rater_role, uow)
            return resolved if isinstance(resolved, Failure) else Result.ok(None)

    async def can_rate_booking(
        self, booking_id: uuid.UUID, rater_role: PartyRole
    ) -> Result[bool]:
        async with self._uow_factory() as uow:
            if await uow.bookings.get_by_id(booking_id) is None:
                return fail(RatingBookingNotFoundError)
            existing = await uow.ratings.list_by_booking_id(booking_id)
            return Result.ok(not any(r.rater_role == rater_role for r in existing))

    # --- Rating Management -------------------------------------------------

    async def create_rating(
        self,
        *,
        trip_id: uuid.UUID,
        booking_id: uuid.UUID,
        rater_role: PartyRole,
        score: int,
        comment: str | None = None,
    ) -> Result[RatingRecord]:
        violation = self._score_violation(score)
        if violation is not None:
            return violation

        async with self._uow_factory() as uow:
            resolved = await self._resolve_rating_parties(trip_id, booking_id, rater_role, uow)
            if isinstance(resolved, Failure):
                return resolved
            rater_user_id, target_user_id, driver_profile_id, passenger_profile_id = resolved

            try:
                rating = await uow.ratings.create(
                    trip_id=trip_id,
                    booking_id=booking_id,
                    driver_profile_id=driver_profile_id,
                    passenger_profile_id=passenger_profile_id,
                    rater_user_id=rater_user_id,
                    target_user_id=target_user_id,
                    rater_role=rater_role,
                    score=score,
                    comment=comment,
                )
            except ValueError as exc:
                return fail(RatingInvalidDataError, str(exc))
            return Result.ok(rating)

    async def update_rating(
        self, rating_id: uuid.UUID, *, score: int | None = None, comment: str | None = None
    ) -> Result[RatingRecord]:
        """Only `score`/`comment` are editable -- every other field is the
        rating's fixed identity (who rated whom, about which trip/booking)
        and is never accepted here. Re-validates `score` against the same
        range `create_rating()` enforces ("rating updates must follow
        business rules").
        """
        if score is not None:
            violation = self._score_violation(score)
            if violation is not None:
                return violation

        async with self._uow_factory() as uow:
            rating = await uow.ratings.get_by_id(rating_id)
            if rating is None:
                return fail(RatingNotFoundError)

            fields: dict[str, Any] = {}
            if score is not None:
                fields["score"] = score
            if comment is not None:
                fields["comment"] = comment
            if not fields:
                return Result.ok(rating)

            try:
                updated = await uow.ratings.update(rating, **fields)
            except ValueError as exc:
                return fail(RatingInvalidDataError, str(exc))
            return Result.ok(updated)

    async def delete_rating(self, rating_id: uuid.UUID) -> Result[None]:
        async with self._uow_factory() as uow:
            rating = await uow.ratings.get_by_id(rating_id)
            if rating is None:
                return fail(RatingNotFoundError)
            await uow.ratings.delete(rating)
            return Result.ok(None)

    async def get_rating(self, rating_id: uuid.UUID) -> Result[RatingRecord]:
        async with self._uow_factory() as uow:
            rating = await uow.ratings.get_by_id(rating_id)
            if rating is None:
                return fail(RatingNotFoundError)
            return Result.ok(rating)

    # --- Queries -----------------------------------------------------------

    async def get_booking_ratings(self, booking_id: uuid.UUID) -> Result[Sequence[RatingRecord]]:
        async with self._uow_factory() as uow:
            ratings = await uow.ratings.list_by_booking_id(booking_id)
            return Result.ok(ratings)

    async def get_driver_ratings(
        self, driver_profile_id: uuid.UUID
    ) -> Result[Sequence[RatingRecord]]:
        async with self._uow_factory() as uow:
            ratings = await uow.ratings.list_by_driver_profile_id(driver_profile_id)
            return Result.ok(ratings)

    async def get_passenger_ratings(
        self, passenger_profile_id: uuid.UUID
    ) -> Result[Sequence[RatingRecord]]:
        async with self._uow_factory() as uow:
            ratings = await uow.ratings.list_by_passenger_profile_id(passenger_profile_id)
            return Result.ok(ratings)

    async def calculate_average_rating(
        self,
        *,
        driver_profile_id: uuid.UUID | None = None,
        passenger_profile_id: uuid.UUID | None = None,
    ) -> Result[Decimal | None]:
        """`Result.ok(None)` -- not a failure -- when the party has no
        ratings yet: a meaningful, valid answer (same convention as
        `GeographyService.get_parent`'s `Result.ok(None)` for a
        COUNTRY-level area). Only ratings *received* count: `driver_profile_id`
        filters to `rater_role == PASSENGER` (a passenger rating the
        driver), and `passenger_profile_id` filters to `rater_role ==
        DRIVER` -- both `driver_profile_id`/`passenger_profile_id` on a
        `Rating` row denormalize the fixed pair regardless of which
        direction that specific row is, so an unfiltered average would
        wrongly include ratings this party *gave*, not just received.
        """
        if (driver_profile_id is None) == (passenger_profile_id is None):
            raise ValueError(
                "calculate_average_rating() requires exactly one of "
                "driver_profile_id or passenger_profile_id"
            )

        async with self._uow_factory() as uow:
            if driver_profile_id is not None:
                all_ratings = await uow.ratings.list_by_driver_profile_id(driver_profile_id)
                received = [r for r in all_ratings if r.rater_role == PartyRole.PASSENGER]
            else:
                assert passenger_profile_id is not None
                all_ratings = await uow.ratings.list_by_passenger_profile_id(passenger_profile_id)
                received = [r for r in all_ratings if r.rater_role == PartyRole.DRIVER]

            if not received:
                return Result.ok(None)
            average = Decimal(sum(r.score for r in received)) / Decimal(len(received))
            return Result.ok(average.quantize(Decimal("0.01")))


__all__ = ["RatingService"]
