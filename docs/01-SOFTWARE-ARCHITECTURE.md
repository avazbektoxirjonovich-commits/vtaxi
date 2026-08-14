# VTaxi — Software Architecture Document (SAD)

**Step 1 of the staged build plan. Status: DRAFT — awaiting approval.**

**Document owner:** Principal Software Engineer / Solution Architect role
**Project:** VTaxi — Telegram-based intercity taxi booking platform
**Initial corridor:** Namangan ⇄ Tashkent (must extend to N cities without rewrite)
**Target scale:** 100,000+ users
**Stack (fixed by product decision):** Python 3.13, Aiogram 3, PostgreSQL, SQLAlchemy 2.0 (async), Alembic, Pydantic Settings, uv, async-everywhere

---

## 1. Purpose and Scope

VTaxi connects **passengers** who need an intercity seat and **drivers** who publish intercity trips, with an **administrator** layer that gatekeeps driver quality and monitors the platform. This document defines the system's architecture *before any code is written*. Every later step (folder structure, DB schema, config, infra, domain, bot, services, repositories, handlers) is a refinement of the decisions made here — nothing here should need to change once implementation starts. If it does, we stop and revise this document first.

### 1.1 Hard constraints from the product spec

- Two directions today (Namangan⇄Tashkent), but the model must treat "direction" as **data**, not code, so city #3 is a database row, not a deployment.
- Three roles: Passenger, Driver, Admin — one Telegram bot, role resolved from the user's state, not from separate bots.
- Driver requires admin approval before publishing trips.
- Seats are a finite, contended resource — correctness under concurrent booking is a first-class requirement, not an edge case.
- The bot is explicitly *one* of several future front doors: REST API, Admin Panel, Background Workers, Mobile App, Web Dashboard, Payment Gateway. **This single constraint drives most of the architecture below.**

### 1.2 Out of scope for v1 (explicitly deferred, so we don't over-engineer now)

- Real payment processing (design leaves a seam, does not implement a gateway).
- PostGIS-grade geospatial routing (we use straight-line/haversine distance on lat/lon first; the port is swappable later).
- Multi-language i18n framework (Uzbek/Russian copy can be flat resource files for now; not an architectural concern yet).

---

## 2. Architectural Style

**Clean Architecture (Ports & Adapters / Hexagonal) + tactical Domain-Driven Design.**

### Why this over a "normal" aiogram bot project (handlers → DB directly)

A typical small Telegram bot puts SQLAlchemy calls straight inside `@router.message()` handlers. That is the fastest way to *start*, and the fastest way to make this specific project unmaintainable, because the spec already promises a REST API, an Admin Panel, and a Mobile App on top of the *same business rules* (seat allocation, driver approval, matching). If business logic lives inside Aiogram handlers:

- The REST API team either duplicates the rules (drift, bugs, two sources of truth) or imports bot-framework code into a web server (wrong dependency direction).
- Every business-rule change requires re-testing through Telegram, because there's no way to unit-test a handler without mocking `Bot`, `Update`, FSM context, etc.
- Seat-decrement races become handler-local bugs instead of a domain invariant enforced in one place.

Clean Architecture fixes this by drawing a hard boundary: **domain and application logic know nothing about Aiogram, SQLAlchemy, or Redis.** Aiogram is a *delivery mechanism*, exactly as interchangeable as the future FastAPI layer. This is the single most important decision in this document — it is why every later step (folders, DB, services, repos) is shaped the way it is.

### 2.1 The Dependency Rule

```
┌─────────────────────────────────────────────────────────┐
│  Presentation  (Aiogram routers, future FastAPI routers, │
│  future Admin Panel views)                               │
│        depends on ↓                                      │
│  Application  (use cases, DTOs, port interfaces)          │
│        depends on ↓                                      │
│  Domain  (entities, value objects, domain services,       │
│  domain events — zero framework imports)                 │
│        ↑ implemented by                                  │
│  Infrastructure  (SQLAlchemy repos, Redis, Telegram file  │
│  storage, notification senders)                           │
└─────────────────────────────────────────────────────────┘
```

Source code dependencies point **only inward**. Domain defines interfaces (`AbstractTripRepository`, `AbstractNotifier`, …); Infrastructure implements them; a **composition root** (DI container, built in Step 8/9) wires concrete implementations into use cases at startup. Presentation calls use cases, never repositories, never the ORM.

This is what lets us add a REST API in month 4 by writing new Presentation-layer routers that call the *same* application use cases — no domain or business-rule code is touched.

