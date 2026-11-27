# Metro Trotro v3: phone dashboard + driver registration requests

This folder holds every file that differs from the original GitHub project. It already includes
your group member's v2 changes (live map, security clean-up), so you do NOT need to copy v2 separately.

Commands are for Windows (Command Prompt). Mac/Linux differences are in brackets.

---------------------------------------------------------------------------------------------------
## Step 0. Have these installed
- Git, Python 3.11 or newer, Node.js 20 or newer, PostgreSQL (with `psql` working in the terminal)

Check:
    git --version
    python --version
    node --version
    psql --version

---------------------------------------------------------------------------------------------------
## Step 1. Make a new branch in your project
    cd path\to\Metro-trotro-Information-System
    git checkout main
    git pull
    git checkout -b phone-dashboard-driver-requests

---------------------------------------------------------------------------------------------------
## Step 2. Copy the new files into the project
Unzip metro-trotro-v3.zip somewhere (for example Downloads). Then copy everything INSIDE the
`metro-trotro-v3` folder into your project folder and choose "Replace" for every file.

Or from the project folder in PowerShell:
    Copy-Item -Recurse -Force "$HOME\Downloads\metro-trotro-v3\*" .
[Mac/Linux: cp -R ~/Downloads/metro-trotro-v3/. .]

Check that it worked:
    git status
You should see about 45 changed or new files, including
`backend/app/routers/driver_requests.py` and `staff_dashboard/src/pages/Requests.jsx`.

---------------------------------------------------------------------------------------------------
## Step 3. Take the secret `.env` file out of GitHub
The original repo has a `.env` committed. The new `.gitignore` stops future commits, but you must
remove the existing one from Git (the file stays on your computer):
    git rm --cached .env
Later, in Step 5, use a NEW `JWT_SECRET`, because the old one is public on GitHub.

---------------------------------------------------------------------------------------------------
## Step 4. Update the database
Choose ONE option.

Option A: start fresh (deletes all data, reloads the sample data). Easiest for a class demo.
    psql -U postgres -c "DROP DATABASE IF EXISTS metro_trotro"
    psql -U postgres -c "CREATE DATABASE metro_trotro ENCODING 'UTF8' TEMPLATE template0"
    psql -U postgres -d metro_trotro -f metro_trotro_db.sql

Option B: keep your existing data. Run both (safe to run more than once):
    psql -U postgres -d metro_trotro -f tracking_migration.sql
    psql -U postgres -d metro_trotro -f driver_requests_migration.sql

Check:
    psql -U postgres -d metro_trotro -c "SELECT request_id, full_name, request_status FROM driver_requests"
Option A shows two waiting sample requests (Kojo Antwi, Akosua Darko). Option B shows an empty table.

---------------------------------------------------------------------------------------------------
## Step 5. Set up and start the backend
    cd backend
    python -m venv venv
    venv\Scripts\activate                [Mac/Linux: source venv/bin/activate]
    pip install -r requirements.txt
    copy .env.example .env               [Mac/Linux: cp .env.example .env]

Make a new secret:
    python -c "import secrets; print(secrets.token_urlsafe(48))"

Open `backend\.env` and set:
- `DATABASE_URL` with your PostgreSQL password
- `JWT_SECRET` to the secret you just made

Start it:
    uvicorn app.main:app --reload --port 8000

Check: open http://localhost:8000/health (should say "ok") and http://localhost:8000/docs.
You should see a new section "Driver registration requests". Leave this terminal running.

---------------------------------------------------------------------------------------------------
## Step 6 (recommended). Run the automated tests
In a NEW terminal (the tests erase their database, so use a separate one):
    psql -U postgres -c "CREATE DATABASE metro_trotro_test ENCODING 'UTF8' TEMPLATE template0"
    cd backend
    venv\Scripts\activate
    set TEST_DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/metro_trotro_test
                                         [Mac/Linux: export TEST_DATABASE_URL=...]
    pytest
Expected result: `120 passed`.

---------------------------------------------------------------------------------------------------
## Step 7. Start the staff dashboard
In another NEW terminal:
    cd staff_dashboard
    npm install
    npm run dev
Open http://localhost:5173

To see the phone layout on your laptop: in Chrome press F12, then Ctrl+Shift+M, and pick a phone
such as "iPhone 12 Pro" or "Pixel 7".

