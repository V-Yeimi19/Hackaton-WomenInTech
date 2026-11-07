"""CLI de fixtures sintéticas para la demo.

Uso:
    python -m app.modules.demo.seed --scenario risk

Requiere migraciones aplicadas. Imprime el token de sesión y el CSRF; no se
vuelven a mostrar.
"""

from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal
from app.modules.demo.service import seed_scenario
from app.modules.identity.service import create_demo_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea una sesión demo aislada")
    parser.add_argument("--scenario", choices=["empty", "risk", "stable"], default="risk")
    parser.add_argument("--name", default="Rosa Demo")
    parser.add_argument("--phone", default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user, session, token, csrf = create_demo_session(db, args.name)
        business = seed_scenario(db, user, args.scenario, phone=args.phone)
        print(
            json.dumps(
                {
                    "session_token": token,
                    "csrf_token": csrf,
                    "expires_at": session.expires_at.isoformat(),
                    "user_id": str(user.id),
                    "business_id": str(business.id) if business else None,
                    "environment": "DEMO",
                    "scenario": args.scenario,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
