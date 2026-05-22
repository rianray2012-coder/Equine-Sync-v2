# EquineSync — Auth Migration Plan
_Status: **DOCUMENTED ONLY · NOT IMPLEMENTED** · scheduled as the first major post-founder-beta engineering sprint_

> Per founder direction, this plan is captured before founder-barn onboarding
> begins so the work is well-scoped when we eventually do it. **No
> implementation work has started.** The current localStorage-based JWT
> approach is preserved through founder-beta to avoid auth disruption during
> the most observation-critical window.

---

## 1 · Current state (as of Feb 20 2026)

- Access token stored in `localStorage` under `equine_session.access_token`.
- Refresh token stored alongside in the same `equine_session` object.
- `apiClient` reads both on each request, attaches `Authorization: Bearer <access>` header.
- Refresh-rotation already implemented: a 401 triggers a single `/api/auth/refresh` call, which rotates both tokens. Working as designed.
- No CSRF token issued. CSRF protection currently relies on the bearer-token model (no cookies) — which is the standard SPA defense.

## 2 · Risk profile

The localStorage approach has three known exposures, mitigated to varying degrees:

| Exposure | Mitigation today | Residual risk |
|---|---|---|
| XSS-extractable tokens | React strict mode + sanitised inputs + CSP-eligible build | **Real but bounded.** A successful XSS lifts the access token. Refresh rotation limits the blast radius to one access-token lifetime (currently short). |
| Token leakage via shared device | Tokens persist across browser tabs, survive page reload | Acceptable for boarding-barn staff devices; **not acceptable** for shared lobby tablets long-term. |
| Stolen-token replay | Bearer tokens have no per-request signature | Standard SPA risk; rotation reduces window. |

Founder-beta deployment characteristics that make this acceptable for now:

- Single-tenant deployment, known-trusted staff devices.
- No public-facing endpoints with sensitive write capabilities outside auth.
- No payment data or financial PII flows through the platform.
- The first founder-barn can be advised to use staff-personal devices, not a shared tablet, during the observation window.

## 3 · Target state (post-founder-beta sprint scope)

The migration will land four changes together. Doing them as a single coherent sprint avoids partial states where some surfaces use cookies and some still use bearer tokens.

### 3.1 — `httpOnly` + `SameSite=Lax` + `Secure` cookies for session tokens

- Backend issues both access and refresh tokens as separate cookies on `/api/auth/login`, `/api/auth/refresh`, `/api/invites/accept`.
- Cookie names: `equine_access` (short-lived), `equine_refresh` (long-lived, `Path=/api/auth`).
- `Secure` flag enforced (HTTPS-only — already the deployment profile).
- `SameSite=Lax` — strict enough to defeat most CSRF, lax enough for the existing tab-restoring login UX.
- Cookies attached automatically on every same-origin `/api` request — no client-side header logic.

### 3.2 — Refresh-token rotation with reuse detection

- Refresh tokens become single-use. Each rotation issues a fresh refresh token and invalidates the prior one.
- Replay of a previously-rotated refresh token signals compromise → invalidate the entire token family for that user, force re-login. Pattern is well-documented (RFC 6749 §10.4 sibling guidance + OWASP).
- Already partly implemented in the current flow (rotation works); the missing piece is the **reuse-detection invalidation cascade**.

### 3.3 — Per-form CSRF tokens

- The cookie session needs CSRF defense — `SameSite=Lax` covers most cases, but explicit double-submit tokens are best practice for any state-changing endpoint.
- New `/api/auth/csrf` endpoint issues a token bound to the session.
- Frontend reads the CSRF cookie (non-`httpOnly`) and echoes it as `X-CSRF-Token` header on every POST/PUT/PATCH/DELETE.
- Backend middleware compares header-vs-cookie — mismatch → 403.

### 3.4 — Auth middleware cleanup

The current `auth.py` has accumulated three concerns: dependency injection of `current_user`, role gating decorators, and refresh handling. Sprint should:

- Split into `routes/auth.py` (the public endpoints), `dependencies/auth.py` (the FastAPI dependency), `middleware/csrf.py` (new).
- Remove the `Authorization: Bearer` code path entirely once cookies are in place. Single auth surface, no dual support.
- Move `JWT_SECRET` rotation handling into a small key-set construct so a key can be retired without invalidating in-flight sessions.

---

## 4 · Migration sequence (when we eventually do this)

1. **Backend prep** — issue both cookies AND `Authorization` header in parallel for one release. Frontend continues to use bearer tokens. No user-visible change.
2. **Frontend cutover** — switch every `apiClient` call to credentialed cookie-based requests. Remove `Authorization` header logic. Test login + refresh + role gating + invite-accept end-to-end on every role.
3. **Backend tighten** — drop the bearer-token code path. Cookies become the only auth surface.
4. **CSRF rollout** — middleware-on for state-changing endpoints. Frontend reads CSRF cookie + sends header. Single release.
5. **Refresh-rotation reuse detection** — last because it depends on the cleaner auth structure landing first.

Each step is independently shippable. None of the steps in 1-3 are user-visible. Step 4 may briefly produce 403s if any frontend call is missed; pytest coverage of every `POST/PUT/PATCH/DELETE` route gates the release.

## 5 · Test surface

- Existing 175 backend tests: every login call goes through `_login()` helpers — the migration only needs to update those helpers to handle cookies, then the assertion changes propagate automatically.
- `test_dispatch_retry.py` and other Mongo-direct tests are unaffected.
- New tests required:
  - `test_csrf_double_submit.py` — header missing → 403, header mismatched → 403, header matched → 200.
  - `test_refresh_reuse_detection.py` — reusing a rotated refresh invalidates the family.
  - `test_cookie_flags.py` — issued cookies have `httpOnly`, `Secure`, `SameSite=Lax` set.

## 6 · Frontend surface

- One file changes: `apiClient.js` switches from header injection to `credentials: 'include'`.
- One file is added: `csrfClient.js` reads the CSRF cookie and attaches the header.
- Login + refresh + invite-accept pages remain visually unchanged.

## 7 · Estimated effort

- **2 engineers · 5–7 working days.** Most of the time is verification, not code.
- Best executed when the founder barn is in a low-activity stretch (e.g. between observation cycles).
- A short maintenance window — under 10 minutes — should be coordinated with the founder barn for step 3.

## 8 · What this plan does NOT address

- **Multi-tenancy.** Out of scope. The current single-tenant assumption is preserved.
- **SSO.** Out of scope. JWT remains the auth primitive.
- **Per-feature granular permissions.** Out of scope. Role-based gating remains.
- **Mobile push channel.** Unrelated; scheduled separately.

## 9 · When to schedule this sprint

Per founder direction, **not until real founder-barn observations have accumulated through the three-week rule** documented in `POST_LAUNCH_OBSERVATION_LOG.md`. Real-world auth latency, refresh-rotation behaviour under poor signal, and shared-device patterns will shape some of the implementation choices in §3. We deliberately do not pre-commit to the exact cookie attribute combinations until that data exists.

---

_End of plan. Re-read together with `OPERATIONAL_SIMULATION.md` §2 (interruption recovery) before scheduling the sprint — token-refresh interruption recovery is the most likely friction point during the migration._
