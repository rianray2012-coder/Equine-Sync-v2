# RELEASE_CHECKLIST.md
# Release Checklist

## Security
- [ ] JWT secret verified (no fallback)
- [ ] Environment variables validated
- [ ] Rate limiting enabled
- [ ] Email verification working
- [ ] Password reset working
- [ ] Permissions verified
- [ ] `ALLOW_SEED_ROUTE` is unset/false in production (destructive `/api/seed` returns 404 — and is blocked entirely in production even if the flag is on)
- [ ] Startup auto-seed disabled in production (`ALLOW_AUTO_SEED` unset; empty prod DB must NOT create demo accounts)
- [ ] Public registration cannot create privileged roles (admin/barn_manager/trainer) — verified `horse_owner` default
- [ ] If `ENFORCE_EMAIL_VERIFICATION=true`: registration withholds session tokens until verified, AND `get_current_user` rejects unverified/pre-issued tokens with 403

## Multi-Tenant Safety
- [ ] Tenant isolation tested
- [ ] Cross-tenant access blocked
- [ ] Owner visibility verified

## Testing
- [ ] Authentication tests pass
- [ ] Billing tests pass
- [ ] Care workflow tests pass
- [ ] Permission tests pass
- [ ] Audit log tests pass

## Frontend
- [ ] Mobile layouts verified
- [ ] Dashboard functionality verified
- [ ] Forms tested
- [ ] Navigation tested

## Backend
- [ ] No critical errors
- [ ] No failing tests
- [ ] Database indexes verified

## Billing
- [ ] Invoice calculations verified
- [ ] Payment tracking verified

## Owner Portal
- [ ] Horse visibility verified
- [ ] Owner updates verified

## Deployment
- [ ] Production variables configured
- [ ] Database backups confirmed
- [ ] Monitoring enabled

## Documentation
- [ ] Changelog updated
- [ ] Documentation updated
