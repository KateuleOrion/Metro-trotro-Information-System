"""Tests for staff registration (phone number, or email instead), phone-number login, and the
station manager approving new accounts.

Sample data: manager demo@station.com / 0200000001 (demo123), staff ama@station.com / 0200000002
(staff123), and Kwesi Owusu 0200000003 (staff456), station staff waiting for approval.
"""
import pytest

from app import config


def register(client, **changes):
    body = {"full_name": "Esi Mensah", "role": "station_staff", "phone_number": "0244111222",
            "password": "secret123", **changes}
    return client.post("/auth/register", json=body)


def login(client, who, password):
    return client.post("/auth/login", json={"login": who, "password": password})


# ------------------------------------------------------------------ logging in with a phone number
def test_existing_users_log_in_with_their_phone_number(client):
    r = login(client, "0200000001", "demo123")
    assert r.status_code == 200 and r.json()["role"] == "station_manager"
    assert login(client, "0200000002", "staff123").json()["role"] == "station_staff"


def test_phone_number_can_be_written_in_different_ways(client):
    for written in ["+233 20 000 0001", "233200000001", "020-000-0001", " 020 000 0001 "]:
        assert login(client, written, "demo123").status_code == 200, written


def test_email_login_still_works(client):
    assert login(client, "DEMO@station.com", "demo123").status_code == 200
    # older clients that send {"email": ...}
    assert client.post("/auth/login", json={"email": "demo@station.com", "password": "demo123"}).status_code == 200


def test_wrong_phone_or_password(client):
    assert login(client, "0200000001", "wrong").status_code == 401
    r = login(client, "0299999999", "demo123")
    assert r.status_code == 401 and r.json()["detail"] == "Wrong phone number, email or password"
    assert client.post("/auth/login", json={"password": "x"}).status_code == 422


def test_repeated_wrong_phone_logins_are_slowed_down(client):
    for _ in range(config.LOGIN_MAX_FAILURES):
        login(client, "0200000002", "bad")
    assert login(client, "0200000002", "staff123").status_code == 429


# ------------------------------------------------------------------ registering
def test_register_with_phone_waits_for_approval(client, db):
    r = register(client)
    assert r.status_code == 201, r.text
    assert r.json()["account_status"] == "pending" and "token" not in r.json()
    row = db.execute("SELECT * FROM staff WHERE phone_number = '0244111222'").fetchone()
    assert row["password_hash"].startswith("$2") and row["email"] is None   # password is hashed
    r = login(client, "0244111222", "secret123")
    assert r.status_code == 403 and "waiting for the station manager" in r.json()["detail"]


def test_register_with_email_instead_of_phone(client, manager):
    r = register(client, phone_number=None, email="Esi@Example.com")
    assert r.status_code == 201
    client.post(f"/staff/accounts/{r.json()['staff_id']}/approve", headers=manager)
    assert login(client, "esi@example.com", "secret123").status_code == 200


def test_phone_or_email_is_needed(client):
    r = register(client, phone_number=None)
    assert r.status_code == 422 and "phone number, or an email" in r.json()["detail"]


@pytest.mark.parametrize("changes", [
    {"password": "short"}, {"phone_number": "abc"}, {"email": "not-an-email", "phone_number": None},
    {"full_name": "A"}, {"role": "passenger"},
])
def test_bad_registration_details_are_rejected(client, changes):
    assert register(client, **changes).status_code == 422


def test_same_phone_or_email_cannot_register_twice(client):
    assert register(client).status_code == 201
    r = register(client, phone_number="+233 24 411 1222")          # same number written differently
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    assert register(client, phone_number=None, email="demo@station.com").status_code == 409


def test_without_approval_setting_the_account_works_straight_away(client, monkeypatch):
    monkeypatch.setattr(config, "STAFF_SIGNUP_NEEDS_APPROVAL", False)
    r = register(client)
    assert r.status_code == 201 and r.json()["account_status"] == "active" and r.json()["token"]
    assert login(client, "0244111222", "secret123").status_code == 200


