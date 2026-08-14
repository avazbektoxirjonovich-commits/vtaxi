# scripts/

One-off developer scripts that are not part of the application package: database seeding, data backfills, ad-hoc reports. Nothing here is imported by `src/vtaxi/`; scripts call the same public use cases the bot/API would call, never the ORM directly.
