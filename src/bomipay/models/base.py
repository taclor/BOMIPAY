from datetime import datetime

from sqlalchemy import Column, DateTime, func


class TimestampMixin:
    # Python-side defaults ensure ORM-created objects use local time, which
    # keeps datetime comparisons consistent regardless of the DB dialect's
    # interpretation of CURRENT_TIMESTAMP.
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=datetime.now,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=datetime.now,
        nullable=False,
    )
