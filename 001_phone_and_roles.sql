-- Run once: psql -d metro_trotro -f backend/migrations/001_phone_and_roles.sql
ALTER TABLE staff ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20) UNIQUE;  -- store as +233XXXXXXXXX
ALTER TABLE staff DROP CONSTRAINT IF EXISTS staff_role_check;
ALTER TABLE staff ADD CONSTRAINT staff_role_check
  CHECK (role IN ('station_manager', 'station_staff', 'driver', 'mate', 'commuter'));

-- Demo accounts (plain-text passwords are upgraded to hashes on first sign-in)
INSERT INTO staff (full_name, username, email, phone_number, password_hash, role, account_status) VALUES
 ('Demo Driver',    'demo_driver',   'driver@station.com',   '+233241000001', 'demo123', 'driver',   'active'),
 ('Demo Mate',      'demo_mate',     'mate@station.com',     '+233241000002', 'demo123', 'mate',     'active'),
 ('Demo Commuter',  'demo_commuter', 'commuter@station.com', '+233241000003', 'demo123', 'commuter', 'active')
ON CONFLICT DO NOTHING;
UPDATE staff SET phone_number = '+233241000000' WHERE email = 'demo@station.com' AND phone_number IS NULL;