# ------------------------------------------------------------------ manager approves or rejects
def test_only_manager_reviews_accounts(client, staff):
    assert client.get("/staff/accounts").status_code == 401
    assert client.get("/staff/accounts", headers=staff).status_code == 403
    assert client.post("/staff/accounts/3/approve", headers=staff).status_code == 403


def test_manager_sees_waiting_accounts(client, manager):
    r = client.get("/staff/accounts", headers=manager)
    assert r.status_code == 200
    names = [a["full_name"] for a in r.json()]
    assert names == ["Kwesi Owusu"]
    assert "password_hash" not in r.json()[0]


def test_approved_account_can_log_in_and_use_the_dashboard(client, manager):
    r = client.post("/staff/accounts/3/approve", headers=manager)
    assert r.status_code == 200 and r.json()["account_status"] == "active"
    assert r.json()["reviewed_by_name"] == "Demo Station Manager"
    token = login(client, "0200000003", "staff456").json()["token"]
    assert client.get("/queue", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/trips", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_rejected_account_cannot_log_in(client, manager):
    r = client.post("/staff/accounts/3/reject", headers=manager, json={"reason": "Not working at this station"})
    assert r.status_code == 200 and r.json()["reject_reason"] == "Not working at this station"
    r = login(client, "0200000003", "staff456")
    assert r.status_code == 403 and "not approved" in r.json()["detail"]


def test_an_account_is_reviewed_only_once(client, manager):
    assert client.post("/staff/accounts/3/approve", headers=manager).status_code == 200
    assert client.post("/staff/accounts/3/reject", headers=manager, json={}).status_code == 409
    assert client.post("/staff/accounts/1/approve", headers=manager).status_code == 409   # already active
    assert client.post("/staff/accounts/999/approve", headers=manager).status_code == 404


def test_new_manager_gets_manager_rights_after_approval(client, manager):
    sid = register(client, role="station_manager", phone_number="0244999888").json()["staff_id"]
    client.post(f"/staff/accounts/{sid}/approve", headers=manager)
    token = login(client, "0244999888", "secret123").json()["token"]
    assert client.get("/staff/accounts", headers={"Authorization": f"Bearer {token}"}).status_code == 200


# ------------------------------------------------------------------ the login page's role must match the account
WRONG = "Wrong phone number, email or password"


@pytest.mark.parametrize("phone,password,chosen", [
    ("0200000001", "demo123", "mate"),              # manager on the mate page
    ("0200000004", "mate123", "station_staff"),     # mate on the station staff page
    ("0200000004", "mate123", "station_manager"),   # mate on the manager page
    ("0200000002", "staff123", "station_manager"),  # station staff on the manager page
    ("0240000001", "driver123", "mate"),            # driver on the mate page
    ("0200000001", "demo123", "station_staff"),     # manager on the station staff page
])
def test_wrong_role_looks_like_wrong_details(client, phone, password, chosen):
    r = client.post("/auth/login", json={"login": phone, "password": password, "role": chosen})
    assert r.status_code == 401 and r.json()["detail"] == WRONG and "token" not in r.json()


@pytest.mark.parametrize("phone,password,role", [
    ("0200000001", "demo123", "station_manager"), ("0200000002", "staff123", "station_staff"),
    ("0200000004", "mate123", "mate"), ("0240000001", "driver123", "driver"),
])
def test_right_role_logs_in(client, phone, password, role):
    r = client.post("/auth/login", json={"login": phone, "password": password, "role": role})
    assert r.status_code == 200 and r.json()["role"] == role


def test_wrong_role_counts_towards_the_attempt_limit(client):
    for _ in range(config.LOGIN_MAX_FAILURES):
        client.post("/auth/login", json={"login": "0200000004", "password": "mate123", "role": "station_staff"})
    r = client.post("/auth/login", json={"login": "0200000004", "password": "mate123", "role": "mate"})
    assert r.status_code == 429
