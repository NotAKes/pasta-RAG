"""Public request contracts; client-provided prices are never authoritative."""

from pydantic import BaseModel, Field, field_validator


class OrderItemRequest(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    quantity: int = Field(strict=True, ge=1, le=20)


class OrderRequest(BaseModel):
    user_id: int | None = None  # Compatibility hint, never trusted as authentication.
    name: str = Field(default="Guest", max_length=120)
    phone: str = Field(min_length=1, max_length=200)
    table: str = Field(min_length=1, max_length=200)
    items: list[OrderItemRequest] = Field(min_length=1, max_length=50)

    @field_validator("phone", "table")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Must not be blank")
        return value
