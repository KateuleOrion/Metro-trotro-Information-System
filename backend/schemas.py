"""Shapes of the data the API accepts. Invalid input is rejected with a readable message."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

VehicleStatus = Literal["available", "queued", "loading", "departed", "unavailable"]


class Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class LoginIn(Base):
    """Sign in with a phone number or an email, plus a password.
    `role` is the role chosen on the menu; when given, the account must have that role."""
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    phone: Optional[str] = Field(default=None, min_length=7, max_length=20)
    password: str = Field(min_length=1, max_length=72)
    role: Optional[Literal["driver", "mate", "commuter", "station_manager"]] = None

    @model_validator(mode="after")
    def _need_phone_or_email(self):
        if not self.email and not self.phone:
            raise ValueError("Enter a phone number or an email")
        return self


class VehicleCreate(Base):
    registration_number: str = Field(min_length=1, max_length=20)
    route_id: int
    capacity: int = Field(ge=1, le=100)
    driver_id: Optional[int] = None
    available_seats: Optional[int] = Field(default=None, ge=0)


class VehicleUpdate(Base):
    vehicle_status: Optional[VehicleStatus] = None
    driver_id: Optional[int] = None
    route_id: Optional[int] = None
    available_seats: Optional[int] = Field(default=None, ge=0)


class VehicleRef(Base):
    vehicle_id: int


class QueueOrderIn(Base):
    vehicle_ids: list[int] = Field(max_length=400)
    station_id: Optional[int] = None


class DriverCreate(Base):
    driver_name: str = Field(min_length=1, max_length=100)
    phone_number: Optional[str] = Field(default=None, pattern=r"^[0-9+ ]{7,20}$")


class RouteCreate(Base):
    destination: str = Field(min_length=1, max_length=100)
    origin: Optional[str] = Field(default=None, min_length=1, max_length=100)
    route_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    station_id: Optional[int] = None


class SyncRecord(Base):
    client_uuid: UUID
    type: Literal["vehicle_arrival", "vehicle_departure", "queue_update"]
    station_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    recorded_at: datetime
    payload: dict = Field(default_factory=dict)


class SyncBatchIn(Base):
    device_id: str = Field(min_length=1, max_length=100)
    records: list[dict] = Field(max_length=500)
