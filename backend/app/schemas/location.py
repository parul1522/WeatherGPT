"""Location schema shared by every endpoint that returns a place."""

from typing import Annotated

from pydantic import BaseModel, Field

Latitude = Annotated[float, Field(ge=-90, le=90, description="Latitude in degrees (-90 to 90)")]
Longitude = Annotated[float, Field(ge=-180, le=180, description="Longitude in degrees (-180 to 180)")]


class Location(BaseModel):
    name: str | None = Field(default=None, examples=["Bhopal"])
    latitude: Latitude = Field(examples=[23.2599])
    longitude: Longitude = Field(examples=[77.4126])
    country: str | None = Field(default=None, examples=["India"])
    state: str | None = Field(default=None, examples=["Madhya Pradesh"])
