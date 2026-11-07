"""Base declarativa y registro de todos los modelos."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


def load_models() -> None:
    """Importa todos los módulos con modelos para poblar `Base.metadata`.

    Se llama desde Alembic y scripts de demo, nunca durante un import de módulo,
    para evitar ciclos.
    """
    from app.jobs import models as _jobs  # noqa: F401
    from app.modules.alerts import models as _alerts  # noqa: F401
    from app.modules.audit import models as _audit  # noqa: F401
    from app.modules.business import models as _business  # noqa: F401
    from app.modules.classification import models as _classification  # noqa: F401
    from app.modules.commitments import models as _commitments  # noqa: F401
    from app.modules.consents import models as _consents  # noqa: F401
    from app.modules.demo import models as _demo  # noqa: F401
    from app.modules.identity import models as _identity  # noqa: F401
    from app.modules.insights import models as _insights  # noqa: F401
    from app.modules.ledger import models as _ledger  # noqa: F401
    from app.modules.messaging import models as _messaging  # noqa: F401
    from app.modules.opportunities import models as _opportunities  # noqa: F401
