import json
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, Integer, String, Text, DateTime, event
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql.expression import text

Base = declarative_base()


class Event(Base):
    __tablename__ = "outbox"
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(36), default=uuid4)
    timestamp = Column(DateTime(timezone=True), server_default=text("now()"))
    event = Column(String(255), nullable=False)
    org = Column(String(255), nullable=False)
    payload = Column(Text)

    def as_dict(self):
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
            if c.name not in ["id"]
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.as_dict()})"


class Producer:
    def __init__(self, session: Any, org: str, outbox_topic: str = None):
        self.session = session
        self.org = org
        if outbox_topic:
            event.listens_for(session, "after_commit")(self._notify)

    def _notify(self, session):
        pass

    def emmit(self, event: str, payload: Any):
        self.session.add(Event(event=event, org=self.org, payload=json.dumps(payload)))
