-- Run this ONCE on a database you already created from an older metro_trotro_db.sql.
-- It lets staff register and sign in with a phone number, keeps all existing data,
-- and is safe to run twice.
-- (A brand-new database made from the updated metro_trotro_db.sql already has this.)
--
--   psql -U postgres -d metro_trotro -f staff_accounts_migration.sql

ALTER TABLE staff ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20);
ALTER TABLE staff ADD COLUMN IF NOT EXISTS reject_reason VARCHAR(255);
ALTER TABLE staff ADD COLUMN IF NOT EXISTS reviewed_by INTEGER
    REFERENCES staff(staff_id) ON UPDATE CASCADE ON DELETE SET NULL;
ALTER TABLE staff ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;

-- Email and username are optional now (someone can register with only a phone number).
ALTER TABLE staff ALTER COLUMN email DROP NOT NULL;
ALTER TABLE staff ALTER COLUMN username DROP NOT NULL;

-- New account states: 'pending' (waiting for approval) and 'rejected'.
ALTER TABLE staff DROP CONSTRAINT IF EXISTS staff_account_status_check;
ALTER TABLE staff ADD CONSTRAINT staff_account_status_check
    CHECK (account_status IN ('pending', 'active', 'inactive', 'locked', 'rejected'));

ALTER TABLE staff DROP CONSTRAINT IF EXISTS staff_phone_or_email;
ALTER TABLE staff ADD CONSTRAINT staff_phone_or_email CHECK (phone_number IS NOT NULL OR email IS NOT NULL);

CREATE UNIQUE INDEX IF NOT EXISTS staff_phone_number_key ON staff(phone_number);

-- Give the two demo accounts phone numbers, if they exist and have none yet.
UPDATE staff SET phone_number = '0200000001' WHERE email = 'demo@station.com' AND phone_number IS NULL;
UPDATE staff SET phone_number = '0200000002' WHERE email = 'ama@station.com' AND phone_number IS NULL;
