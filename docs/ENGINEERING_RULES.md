# ENGINEERING_RULES.md
# EquineSync Engineering Rules

## Purpose
EquineSync is a production-grade equine operations SaaS platform. All engineering decisions must prioritize:
- reliability
- maintainability
- security
- scalability
- mobile usability
- trust
- operational clarity

This codebase is **NOT** a prototype playground.

---

## Core Engineering Principles
1. **Do Not Rebuild Working Systems Unnecessarily** — Preserve stable workflows whenever possible. Refactor incrementally.
2. **One Architectural Objective Per Change** — Avoid large uncontrolled rewrites. Changes should be isolated and reviewable.
3. **Prefer Explicitness Over Cleverness** — Code should be readable by future AI systems and human developers.
4. **Security Over Convenience** — Never use unsafe production defaults.
5. **Mobile-First Thinking** — All workflows should prioritize phone usability.

---

## Backend Rules

### Target Folder Structure
```
/backend
  /app
    /api        (routes; thin)
    /services   (business logic)
    /models     (persistence models)
    /schemas    (request/response typed schemas)
    /core       (config, security, deps)
    /db         (database access)
    /utils
```
Do not place business logic directly in route handlers.

> **Current-state note:** The backend has not yet been restructured to this target. Logic currently lives in `backend/server.py` (~797 lines) and `backend/routes/*.py`. Migration is sequenced in Phase 3 of `PHASED_EXECUTION_PLAN.md`. New work should move toward this target structure, not deepen the monolith.

### Route Rules
Routes **should**: validate requests, call services, return standardized responses.
Routes should **NOT**: contain business logic, directly manipulate database queries, contain permission logic inline.

### Service Rules
Business logic belongs in services. Services may call the database layer and external APIs and may enforce workflows. Services should **NOT** contain HTTP response formatting or frontend-specific logic.

### Schema Rules
All API request and response structures must use typed schemas.

### Database Rules
Every major entity must include:
- `id`
- `barn_id`
- `created_at`
- `updated_at`
- `created_by`

---

## Security Rules
- **JWT Rules:** No fallback secrets allowed.
- **Auth Rules:** All protected routes require authentication, permission validation, and tenant isolation validation.
- **Permission Rules:** Never hardcode role checks inline. Always use the centralized permission system.

---

## Frontend Rules
- **Component Structure:** Shared UI belongs in `/components/ui`. Feature-specific components belong in `/components/features`.
- **Styling Rules:** Use shared design tokens only (see `DESIGN_TOKENS.md`). No random inline styles.
- **Mobile Rules:** All pages must function cleanly on mobile.

---

## Dependency Rules
Do not add dependencies without: explaining purpose, checking overlap with existing dependencies, evaluating bundle impact.

---

## Testing Rules
All major features require: backend tests, permission tests, tenant isolation tests.

---

## AI Coding Rules
AI systems **must**: inspect architecture before coding, avoid duplicate systems, avoid creating alternative patterns, preserve existing behavior unless requested.

AI systems must **NOT**: create large rewrites without approval, introduce new architecture patterns arbitrarily, silently modify schemas.
