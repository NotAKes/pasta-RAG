from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name : str = Field(index=True)
    tg_id: str = Field(unique=True, index=True)
    fb_id: str = Field(unique=True, index=True)
    platform: str = Field(index=True)
    languages: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)