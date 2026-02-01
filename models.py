# from sqlalchemy.dialects.postgresql import TEXT
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    name : str = Field(sa_column=Column(Text, index=True))
    fb_id: str = Field(sa_column=Column(Text, unique=True, index=True))
    tg_id: str = Field(sa_column=Column(Text, unique=True, index=True, ))
    platform: str = Field(sa_column=Column(Text, index=True))
    languages: str = Field(sa_column=Column(Text, index=True))
    # created_at: datetime = Field(default_factory=datetime.utcnow)