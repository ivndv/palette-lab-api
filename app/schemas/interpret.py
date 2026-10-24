from typing import Literal

from pydantic import BaseModel, Field, field_validator

Modo = Literal[
    "analogous",
    "complementary",
    "triadic",
    "monochrome",
    "random",
]

Tono = Literal[
    "balanced",
    "pastel",
    "vivid",
    "muted",
    "dark",
    "light",
]


class PeticionInterpretacion(BaseModel):
    prompt: str = Field(min_length=1)


class RespuestaInterpretacion(BaseModel):
    base: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    mode: Modo
    tone: Tono
    label: str | None = Field(default=None, max_length=60)

    @field_validator("base")
    @classmethod
    def normalizar_base(cls, value: str) -> str:
        return value.lower()
