"""Unidad de trabajo simple sobre una sesión SQLAlchemy."""

from __future__ import annotations

from types import TracebackType
from typing import Literal

from sqlalchemy.orm import Session


class UnitOfWork:
    """Context manager que confirma o revierte una sesión existente."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Session:
        return self.session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        if exc_type is not None:
            self.session.rollback()
        else:
            self.session.commit()
        return False
