-- Adjust to match the database developer's tables.
-- Only the sync-related parts are essential.

CREATE TABLE IF NOT EXISTS stations (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS routes (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS vehicles (
  id SERIAL PRIMARY KEY,
  plate_number TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS departures (
  id SERIAL PRIMARY KEY,
  route_id INT REFERENCES routes(id),
  station_id INT REFERENCES stations(id),
  vehicle_id INT REFERENCES vehicles(id),
  departure_time TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS staff (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL
);

-- Records uploaded from offline devices.
-- client_uuid UNIQUE is what prevents duplicates.
CREATE TABLE IF NOT EXISTS vehicle_arrivals (
  id SERIAL PRIMARY KEY,
  client_uuid UUID UNIQUE NOT NULL,
  device_id TEXT NOT NULL,
  station_id INT NOT NULL REFERENCES stations(id),
  vehicle_id INT NOT NULL REFERENCES vehicles(id),
  staff_id INT NOT NULL REFERENCES staff(id),
  recorded_at TIMESTAMPTZ NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
