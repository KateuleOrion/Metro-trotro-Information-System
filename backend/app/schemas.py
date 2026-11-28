"""Shapes of the data the API accepts. Invalid input is rejected with a readable message."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

VehicleStatus = Literal["available", "queued", "loading", "departed", "unavailable"]


class Base(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class LoginIn(Base):
    """Sign in with the phone number the account was registered with, or its email.
    `login` holds either one. (`email` is still accepted from older clients.)"""
    login: Optional[str] = Field(default=None, min_length=3, max_length=255)
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=72)

    @model_validator(mode="after")
    def need_login(self):
        if not (self.login or self.email):
            raise ValueError("Please enter your phone number or email")
        return self


PHONE_PATTERN = r"^\+?[0-9][0-9 -]{6,19}$"
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(Base):
    """A new station staff, station manager or mate (conductor) account. Give a phone number, or an
    email instead; at least one is needed."""
    full_name: str = Field(min_length=2, max_length=100)
    role: Literal["station_staff", "station_manager", "mate"]
    phone_number: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)
    email: Optional[str] = Field(default=None, max_length=255, pattern=EMAIL_PATTERN)
    password: str = Field(min_length=8, max_length=72)

    @model_validator(mode="after")
    def phone_or_email(self):
        if not (self.phone_number or self.email):
            raise ValueError("Please enter a phone number, or an email instead")
        return self


class VehicleCreate(Base):
    """A vehicle. The route is given by route_id, or by typing a destination (an existing route to
    the same destination is reused). The driver must already be registered: give their driver_id.
    New drivers are added only by approving a driver registration request (/driver/requests).
    All of it is saved in one step: if anything fails, nothing is saved."""
    registration_number: str = Field(min_length=1, max_length=20)
    route_id: Optional[int] = None
    destination: Optional[str] = Field(default=None, min_length=1, max_length=100)
    capacity: int = Field(ge=1, le=100)
    driver_id: Optional[int] = None
    # Kept only to give a clear message to old clients: typing a new driver here is no longer allowed.
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    available_seats: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def route_is_required(self):
        if self.route_id is None and not self.destination:
            raise ValueError("Give a route_id or a destination")
        if self.driver_name or self.driver_phone:
            raise ValueError("New drivers must send a registration request. Choose a registered driver by driver_id")
        return self


class VehicleUpdate(Base):
    vehicle_status: Optional[VehicleStatus] = None
    driver_id: Optional[int] = None
    route_id: Optional[int] = None
    available_seats: Optional[int] = Field(default=None, ge=0)


class SeatChange(Base):
    """How many passengers a mate is booking onto, or taking off, a vehicle."""
    count: int = Field(default=1, ge=1, le=100)


class VehicleRef(Base):
    vehicle_id: int


class QueueOrderIn(Base):
    vehicle_ids: list[int] = Field(max_length=400)
    station_id: Optional[int] = None


class DriverRequestIn(Base):
    """A driver's request to be registered. The vehicle details are optional, but if one of
    registration_number, destination or capacity is given, all three are needed."""
    full_name: str = Field(min_length=2, max_length=100)
    phone_number: str = Field(pattern=r"^[0-9+ ]{7,20}$")
    registration_number: Optional[str] = Field(default=None, min_length=1, max_length=20)
    destination: Optional[str] = Field(default=None, min_length=1, max_length=100)
    capacity: Optional[int] = Field(default=None, ge=1, le=100)

    @model_validator(mode="after")
    def vehicle_details_together(self):
        given = [self.registration_number, self.destination, self.capacity]
        if any(x is not None for x in given) and not all(x is not None for x in given):
            raise ValueError("To register a vehicle, give its registration number, destination and number of seats")
        return self


class RejectIn(Base):
    reason: Optional[str] = Field(default=None, max_length=255)


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


class PositionIn(Base):
    """One location report for a vehicle (for example from the driver's phone)."""
    vehicle_id: int
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_kmh: Optional[float] = Field(default=None, ge=0, le=200)
    recorded_at: Optional[datetime] = None


class LocationIn(Base):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
