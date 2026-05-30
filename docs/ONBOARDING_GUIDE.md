# ONBOARDING_GUIDE.md
# EquineSync Onboarding Guide

## Welcome
EquineSync is a multi-tenant equine operations platform. Before making changes, read:
1. `PRODUCT_VISION.md`
2. `ENGINEERING_RULES.md`
3. `DATA_MODEL.md`
4. `API_CONTRACTS.md`

## Project Philosophy
EquineSync prioritizes: trust, accountability, operational clarity, mobile usability.

## Folder Structure
```
/docs        (governance — physically /app/docs)
/frontend    (React app)
/backend     (FastAPI app)
```

## Development Workflow
1. Analyze
2. Plan
3. Implement
4. Test
5. Document

## Rules
Never: create duplicate systems, bypass permissions, skip testing, alter schemas without documentation.

## Core Modules
Authentication · Horse Management · Care Operations · Billing · Owner Portal · Notifications · Audit Logs · Reporting.

## Before Shipping
Review `RELEASE_CHECKLIST.md`.

## Local Environment Notes (this workspace)
- Backend: FastAPI on `0.0.0.0:8001` (supervisor-managed). All routes prefixed `/api`.
- Frontend: React on `:3000`. Uses `REACT_APP_BACKEND_URL` for API calls.
- Database: MongoDB via `MONGO_URL` + `DB_NAME` (backend `.env`).
- Restart after `.env`/dependency changes only: `sudo supervisorctl restart backend|frontend`.