---

## 3. Bounded Contexts (DDD)

Rather than one flat `models.py`, the domain is split into contexts that map to how the business actually talks about the problem. Each becomes its own package inside `domain/` and `application/` in the folder structure (Step 2).

| # | Bounded Context | Responsibility | Key Aggregate Root(s) |
|---|---|---|---|
| 1 | **Identity & Access** | User accounts, role (Passenger/Driver/Admin), phone verification, suspension | `User` |
| 2 | **Driver Verification** | Driver-specific profile, uploaded documents, vehicle info, approval workflow | `DriverProfile` |
| 3 | **Geography** | Region/District/Village/Mahalla/Street hierarchy, coordinates, `Direction` (city-pair) | `Direction`, `AdministrativeArea` |
| 4 | **Trip Publishing** | A driver's advertised trip: seats, price, vehicle class, lifecycle | `Trip` |
| 5 | **Booking** | A passenger's request against a trip, its lifecycle, seat consumption | `Booking` |
| 6 | **Matching** | Read-side domain service: find & rank candidate trips for a booking request | *(stateless domain service, no own aggregate)* |
| 7 | **Rating & Feedback** | Post-trip mutual rating (driver↔passenger) | `Rating` |
| 8 | **Notification** | Outbound event-driven messaging to Telegram, decoupled from business logic | *(no aggregate — pure port/adapter)* |
| 9 | **Administration** | Statistics, moderation actions, broadcast, complaint handling | `Complaint`, read-models over other contexts |

**Why split this way and not "one big models.py":** each context has its own reason to change (e.g., geography hierarchy changes when we add a city; trip lifecycle changes when we add vehicle classes) — this is the Single Responsibility Principle applied at the package level, not just the class level. It also means Step 6 (Core Domain) can be built and unit-tested one context at a time, which matches the "never generate the whole project at once" rule.

### 3.1 Why `User`, `DriverProfile` are separate aggregates (not one bloated `User` table)

A `User` is Identity & Access: telegram_id, phone, role, status. A `DriverProfile` is one-to-one with a `User` but belongs to a different bounded context (Driver Verification) with its own lifecycle (`PENDING_REVIEW → APPROVED/REJECTED → SUSPENDED`) and its own volatile data (documents, vehicle). Keeping them separate means:
- Passenger-only code paths never load driver-document blobs.
- The approval workflow (admin-facing) can evolve independently of login/auth.
- Adding "Driver can also be a Passenger sometimes" later is a foreign key, not a schema rewrite.

### 3.2 Why `Booking` references `Trip` by ID instead of `Trip` owning a `bookings` collection as one aggregate

This is a concurrency decision, explained in §6.

---

## 4. Domain Model Overview

### 4.1 Core entities and value objects

- **User** (entity, aggregate root): `id`, `telegram_id`, `phone_number` (VO, normalized E.164), `full_name`, `role` (enum: PASSENGER/DRIVER/ADMIN — see note below), `status` (ACTIVE/SUSPENDED), timestamps.
- **DriverProfile** (entity, aggregate root, 1:1 with User): `user_id`, `license_document_ref`, `vehicle_registration_ref`, `vehicle_photo_ref`, `profile_photo_ref` (all *file references*, not blobs — see §7.3), `vehicle` (VO: model, color, plate number, class), `approval_status` (PENDING/APPROVED/REJECTED/SUSPENDED), `current_location` (VO).
- **AdministrativeArea** (entity, self-referencing tree): `region → district → village/mahalla → street`, generic depth-first hierarchy, not hardcoded to Namangan/Tashkent.
- **Direction** (entity, reference data): `origin_area_id`, `destination_area_id`, `is_active`. Namangan⇄Tashkent is *two rows* (directionality matters for search), not an enum value.
- **Trip** (entity, aggregate root): `id`, `driver_id`, `direction_id`, `origin_point` (VO: lat/lon + free-text), `destination_point`, `departure_time`, `price`, `seats_total`, `seats_available`, `vehicle_class` (enum: ECONOMY/COMFORT/BUSINESS/MINIVAN), `status` (DRAFT/ACTIVE/FULL/STARTED/COMPLETED/CANCELLED).
- **Booking** (entity, aggregate root): `id`, `trip_id`, `passenger_id`, `seats_requested`, `pickup_point` (VO), `destination_point` (VO), `comment`, `status` (PENDING/ACCEPTED/REJECTED/CANCELLED/COMPLETED).
- **Rating** (entity, aggregate root): `booking_id`, `rater_id`, `ratee_id`, `score` (1–5), `comment`.
- **GeoPoint** (value object): `lat`, `lon`, optional `address_text` — used by both hierarchical-selector input and Telegram-location input, so downstream code (distance calc) never cares which input method was used. This is the key abstraction that unifies "Location System" method 1 and method 2 from the spec.

