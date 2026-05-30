# RELEASE_CHECKLIST.md
# Release Checklist

## Security
- [ ] JWT secret verified (no fallback)
- [ ] Environment variables validated
- [ ] Rate limiting enabled
- [ ] Email verification working
- [ ] Password reset working
- [ ] Permissions verified

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
