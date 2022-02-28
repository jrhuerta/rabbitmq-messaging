from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, Text, null
from typing import Any
from uuid import uuid4

Base = declarative_base()


class Event(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(36), default=uuid4)
    event_name = Column(String(255), nullable=False)
    org = Column(String(255), nullable=False)
    payload = Column(Text)


class Producer:
    def __init__(self, session: Any, org: str):
        self.session = session
        self.org = org

    def emmit(self, event: Event):
        self.session.add(event)