**Note on `role`:** modeled as a value on `User`, not as separate `Passenger`/`Driver` root entities, because in this domain every Driver *also* has the full passenger login/identity lifecycle (phone verification, suspension) — only the additional Driver-specific data (`DriverProfile`) diverges. This avoids duplicating Identity logic across two entities, per DRY.

### 4.2 Domain events (for cross-context decoupling)

Contexts do not call each other directly (e.g., Booking does not import Notification). Instead, domain/application layer raises events; an event dispatcher (in-process for v1, see ADR-008) invokes registered handlers:

- `DriverApproved`, `DriverRejected`, `DriverSuspended`
- `TripPublished`, `TripSeatsExhausted` (→ triggers auto FULL transition), `TripCancelled`, `TripStarted`, `TripCompleted`
- `BookingRequested`, `BookingAccepted`, `BookingRejected`, `BookingCancelled`, `BookingCompleted`
- `RatingSubmitted`

**Why events instead of direct calls:** `TripSeatsExhausted` must (a) flip trip status, (b) remove it from matching results, (c) notify the driver, (d) potentially notify passengers on a waitlist (future). Wiring all four as direct function calls inside the booking use case violates SRP and blocks future consumers from being added without touching booking code. An event + handler list keeps the booking use case's only job as "book a seat correctly."

---

## 5. State Machines

### 5.1 Trip status

```
DRAFT → ACTIVE → FULL → STARTED → COMPLETED
          │         │
          └────→ CANCELLED ←──────┘
```
- `ACTIVE → FULL`: automatic, triggered when `seats_available` reaches 0 (domain invariant, enforced in the `Trip` entity itself, not in a handler).
- `FULL → ACTIVE`: automatic, if a booking against it is cancelled and seats free up again (spec implies seats are dynamic; this reversal keeps the trip re-searchable — confirm in Step 3 review if this is desired, flagging as an open question).
- `ACTIVE/FULL → CANCELLED`: manual, by driver.
- `ACTIVE/FULL → STARTED`: manual, by driver ("depart").
- `STARTED → COMPLETED`: manual, by driver ("complete trip").

### 5.2 Booking status

```
PENDING → ACCEPTED → COMPLETED
   │           │
   └→ REJECTED │
   └→ CANCELLED ┘ (cancellable up until COMPLETED, per spec)
```

### 5.3 Driver approval status

```
PENDING_REVIEW → APPROVED → SUSPENDED
       │
       └→ REJECTED
```
A driver in any state except `APPROVED` cannot call the "publish trip" use case — this is enforced as a **guard clause in the application-layer use case**, not merely a UI restriction, so the REST API can never bypass it either.

---

## 6. The Seat Concurrency Problem (why `Booking` is its own aggregate)

Spec example: 4 seats, three passengers book 2 / 1 / 1 concurrently. If two passengers request the *last* seat at the same instant, exactly one must succeed.

**Decision:** seat consumption is implemented as a single **atomic conditional UPDATE** at the database level:

```sql
UPDATE trips
SET seats_available = seats_available - :requested
WHERE id = :trip_id AND seats_available >= :requested
RETURNING seats_available;
```

If zero rows return, the application layer raises a domain error (`NotEnoughSeatsAvailable`) and the use case aborts the booking — no partial state, no separate lock step needed, no lost-update race, because PostgreSQL guarantees this single statement is atomic per row. This is preferred over `SELECT ... FOR UPDATE` because it avoids holding a row lock across a network round-trip to application code — the whole check-and-decrement happens in one server-side statement, which scales far better under contention at 100k-user volume.

This is also *why Booking is a separate aggregate from Trip* rather than "Trip has a list of Bookings": if Booking were a child entity loaded as part of the Trip aggregate (DDD "one aggregate = one transaction" rule), every concurrent booking attempt against a popular trip would contend on loading/saving the entire aggregate graph. Keeping them separate means the seat counter update is a tiny, isolated, atomic operation, and the `Booking` row is an independent record referencing `trip_id` — standard "aggregates reference each other by ID, not by object composition" DDD guidance.

---

