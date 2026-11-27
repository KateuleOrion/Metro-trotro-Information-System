
"""Passenger booking operations.

Passenger identity must come from verified authentication,
not directly from an untrusted request.
"""
from uuid import uuid4

from .errors import ApiError
from .services import active_entry, audit, get_vehicle


def create_booking(conn, passenger_subject: str, vehicle_id: int, seats: int) -> dict:
    """Reserve seats safely and record the updated availability."""

    if not passenger_subject:
        raise ApiError(401, "Passenger authentication is required")

    if seats < 1:
        raise ApiError(422, "You must book at least one seat")

    # Lock the vehicle so bookings, staff seat updates and departures
    # cannot modify it simultaneously.
    vehicle = get_vehicle(conn, vehicle_id, lock=True)

    if vehicle["vehicle_status"] not in ("queued", "loading"):
        raise ApiError(409, "This vehicle is not accepting bookings")

    entry = active_entry(conn, vehicle_id, lock=True)
    if not entry:
        raise ApiError(409, "This vehicle is no longer in the queue")

    latest = conn.execute(
        """
        SELECT available_seats
        FROM seat_availability
        WHERE vehicle_id = %s
        ORDER BY last_updated DESC, seat_record_id DESC
        LIMIT 1
        """,
        (vehicle_id,),
    ).fetchone()

    available = latest["available_seats"] if latest else 0

    if available < seats:
        raise ApiError(
            409,
            f"Only {available} seat(s) are currently available"
        )

    reference = "MT-" + uuid4().hex[:12].upper()

    booking = conn.execute(
        """
        INSERT INTO bookings
            (booking_reference, passenger_subject, vehicle_id, seats_booked)
        VALUES (%s, %s, %s, %s)
        RETURNING booking_id, booking_reference, vehicle_id,
                  seats_booked, booking_status, booking_time
        """,
        (reference, passenger_subject, vehicle_id, seats),
    ).fetchone()

    # Record the new seat count. Do not overwrite the historical record.
    conn.execute(
        """
        INSERT INTO seat_availability
            (vehicle_id, available_seats, recorded_by)
        VALUES (%s, %s, NULL)
        """,
        (vehicle_id, available - seats),
    )

    audit(
        conn,
        None,
        "PASSENGER_BOOKING_CREATED",
        "bookings",
        booking["booking_id"],
        {"vehicle_id": vehicle_id, "seats_booked": seats},
    )

    return {
        **booking,
        "available_seats": available - seats,
    }



def cancel_booking(conn, passenger_subject: str, booking_reference: str) -> dict:
    """Cancel a passenger's booking and restore the reserved seats."""

    if not passenger_subject:
        raise ApiError(401, "Passenger authentication is required")

    # First, find the vehicle without locking the booking.
    preliminary = conn.execute(
        """
        SELECT vehicle_id
        FROM bookings
        WHERE booking_reference = %s
          AND passenger_subject = %s
        """,
        (booking_reference, passenger_subject),
    ).fetchone()

    if not preliminary:
        raise ApiError(404, "Booking not found")

    # Lock the vehicle first to maintain a consistent lock order.
    vehicle = get_vehicle(conn, preliminary["vehicle_id"], lock=True)

    # Now lock and verify the passenger's booking.
    booking = conn.execute(
        """
        SELECT *
        FROM bookings
        WHERE booking_reference = %s
          AND passenger_subject = %s
        FOR UPDATE
        """,
        (booking_reference, passenger_subject),
    ).fetchone()

    if not booking:
        raise ApiError(404, "Booking not found")

    if booking["booking_status"] != "confirmed":
        raise ApiError(409, "This booking is no longer active")

    if vehicle["vehicle_status"] == "departed":
        raise ApiError(409, "This vehicle has already departed")

    latest = conn.execute(
        """
        SELECT available_seats
        FROM seat_availability
        WHERE vehicle_id = %s
        ORDER BY last_updated DESC, seat_record_id DESC
        LIMIT 1
        """,
        (booking["vehicle_id"],),
    ).fetchone()

    if not latest:
        raise ApiError(409, "Seat availability could not be verified")

    restored = latest["available_seats"] + booking["seats_booked"]

    if restored > vehicle["capacity"]:
        raise ApiError(409, "Cancellation would exceed vehicle capacity")

    conn.execute(
        """
        UPDATE bookings
        SET booking_status = 'cancelled',
            cancelled_at = CURRENT_TIMESTAMP
        WHERE booking_id = %s
        """,
        (booking["booking_id"],),
    )

    conn.execute(
        """
        INSERT INTO seat_availability
            (vehicle_id, available_seats, recorded_by)
        VALUES (%s, %s, NULL)
        """,
        (booking["vehicle_id"], restored),
    )

    audit(
        conn,
        None,
        "PASSENGER_BOOKING_CANCELLED",
        "bookings",
        booking["booking_id"],
        {"seats_restored": booking["seats_booked"]},
    )

    return {
        "booking_reference": booking_reference,
        "booking_status": "cancelled",
        "seats_restored": booking["seats_booked"],
        "available_seats": restored,
    }