(No backend? Demo mode works too: create `staff_dashboard\.env.local` containing
`VITE_USE_MOCK=true` and run `npm run dev` again. The driver request flow works in demo mode.)

---------------------------------------------------------------------------------------------------
## Step 8 (optional). Open it on a real phone
Phone and laptop must be on the same Wi-Fi.
1. Find your laptop's IP address: `ipconfig` (look for IPv4, for example 192.168.1.20) [Mac: ipconfig getifaddr en0]
2. In `backend\.env`, add the phone address to CORS_ORIGINS:
   `CORS_ORIGINS=http://localhost:5173,http://192.168.1.20:5173`
3. Start the backend so the phone can reach it:
   `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
4. Create `staff_dashboard\.env.local` containing `VITE_API_URL=http://192.168.1.20:8000`
5. Start the dashboard: `npm run dev -- --host`
6. On the phone open http://192.168.1.20:5173. In Chrome's menu choose "Add to Home screen" so it opens like an app.
If Windows asks about the firewall, allow access on private networks.

---------------------------------------------------------------------------------------------------
## Step 9. Try the full flow (use this as your demo for the lecturer)
1. On the sign-in page tap "Ask to be registered" (or open http://localhost:5173/driver-register).
2. As a driver: enter a name and phone, tick "I also want to register my vehicle", fill in plate,
   destination and seats, then tap "Send request".
3. Go back and sign in as the manager: demo@station.com / demo123.
4. The Requests tab at the bottom shows a red number. Open it, then Approve one request and Reject another with a reason.
5. Vehicles tab: the approved driver's vehicle is there with the driver. "+ Add a vehicle" now only
   lets you choose registered drivers.
6. Back on the driver page, "Check your request" with the rejected phone number shows the reason.
7. Sign in as normal staff (ama@station.com / staff123): there is no Requests tab, because only the manager approves drivers.

---------------------------------------------------------------------------------------------------
## Step 10. Commit and push
    git add -A
    git status          (make sure .env is NOT listed, and node_modules / venv are not either)
    git commit -m "Phone layout for staff dashboard; drivers request registration, manager approves"
    git push -u origin phone-dashboard-driver-requests
Then open a Pull Request on GitHub so your group can review it before merging into main.

---------------------------------------------------------------------------------------------------
## Step 11. Update the analysis documents (lecturer marks these too)
- Use case diagram: add the actor **Driver** with "Submit registration request" and "Check request status".
  Give **Station Manager** "Review driver requests", "Approve request" and "Reject request".
  Remove "Add driver" from the manager.
- ERD: add the entity **DRIVER_REQUEST** (request_id, full_name, phone_number, registration_number,
  destination, capacity, request_status, reject_reason, submitted_at, reviewed_at).
  Relationships: STAFF 1 to many DRIVER_REQUEST (reviews), DRIVER_REQUEST 0..1 to 1 DRIVER (creates),
  DRIVER_REQUEST 0..1 to 1 VEHICLE (creates), STATION 1 to many DRIVER_REQUEST.
- DFD: new data store "D: Driver requests". Driver sends request details to "Register driver" process;
  the process sends pending requests to the Station Manager; the manager's decision updates Drivers and Vehicles.
- Activity or sequence diagram: Driver submits, request is pending, manager approves (driver + vehicle created)
  or rejects (reason stored), driver checks status.
- Requirements: "The staff dashboard shall be usable on a mobile phone" and
  "A driver shall only be registered after a station manager approves their request".

---------------------------------------------------------------------------------------------------
## What changed, in short
Phone version of the dashboard
- Removed the 85% zoom. The layout is designed for phones first.
- Bottom tab bar (Queue, Vehicles, Trips, Map, Requests) and a green top bar with the page name.
- Tables replaced by cards. The queue shows one big "Record departure" button per vehicle, with less
  common actions under "More". Seats change with large minus and plus buttons.
- Large touch targets (48px), 16px text in fields (stops phones zooming in), the map fits the screen.

Driver registration requests
- New table `driver_requests` and new API endpoints under `/driver/requests`.
- Public page `/driver-register` for drivers: send a request and check its status.
- Requests tab for the station manager with a waiting count, Approve and Reject (with reason).
- Drivers can no longer be typed in or added directly by staff (POST /drivers was removed and
  "Add vehicle" picks from registered drivers). This undoes part of v2 on purpose, to match the lecturer's flow.
- 15 new automated tests; 120 tests pass in total.
