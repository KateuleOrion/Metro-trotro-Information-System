-- Run this ONCE on an existing database (after mate_accounts_migration.sql).
-- Drivers now log in like mates and managers. Safe to run twice; keeps all data.
--
--   psql -U postgres -d metro_trotro -f driver_accounts_migration.sql

ALTER TABLE staff DROP CONSTRAINT IF EXISTS staff_role_check;
ALTER TABLE staff ADD CONSTRAINT staff_role_check
    CHECK (role IN ('station_manager', 'station_staff', 'mate', 'driver'));

ALTER TABLE drivers ADD COLUMN IF NOT EXISTS account_id INTEGER
    REFERENCES staff(staff_id) ON UPDATE CASCADE ON DELETE SET NULL;
CREATE UNIQUE INDEX IF NOT EXISTS drivers_account_id_key ON drivers(account_id);

ALTER TABLE driver_requests ADD COLUMN IF NOT EXISTS account_id INTEGER
    REFERENCES staff(staff_id) ON UPDATE CASCADE ON DELETE SET NULL;
ALTER TABLE driver_requests ADD COLUMN IF NOT EXISTS existing_driver_id INTEGER
    REFERENCES drivers(driver_id) ON UPDATE CASCADE ON DELETE SET NULL;

-- Demo driver login: 0240000001 / driver123 (Kwame Asare), if he has no login yet.
INSERT INTO staff (full_name, phone_number, password_hash, role, account_status)
SELECT 'Kwame Asare', '0240000001', 'driver123', 'driver', 'active'
WHERE EXISTS (SELECT 1 FROM drivers WHERE phone_number = '0240000001' AND account_id IS NULL)
  AND NOT EXISTS (SELECT 1 FROM staff WHERE phone_number = '0240000001');
UPDATE drivers d SET account_id = s.staff_id
FROM staff s
WHERE d.phone_number = '0240000001' AND d.account_id IS NULL
  AND s.phone_number = '0240000001' AND s.role = 'driver';
