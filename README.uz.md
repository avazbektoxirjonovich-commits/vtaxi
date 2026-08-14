# VTaxi

**Shaharlararo taksi xizmati uchun Clean Architecture / DDD backend — arxitektura namunasi sifatida nashr qilingan, tugallangan mahsulot emas.**

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Aiogram](https://img.shields.io/badge/Aiogram-3-2CA5E0)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%20async-D71F00)
![Testlar](https://img.shields.io/badge/testlar-6%20o'tdi-brightgreen)
![Litsenziya](https://img.shields.io/badge/litsenziya-proprietary-lightgrey)

[English](README.md) | [O'zbek](README.uz.md)

> **Halol holat:** domen va application qatlamlari bir nechta bounded context uchun sezilarli darajada amalga oshirilgan — booking to'liq holat mashinasiga ega, identity/trip/vehicle'da real xizmatlar bor — lekin Telegram bot, API va admin panel taqdimot qatlamlari hali ulanmagan (routers/keyboards/middlewares/states faqat bo'sh paketlar sifatida mavjud). Bu repo arxitektura va domen modellashtirish ishini ko'rsatadi, ishlaydigan botni emas.

## Tavsif

VTaxi — Telegram asosidagi shaharlararo taksi buyurtma backend'i (Namangan ⇄ Toshkentdan boshlab), Clean Architecture va Domain-Driven Design asosida qurilgan, shunday qilib yangi shahar juftligi qo'shish qayta yozish emas, ma'lumot o'zgarishi bo'ladi.

## Nima amalga oshirilgan, nima yo'q

| Qatlam | Holat |
|---|---|
| `domain/booking`, `application/booking` (booking_service.py, 620 qator) | **Amalga oshirilgan** — to'liq booking holat mashinasi |
| `domain/identity`, `application/identity` | **Amalga oshirilgan** |
| `domain/trip`, `application/trip` | **Amalga oshirilgan** |
| `domain/vehicle`, `application/vehicle` | **Amalga oshirilgan** |
| `application/payment`, `application/matching` va boshqalar | **Faqat qoraqamma** — paket bor, logika yo'q |
| `presentation/bot` (routers, keyboards, middlewares, states) | **Amalga oshirilmagan** — bo'sh paketlar |
| `presentation/api`, `presentation/admin_panel` | **Amalga oshirilmagan** — bo'sh paketlar |
| Ma'lumotlar bazasi asosi | **Amalga oshirilgan va sinovdan o'tgan** — SQLAlchemy 2.0 async, Alembic (1 migratsiya) |

## Arxitektura

[docs/architecture/clean-architecture.svg](docs/architecture/clean-architecture.svg), [docs/architecture/bounded-contexts.svg](docs/architecture/bounded-contexts.svg), [docs/architecture/booking-state-machine.svg](docs/architecture/booking-state-machine.svg) va [docs/architecture/database-er.svg](docs/architecture/database-er.svg) ga qarang.

```
presentation/  (bot, API, admin — hali ulanmagan)
      ↓
application/   (xizmatlar, Protocol-asoslangan portlar) — booking/identity/trip/vehicle amalga oshirilgan
      ↓
domain/        (entitilar, xatoliklar, har bir bounded context uchun)
      ↓
infrastructure/ (SQLAlchemy modellari, repository'lar, Unit-of-Work)
      ↓
PostgreSQL (async, asyncpg orqali)
```

## Testlar

Hozircha 6 ta test o'tadi (`tests/unit/infrastructure/test_database_foundation.py`), baza asosini qamrab oladi. `tests/{unit,integration,e2e}` boshqa joyda faqat qoraqamma, bo'sh — bu loyihaning production-ready deb atalishidan oldingi eng aniq bo'shliq.

```bash
uv run pytest tests/ -q
```

## O'rnatish

```powershell
uv sync
Copy-Item .env.example .env
uv run python -m vtaxi
```

`VTaxi initialized successfully` ko'rinishi kerak — skelet ishga tushadi, lekin hali bot, API yoki handler logikasi ulanmagan.

## Roadmap

- [ ] Telegram bot taqdimot qatlamini mavjud application xizmatlariga ulash
- [ ] `payment` va `matching` application logikasini amalga oshirish
- [ ] Test qamrovini baza asosidan tashqariga kengaytirish

## Litsenziya

Proprietary — qarang [LICENSE](LICENSE). Bu repo portfolio/arxitektura namunasi sifatida nashr qilingan; litsenziya shartlari loyihaning asl tijorat niyatini aks ettiradi va bu nashr uchun o'zgartirilmagan.
