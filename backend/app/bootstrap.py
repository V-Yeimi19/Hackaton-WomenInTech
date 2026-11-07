"""Composición y arranque operativo.

La creación de tablas se hace **solo** con Alembic; la aplicación no improvisa
tablas al iniciar. Este módulo ofrece comandos de arranque reproducibles para
Docker Compose y para desarrollo local.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import get_settings

BASE_DIR = Path(__file__).resolve().parent.parent
settings = get_settings()


def alembic_config() -> Config:
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def run_migrations(revision: str = "head") -> None:
    command.upgrade(alembic_config(), revision)


def check_database() -> bool:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Arranque de Mica")
    parser.add_argument(
        "command",
        choices=["upgrade", "check"],
        nargs="?",
        default="upgrade",
        help="upgrade: aplica migraciones; check: verifica la BD",
    )
    parser.add_argument("--revision", default="head")
    args = parser.parse_args()

    if args.command == "check":
        print("database: ok" if check_database() else "database: unavailable")
        return

    run_migrations(args.revision)
    print(f"migraciones aplicadas: {args.revision}")


if __name__ == "__main__":
    main()
