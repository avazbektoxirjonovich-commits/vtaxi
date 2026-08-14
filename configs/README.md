# configs/

Static, non-secret configuration assets loaded at runtime by `src/vtaxi/config/`. Today this holds `logging.yaml` (the `logging.config.dictConfig` definition applied by `src/vtaxi/config/logging.py`). Secrets and per-environment values stay in `.env` — nothing here should ever contain a credential.
