-- Run this ONCE on an existing database (after staff_accounts_migration.sql).
-- It adds the 'mate' account type and a demo mate. Safe to run twice; keeps all data.
--
--   psql -U postgres -d metro_trotro -f mate_accounts_migration.sql

ALTER TABLE staff DROP CONSTRAINT IF EXISTS staff_role_check;
ALTER TABLE staff ADD CONSTRAINT staff_role_check
    CHECK (role IN ('station_manager', 'station_staff', 'mate'));

-- Demo mate: log in with 0200000004 / mate123
INSERT INTO staff (full_name, phone_number, password_hash, role, account_status)
SELECT 'Kofi Boateng', '0200000004', 'mate123', 'mate', 'active'
WHERE NOT EXISTS (SELECT 1 FROM staff WHERE phone_number = '0200000004');
