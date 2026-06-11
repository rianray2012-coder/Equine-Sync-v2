"""Backend tests for invite flow, analytics events, tenant-reset, onboarding reset, deep-merge progress."""
import uuid
import requests
import pytest

from ._api_helpers import API, BASE as BASE_URL
from ._test_creds import ADMIN, GROOM, DEMO_PASSWORD


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login(ADMIN)}"}


@pytest.fixture(scope="module")
def groom_h():
    return {"Authorization": f"Bearer {_login(GROOM)}"}


def _uniq_email(prefix="test_invite"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"


# ============ INVITES ============
class TestInvitesCreate:
    def test_create_invite_returns_dev_url(self, admin_h):
        email = _uniq_email()
        r = requests.post(f"{API}/invites", headers=admin_h,
                          json={"email": email, "full_name": "TEST_ Manager",
                                "role": "barn_manager"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Should expose dev_accept_url because RESEND_API_KEY is blank (dev mode)
        assert "dev_accept_url" in d, f"expected dev_accept_url in response, got {d}"
        assert "/accept-invite?token=" in d["dev_accept_url"]
        assert d["status"] == "pending"
        assert d["email"] == email
        assert d["role"] == "barn_manager"
        assert "token_hash" not in d  # never leaked
        # Cleanup
        requests.post(f"{API}/invites/{d['id']}/revoke", headers=admin_h, timeout=30)

    def test_create_invite_forbidden_for_groom(self, groom_h):
        r = requests.post(f"{API}/invites", headers=groom_h,
                          json={"email": _uniq_email("forbidden"), "role": "trainer"}, timeout=30)
        assert r.status_code == 403, r.text

    def test_create_invite_409_on_duplicate(self, admin_h):
        email = _uniq_email("dup")
        r1 = requests.post(f"{API}/invites", headers=admin_h,
                           json={"email": email, "role": "trainer"}, timeout=30)
        assert r1.status_code == 200
        inv_id = r1.json()["id"]
        r2 = requests.post(f"{API}/invites", headers=admin_h,
                           json={"email": email, "role": "trainer"}, timeout=30)
        assert r2.status_code == 409
        requests.post(f"{API}/invites/{inv_id}/revoke", headers=admin_h, timeout=30)

    def test_create_invite_409_existing_user(self, admin_h):
        # admin already exists
        r = requests.post(f"{API}/invites", headers=admin_h,
                          json={"email": "admin@equinesync.com", "role": "trainer"}, timeout=30)
        assert r.status_code == 409


class TestInvitesList:
    def test_list_invites_no_token_hash(self, admin_h):
        r = requests.get(f"{API}/invites", headers=admin_h, timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        for it in items:
            assert "token_hash" not in it


class TestInvitesResendRevokeVerifyAccept:
    @pytest.fixture(scope="class")
    def created(self, admin_h):
        email = _uniq_email("flow")
        r = requests.post(f"{API}/invites", headers=admin_h,
                          json={"email": email, "full_name": "TEST_ Flow",
                                "role": "barn_manager"}, timeout=30)
        assert r.status_code == 200
        return {"email": email, **r.json()}

    def test_resend_returns_new_dev_url(self, admin_h, created):
        r = requests.post(f"{API}/invites/{created['id']}/resend", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "dev_accept_url" in d
        assert d["status"] == "pending"
        # sends history grew
        assert len(d.get("sends", [])) >= 2
        # save new token URL for accept test
        created["dev_accept_url"] = d["dev_accept_url"]

    def test_verify_invalid_token_404(self):
        r = requests.get(f"{API}/invites/verify", params={"token": "garbage_invalid_token"}, timeout=30)
        assert r.status_code == 404

    def test_verify_valid_token(self, created):
        token = created["dev_accept_url"].split("token=")[-1]
        r = requests.get(f"{API}/invites/verify", params={"token": token}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == created["email"]
        assert "barn" in d
        assert "token_hash" not in d

    def test_accept_creates_user_with_auto_launch(self, admin_h, created):
        token = created["dev_accept_url"].split("token=")[-1]
        r = requests.post(f"{API}/invites/accept",
                          json={"token": token, "password": DEMO_PASSWORD,
                                "full_name": "TEST_ Flow User"}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "token" in d and "user" in d
        assert d["user"]["email"] == created["email"]
        assert d["user"]["role"] == "barn_manager"
        # barn_manager => auto_launch_onboarding=true
        assert d["auto_launch_onboarding"] is True
        # Onboarding progress pre-created
        new_token = d["token"]
        gp = requests.get(f"{API}/onboarding/progress",
                         headers={"Authorization": f"Bearer {new_token}"}, timeout=30)
        assert gp.status_code == 200
        assert gp.json()["completed"] is False

        # Now invite is accepted; verify on same token returns 410
        r2 = requests.get(f"{API}/invites/verify", params={"token": token}, timeout=30)
        assert r2.status_code == 410

    def test_revoke_marks_revoked(self, admin_h):
        # create fresh invite to revoke
        email = _uniq_email("torevoke")
        r = requests.post(f"{API}/invites", headers=admin_h,
                          json={"email": email, "role": "trainer"}, timeout=30)
        inv_id = r.json()["id"]
        rr = requests.post(f"{API}/invites/{inv_id}/revoke", headers=admin_h, timeout=30)
        assert rr.status_code == 200
        # List should show revoked
        items = requests.get(f"{API}/invites", headers=admin_h, timeout=30).json()
        match = next((x for x in items if x["id"] == inv_id), None)
        assert match and match["status"] == "revoked"


class TestAcceptNonSetupRole:
    def test_accept_groom_role_no_auto_launch(self, admin_h):
        email = _uniq_email("groom_invite")
        r = requests.post(f"{API}/invites", headers=admin_h,
                          json={"email": email, "full_name": "TEST_ Groom",
                                "role": "groom"}, timeout=30)
        assert r.status_code == 200
        token = r.json()["dev_accept_url"].split("token=")[-1]
        ar = requests.post(f"{API}/invites/accept",
                           json={"token": token, "password": DEMO_PASSWORD}, timeout=30)
        assert ar.status_code == 200, ar.text
        assert ar.json()["auto_launch_onboarding"] is False


# ============ ONBOARDING RESET ============
class TestOnboardingReset:
    def test_reset_reopens(self, admin_h):
        # Complete then reset
        requests.post(f"{API}/onboarding/complete", headers=admin_h, timeout=30)
        r = requests.post(f"{API}/onboarding/reset", headers=admin_h, timeout=30)
        assert r.status_code == 200, r.text
        g = requests.get(f"{API}/onboarding/progress", headers=admin_h, timeout=30).json()
        assert g["completed"] is False


# ============ DEEP MERGE ============
class TestProgressDeepMerge:
    def test_deep_merge_preserves_sibling_keys(self, admin_h):
        # First patch: set barn_draft.name AND barn_draft.facility
        r1 = requests.patch(f"{API}/onboarding/progress", headers=admin_h,
                            json={"data": {"barn_draft": {"name": "TEST_ DM", "facility": "boarding"}}},
                            timeout=30)
        assert r1.status_code == 200
        # Second patch: set ONLY barn_draft.name -> facility must remain
        r2 = requests.patch(f"{API}/onboarding/progress", headers=admin_h,
                            json={"data": {"barn_draft": {"name": "TEST_ DM 2"}}}, timeout=30)
        assert r2.status_code == 200
        d = r2.json()["data"]
        assert d["barn_draft"]["name"] == "TEST_ DM 2"
        assert d["barn_draft"].get("facility") == "boarding", \
            f"deep-merge failed; expected sibling key preserved, got {d['barn_draft']}"


# ============ EVENTS / FUNNEL ============
class TestEvents:
    def test_record_event(self, admin_h):
        r = requests.post(f"{API}/events", headers=admin_h,
                          json={"name": "onboarding.test_event",
                                "props": {"step": "barn"}}, timeout=30)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_funnel_admin(self, admin_h):
        # Make sure at least one event exists
        requests.post(f"{API}/events", headers=admin_h,
                      json={"name": "onboarding.step_view", "props": {"step": "barn"}}, timeout=30)
        r = requests.get(f"{API}/events/onboarding-funnel", headers=admin_h, timeout=30)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        names = [row["event"] for row in rows]
        assert any(n.startswith("onboarding.") for n in names)

    def test_funnel_forbidden_for_groom(self, groom_h):
        r = requests.get(f"{API}/events/onboarding-funnel", headers=groom_h, timeout=30)
        assert r.status_code == 403


# ============ TENANT RESET ============
class TestTenantReset:
    def test_requires_confirm(self, admin_h):
        r = requests.post(f"{API}/admin/tenant-reset", headers=admin_h,
                          json={"scope": "onboarding", "confirm": "nope"}, timeout=30)
        assert r.status_code == 400

    def test_groom_forbidden(self, groom_h):
        r = requests.post(f"{API}/admin/tenant-reset", headers=groom_h,
                          json={"scope": "onboarding", "confirm": "RESET"}, timeout=30)
        assert r.status_code == 403

    def test_unknown_scope(self, admin_h):
        r = requests.post(f"{API}/admin/tenant-reset", headers=admin_h,
                          json={"scope": "bogus", "confirm": "RESET"}, timeout=30)
        assert r.status_code == 400

    def test_onboarding_scope(self, admin_h):
        r = requests.post(f"{API}/admin/tenant-reset", headers=admin_h,
                          json={"scope": "onboarding", "confirm": "RESET"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert "onboarding_progress" in d["cleared"]