## 7. Cross-Cutting Concerns

### 7.1 Async everywhere

Aiogram 3 (async native) + SQLAlchemy 2.0 async engine (`asyncpg` driver) + `redis.asyncio`. No sync DB calls anywhere, including in background workers — one execution model end-to-end avoids the classic "sync call blocks the event loop under load" failure mode at scale.

### 7.2 Dependency Injection

No global state, no module-level singletons holding DB sessions. A DI container (candidate: `dishka`, purpose-built for Aiogram 3 + async — final choice justified in Step 8) constructs use cases per-request with a fresh session/unit-of-work, injected into handlers via Aiogram middleware. This is what lets application/domain code stay framework-agnostic: handlers ask the container for a use case; they never construct a repository themselves.

### 7.3 File uploads (driver documents/photos)

Decision: store **Telegram `file_id`** references (and a storage-key abstraction behind a port) rather than raw bytes in Postgres. Reasoning: Telegram already hosts the binary; duplicating it in our DB/object storage is wasted cost with no benefit at MVP stage. The port (`AbstractFileStorage`) is defined now so that swapping to S3/MinIO later (for the future Web Dashboard, where Telegram `file_id`s aren't retrievable outside Bot API) is an adapter swap, not a rewrite.

### 7.4 Configuration

Pydantic Settings, one `Settings` object built from `.env`, validated at process startup (fail-fast on missing/invalid config — e.g., missing `BOT_TOKEN` crashes on boot, not on first message). Per-environment `.env` files (`dev`, `staging`, `prod`); no secrets committed, `.env.example` checked in with placeholder values (defined in Step 4).

### 7.5 Notification delivery

`AbstractNotifier` port in application layer; Aiogram-backed adapter in infrastructure sends the actual Telegram messages. Domain/application code never imports `aiogram.Bot`. This means the same `BookingAccepted` event handler could later push a push-notification (mobile app) or an email, by registering an additional adapter — no application code changes.

### 7.6 Observability

Structured logging (`structlog` or stdlib `logging` with JSON formatter — decided in Step 4) from day one, correlation/request ID threaded through middleware → use case → repository, so a single booking attempt is traceable across logs. Metrics/tracing hooks (OpenTelemetry-compatible) are a deferred but designed-for seam, not implemented in MVP.

### 7.7 Testing strategy (QA hat)

- **Domain layer:** pure unit tests, no DB, no mocks needed beyond simple fakes — this is the payoff of keeping domain framework-free.
- **Application layer (use cases):** unit tests against fake repositories (in-memory implementations of the same port interfaces) — fast, no Postgres required.
- **Infrastructure layer (repositories):** integration tests against a real Postgres (testcontainers or a dockerized test DB), verifying the atomic seat-update SQL actually behaves under concurrency (a dedicated concurrency test spins up N concurrent booking calls against a 1-seat trip and asserts exactly one succeeds).
- **Presentation (Aiogram handlers):** thin by design (they only call use cases), so tested mostly via a small number of end-to-end scenario tests using Aiogram's test utilities.

---

## 8. Scalability Plan (target: 100,000+ users)

| Concern | Decision | Why |
|---|---|---|
| Bot transport | Webhook mode (not long polling), behind reverse proxy, multiple stateless bot worker processes | Long polling doesn't horizontally scale past one process holding the connection; webhook + N workers behind a load balancer does. |
| FSM/session state | Redis-backed Aiogram storage, not in-memory | In-memory FSM storage breaks the moment there's more than one bot process, which we need for horizontal scaling. |
| Nearby-driver queries | Cache active-trips-by-direction in Redis, refreshed on `TripPublished`/`TripSeatsExhausted`/`TripCancelled` events; fall back to Postgres on cache miss | Matching is a hot, read-heavy path; hitting Postgres per search at 100k users is avoidable load. |
| Distance calculation | Haversine on lat/lon in application code for v1; `Abstract DistanceCalculator` port so PostGIS/earthdistance can replace it later without touching Matching use case | PostGIS is real infra overhead not justified until trip-search volume demands it — YAGNI, but the seam is designed in now. |
| Background/async jobs | Separate worker process (candidate: `arq` or `taskiq`, async-native) for broadcasts, scheduled reminders, statistics aggregation | Keeps the bot's request/response path fast; a slow broadcast job must never block booking traffic. |
| DB scaling | Proper indexing (direction, status, departure_time on Trip; trip_id, passenger_id, status on Booking) from Step 3 onward; read-replica introduction is a config change, not an architecture change, because repositories already abstract "where does this read go" | Right architecture now avoids a rewrite later; we don't build the replica itself until load requires it (YAGNI). |
| Rate limiting / anti-abuse | Aiogram throttling middleware per user | Prevents a single abusive user from degrading service for others. |

---

## 9. Security Considerations

- Phone verification via Telegram's native contact-share, normalized and stored once (no OTP infra to build/maintain for MVP).
- Driver publish-trip capability is gated by `approval_status == APPROVED`, enforced in the **use case**, never only hidden in the UI — a REST API caller or a bug in bot routing cannot bypass it.
- No secrets in source control; `.env` gitignored, `.env.example` documents required keys.
- SQLAlchemy parameterized queries throughout — no raw string SQL interpolation, eliminating SQL-injection risk by construction.
- File references only (see §7.3) — the bot never stores raw driver-document bytes in our DB, shrinking our own data-breach blast radius.
- Least-privilege DB role for the application user (no superuser, no DDL rights at runtime — Alembic migrations run under a separate elevated role in CI/CD, defined in Step 5).

---

## 10. Extensibility: Adding a Third City

Because `AdministrativeArea` and `Direction` are data (not enum members or hardcoded routing logic), adding e.g. Andijan⇄Tashkent is:
1. Insert `AdministrativeArea` rows for the new region's hierarchy.
2. Insert a `Direction` row (and its reverse) linking the areas.
3. Done — no code deploy required, matching/booking/trip logic is direction-agnostic by construction.

This is the concrete payoff of the "direction as data" decision flagged in §1.1.

---

## 11. High-Level Component Diagram

```
                         ┌───────────────────────────┐
                         │   Telegram Bot API         │
                         └──────────────┬─────────────┘
                                        │ webhook
                         ┌──────────────▼─────────────┐
                         │  Presentation: Aiogram      │   (Step 7)
                         │  routers/handlers/FSM       │
                         │  + future FastAPI routers   │   (future)
                         │  + future Admin Panel views │   (future)
                         └──────────────┬─────────────┘
                                        │ calls
                         ┌──────────────▼─────────────┐
                         │  Application: Use Cases,    │   (Step 8)
                         │  DTOs, Port interfaces,      │
                         │  Domain Event dispatcher     │
                         └──────────────┬─────────────┘
                                        │ orchestrates
                         ┌──────────────▼─────────────┐
                         │  Domain: Entities, VOs,      │   (Step 6)
                         │  Domain services, Events     │
                         │  (zero framework imports)    │
                         └──────────────▲─────────────┘
                                        │ implements ports
                         ┌──────────────┴─────────────┐
                         │  Infrastructure: SQLAlchemy  │   (Step 9)
                         │  repositories, Redis cache,  │
                         │  Telegram file storage,      │
                         │  Notification senders        │
                         └──────────────┬─────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
             ┌────────────┐      ┌────────────┐      ┌────────────┐
             │ PostgreSQL │      │   Redis     │      │  Background │
             │ (async,    │      │ (FSM, cache,│      │  Workers    │
             │ SQLAlchemy │      │  throttling)│      │  (arq/      │
             │ 2.0+Alembic)│      │            │      │  taskiq)    │
             └────────────┘      └────────────┘      └────────────┘
```

---

## 12. Architecture Decision Records (Summary)

| ADR | Decision | Alternative considered | Why rejected |
|---|---|---|---|
| 001 | Clean Architecture + DDD | Simple layered bot script | Fails the moment REST API/Admin Panel/Mobile need the same business rules — logic duplication and drift. |
| 002 | Aiogram 3 | python-telegram-bot | Fixed by product spec; also Aiogram 3's router/filter model fits DI-based composition well. |
| 003 | PostgreSQL + SQLAlchemy 2.0 async + Alembic | MongoDB / sync SQLAlchemy | Seat booking needs relational integrity + transactions; async required to avoid blocking the event loop. |
| 004 | Repository Pattern + ports | Direct ORM calls in use cases | Keeps application/domain testable and framework-agnostic; enables swapping/mocking persistence. |
| 005 | DI container (candidate `dishka`) | Manual constructor wiring per handler | Avoids global state and repetitive wiring code as the number of use cases grows past a handful. |
| 006 | Geography/Direction as data | Hardcoded `NAMANGAN_TASHKENT` enum | Spec explicitly requires future cities without rewrite; data-driven is the only way to satisfy that. |
| 007 | Redis for FSM + cache + throttling | In-memory dict storage | Breaks under horizontal scaling (multiple bot processes) which 100k users requires. |
| 008 | Atomic conditional `UPDATE` for seat decrement | `SELECT FOR UPDATE` pessimistic lock | Avoids holding row locks across round-trips; better throughput under contention. |
| 009 | Separate background worker process | Cron-in-bot-process / sync jobs blocking handlers | Keeps user-facing latency low; slow jobs (broadcast) isolated from booking path. |
| 010 | File references (`file_id`) not blob storage | Store binary in Postgres | Telegram already hosts the file; storing it again is pure cost with no v1 benefit. |

---

## 13. Open Questions for Review (please confirm before Step 2)

1. **`FULL → ACTIVE` auto-reversal** (§5.1): if a passenger cancels and a seat frees up, should the trip automatically become searchable again? Assumed **yes** unless you say otherwise.
2. **Driver-initiated cancellation with existing accepted bookings**: does cancelling a trip cascade-cancel all its bookings (with passenger notification), or is that blocked until bookings are individually resolved? Assumed **cascade-cancel + notify**.
3. **Rating**: is it mandatory after every completed trip, or optional? Assumed **optional**, per spec wording ("rate driver after trip" reads as an available action, not enforced).
4. **DI library**: proposing `dishka` (async-native, designed with Aiogram 3 in mind) — open to `punq`/manual composition root if you have a preference; will finalize with justification in Step 8.
5. **Background task queue**: proposing `arq` (lightweight, Redis-backed, async-native, fits our Redis dependency already) over Celery (sync-rooted, heavier) — will finalize in Step 5 (Infrastructure).

---

## 14. Revision 2 — Architecture Amendments (approved together with Step 2)

The following amendments were requested before implementation began and are now part of the approved architecture. Rev 1 (§1–§13) stands except where explicitly superseded below.

### 14.1 Advertisement-first flow (renames Rev 1's `Trip` aggregate)

- **Old (Rev 1):** Driver publishes a `Trip` directly; passengers book against it.
- **New (Rev 2):** `Driver → Advertisement → Booking → Trip → Rating`
- **`Advertisement`** (renamed from Rev 1's `Trip`): what the driver publishes — direction, seats_total/available, price, vehicle_class, status (DRAFT/ACTIVE/FULL/CLOSED/CANCELLED). Bookings are made against an Advertisement.
- **`Trip`** (new aggregate, new meaning): the realized journey, created only when the driver marks departure, carrying the Advertisement's accepted Bookings forward. Status: STARTED → COMPLETED (or CANCELLED).
- **Why:** this mirrors real-world semantics (an advertisement is a listing; a trip is an event that happened), keeps the booking-time concurrency problem (§6, unchanged — atomic `UPDATE` against `Advertisement.seats_available`) separate from execution-time concerns (departure, completion, rating eligibility), and gives Statistics (§14.10) and Rating an unambiguous "did this journey happen" record independent of how many Advertisements a driver churned through.
- **Bounded context table impact:** context #4 renamed **"Trip Publishing" → "Advertisement"**; new context **#4b "Trip Execution"** added (see updated table below).

### 14.2 No continuous live location

- Driver location is captured **once** per Advertisement (a single Telegram location message, or manual address selection) and persisted as the existing `GeoPoint` value object (Rev 1 §4.1). The driver may resend it manually to update it. No live-location subscription, no periodic background polling.
- **Why:** continuous tracking multiplies Bot API traffic and writes per active driver for precision that doesn't matter on an intercity corridor (this isn't turn-by-turn urban ride-hailing) — YAGNI. The `AbstractGeoEngine` port (§14.8) leaves room to add real-time tracking later as a new adapter without touching Advertisement/Trip domain logic.

### 14.3 Driver operational status (new axis, orthogonal to `approval_status`)

- Rev 1's `DriverProfile.approval_status` (PENDING_REVIEW/APPROVED/REJECTED/SUSPENDED) is the **verification gate**.
- Rev 2 adds `DriverProfile.availability_status`: **ONLINE / OFFLINE / BUSY / ON_TRIP / BANNED** — **operational visibility** for matching.
- **Reconciliation call (flagging for confirmation):** `SUSPENDED` is dropped from `approval_status` and folded into `availability_status.BANNED` — both meant "blocked by an admin," and two fields able to express "blocked" invites inconsistent state. `approval_status` now only covers the one-time verification workflow; every enforcement action (temporary or permanent) is `availability_status = BANNED`, recorded with a reason via Complaint (§14.6) / Audit Log (§14.7). **If SUSPENDED and BANNED were meant to be distinct (temporary vs. permanent), say so before Step 3** and both will be modeled.
- Transitions are event-driven: manual toggle → ONLINE/OFFLINE; pending booking request awaiting response → BUSY; `TripStarted` → ON_TRIP; `TripCompleted` → ONLINE; Complaint resolved against driver → BANNED.

### 14.4 Passenger status (new)

- `User.passenger_status` (meaningful when role=PASSENGER): **ACTIVE / WAITING / BOOKED / ON_TRIP / COMPLETED / BANNED**.
- Modeled as a **projection**, not a directly-editable field: updated only by domain event handlers (`BookingRequested`→WAITING, `BookingAccepted`→BOOKED, `TripStarted`→ON_TRIP, `TripCompleted`→COMPLETED then reset to ACTIVE, `BookingRejected`/`BookingCancelled`→ACTIVE, Complaint resolved against passenger→BANNED). Keeping it event-derived (reusing the Rev 1 §4.2 dispatcher) prevents this field from ever drifting out of sync with the real Booking/Trip state.

### 14.5 Queue Engine (new bounded context)

- **Problem:** several ONLINE, approved drivers waiting in the same origin area for the same Direction — sorting by distance/rating alone always surfaces the same top driver and starves the rest.
- **Design:** an independent module (`domain/queue_engine/`, `application/queue_engine/`) maintaining a fair-rotation index per `(Direction, origin area)`. Matching calls Queue Engine to fairness-adjust its distance/rating-ranked candidate set (e.g., weighted round-robin), rather than Queue Engine replacing that ranking.
- **Why independent:** fairness policy is exactly the kind of volatile, business-tunable rule that should sit behind its own port (`AbstractQueuePort`) so it can change without touching the Matching algorithm. Backing store candidate: Redis sorted set keyed by `direction_id:area_id` — queue position is ephemeral, high-churn state, a poor fit for Postgres row updates at 100k-driver scale.

### 14.6 Complaint Module (new bounded context)

- `Complaint` aggregate root: `complainant_id`, `complainant_role`, `respondent_id`, optional `related_booking_id`/`related_trip_id`, `reason`, `description`, `status` (OPEN/UNDER_REVIEW/RESOLVED/DISMISSED), `resolution_action` (NONE/WARNING/BAN).
- Either role can file one against the other. Resolving a Complaint with `resolution_action=BAN` is the **only** path that flips `availability_status`/`passenger_status` → BANNED — centralizes moderation instead of letting bans happen ad hoc from other use cases.

### 14.7 Admin Audit Log (new bounded context)

- `AuditLogEntry` (append-only): `admin_id`, `action` (DRIVER_APPROVED / DRIVER_REJECTED / DRIVER_BANNED / TRIP_DELETED / BROADCAST_SENT / COMPLAINT_RESOLVED / …), `target_type`, `target_id`, `reason`, `occurred_at`.
- **Decision:** every admin-facing use case is wrapped by a single audit-logging decorator in the application layer, instead of each use case manually recording its own entry — this makes audit completeness structural (you cannot forget to call something that isn't optional), which matters here because it's a compliance requirement, not a convenience feature.

### 14.8 Geo Engine (elevates the informal Rev 1 §8 note to a first-class context)

- Consolidates distance calculation (haversine now, swappable later), nearby-driver search, candidate sorting, location normalization (hierarchical-selector address ↔ coordinates ↔ Telegram-location, all converging on the Rev 1 §4.1 `GeoPoint` VO), and a reserved seam for a future real map provider.
- `AbstractGeoEngine` port lives in `application/geo_engine/`; Matching and Queue Engine both depend on it instead of each reimplementing distance math.

### 14.9 Search Engine (new bounded context)

- Autocomplete/search over the `AdministrativeArea` hierarchy (region/district/village/mahalla/street). A **read-optimized query layer over Geography's data**, not a new data owner. Candidate implementation: PostgreSQL `pg_trgm` trigram index for fuzzy address autocomplete — avoids standing up separate search infrastructure (e.g. Elasticsearch) before query volume justifies it (YAGNI).

### 14.10 Statistics Module (new bounded context)

- Read-only aggregation for **Admin** (platform-wide: active drivers, completed trips, complaint volume, revenue-adjacent counts once payments exist) and **Driver** (personal: trips completed, rating average, earnings-adjacent counts). A **query-side module** (lightweight CQRS): reads the same Postgres tables via dedicated aggregation queries/materialized views, never writes — keeps reporting out of Booking/Trip use cases.

### 14.11 Payment provider seam (Click / Payme / Paynet) — prepared, not implemented

- `AbstractPaymentGateway` port is reserved in `application/payment/` (interface written in Step 8, not now). Three placeholder adapter packages reserved in `infrastructure/payment_providers/{click,payme,paynet}/`, no logic. No `Payment` aggregate/table exists until a dedicated payments step is scheduled — adding one later is "implement the port + add a foreign key," not a rewrite, since Booking/Trip carry no payment-status dependency today.

### 14.12 Updated Bounded Context Table (supersedes Rev 1 §3)

| # | Bounded Context | Rev 2 change |
|---|---|---|
| 1 | Identity & Access | unchanged |
| 2 | Driver Verification | `approval_status` narrowed to verification only; `availability_status` added (§14.3) |
| 3 | Geography | unchanged (now has a read-side sibling, #14) |
| 4 | **Advertisement** | renamed from "Trip Publishing"; aggregate renamed `Trip`→`Advertisement` (§14.1) |
| 4b | **Trip Execution** *(new)* | new `Trip` aggregate = realized journey, created post-booking (§14.1) |
| 5 | Booking | unchanged; now targets an Advertisement |
| 6 | Matching | unchanged core algorithm; now consults Queue Engine (#10) and Geo Engine (#13) as ports |
| 7 | Rating & Feedback | unchanged; now rates against a Trip, not an Advertisement |
| 8 | Notification | unchanged |
| 9 | Administration | unchanged; now the home for Statistics (#15) dashboards |
| 10 | **Queue Engine** *(new)* | fairness rotation, independent module (§14.5) |
| 11 | **Complaint** *(new)* | moderation intake, sole path to a ban (§14.6) |
| 12 | **Admin Audit Log** *(new)* | append-only, decorator-enforced (§14.7) |
| 13 | **Geo Engine** *(elevated)* | was an implementation note in Rev 1 §8, now first-class (§14.8) |
| 14 | **Search Engine** *(new)* | address autocomplete, read-side of Geography (§14.9) |
| 15 | **Statistics** *(new)* | read-side/CQRS, Admin + Driver (§14.10) |
| 16 | **Payment** *(seam only, new)* | port reserved, zero implementation (§14.11) |

### 14.13 New Architecture Decision Records

| ADR | Decision | Why |
|---|---|---|
| 011 | Split `Advertisement` (listing) from `Trip` (realized journey) as two aggregates | Matches real-world semantics; isolates booking-time concurrency from execution-time state; gives Statistics/Rating an unambiguous "did this happen" record. |
| 012 | Queue Engine is an independent module behind `AbstractQueuePort`, consulted by (not merged into) Matching | Fairness policy changes far more often than distance/rating math — isolating it behind a port avoids destabilizing Matching every time fairness rules are tuned. |
| 013 | Admin actions are audited via a decorator wrapping admin use cases, not manual per-use-case logging calls | Audit completeness is a compliance requirement; structural enforcement beats relying on every future admin use case remembering to log itself. |
| 014 | Statistics is a read-only/CQRS-style module querying existing tables, not a new write-owning context | Reporting has fundamentally different (read-heavy, eventually-consistent-tolerant) needs than Booking/Trip; keeping it read-only prevents reporting concerns from leaking into transactional use cases. |
| 015 | Payment gets a port (`AbstractPaymentGateway`) and empty adapter packages only — no `Payment` aggregate yet | Explicit product instruction to prepare, not implement; avoids modeling a domain (money, refunds, provider webhooks) whose rules aren't specified yet — YAGNI with a seam left for when they are. |

---

## 15. Next Step

**Step 2 — Project Structure & Foundation** is approved with the amendments above and is being executed now: complete folder skeleton (reflecting the updated 16-context table), Python packages, `pyproject.toml` (uv), Ruff/Black/MyPy/pre-commit config, Docker assets, settings/logging/DI placeholders, and a runnable entrypoint. No business logic, services, repositories, database models, or handlers are created in this step.

See [`02-PROJECT-STRUCTURE.md`](02-PROJECT-STRUCTURE.md) for the directory-by-directory explanation once Step 2 completes.

**Step 3 — Database Design** (ER diagram, relationships, then SQLAlchemy models) follows after Step 2 is reviewed and approved.
