# ARCHITECTURE.md
# EquineSync Architecture

## Purpose
This document defines the **current** and **target** technical architecture for EquineSync. EquineSync is evolving from an early-stage prototype into a production-grade, multi-tenant equine operations SaaS platform. This document exists to: preserve architectural consistency, guide AI-assisted development, reduce technical drift, support future scaling, and simplify onboarding for future developers.

## System Philosophy
EquineSync is designed as: a modular SaaS platform, a multi-tenant operational system, a mobile-first workflow platform, and a trust-centered communication layer.

The system prioritizes: operational clarity, maintainability, tenant isolation, security, scalability, mobile usability, extensibility.

## Current Technology Stack
**Frontend:** React, JavaScript/JSX, TailwindCSS, Radix UI (shadcn/ui), React Router.
**Backend:** FastAPI, Python, JWT authentication (with refresh-token rotation).
**Database:** MongoDB (via Motor async driver).
**Infrastructure:** Environment-variable-driven configuration; Kubernetes-managed services (supervisor), nginx ingress routing `/api` → backend:8001, all else → frontend:3000.

> **Reconciliation note:** The architecture PDF lists "TypeScript" for the frontend; the actual codebase is **JavaScript/JSX** (`.jsx`/`.js`). Documented here for accuracy.

## Target Long-Term Architecture
```
/frontend
  /src
    /components
      /ui
      /layout
      /features
    /pages
    /hooks
    /context
    /lib
    /styles

/backend
  /app
    /api
      /routes
    /services
    /models
    /schemas
    /core
    /db
    /utils
    /tasks

/docs   (governance documents — this folder)
```

> **Current-state note:** Backend is not yet modularized to this target (see `KNOWN_TECH_DEBT.md` → "Backend Monolith"). Frontend has `components/`, `components/ui/`, `pages/`, `hooks/`, `context/`, `lib/` but no `components/features/` separation yet.

## Architectural Principles
1. **Modular Services** — Business logic belongs in services, not route handlers.
2. **Thin Routes** — Routes validate requests, call services, return responses; never contain business logic, direct DB queries, or inline permission logic.
3. **Centralized Permissions** — Permission logic must live in a centralized permission system.
4. **Multi-Tenant Safety** — Every major entity must belong to a tenant/barn. All requests must validate authentication, tenant access, and permissions.
5. **Mobile-First Workflows** — Core workflows must function cleanly on phones.
6. **Incremental Refactoring** — Avoid large uncontrolled rewrites; prefer isolated architectural improvements.

## Core System Modules
- **Authentication** — login, registration, password reset, email verification, JWT handling, session validation.
- **Horses** — horse profiles, ownership, trainer assignment, status tracking, care instructions.
- **Care Operations** — feeding, turnout, medication, rehab, grooming, stall rest, task completion.
- **Billing** — invoices, recurring board, training charges, lessons, owner billing visibility, payment tracking.
- **Owner Portal** — owner communication, horse updates, media sharing, billing visibility, reports, owner updates.
- **Notifications** — email notifications, reminders, workflow alerts.
- **Audit Logs** — immutable operational history, user activity tracking, compliance visibility.

## Multi-Tenant Architecture
Every operational entity should include: `barn_id`, `created_by`, `created_at`, `updated_at`. Users may only access data associated with their tenant/barn. **Tenant isolation is mandatory.**

> **Current-state note:** `barn_id` is **not** yet enforced platform-wide (only present in invites flow). This is a top-priority gap — see Phase 4.

## Security Architecture
Requirements: no fallback production secrets, centralized environment validation, rate limiting, permission validation, audit logging, secure password handling.
**JWT:** JWT secrets must NEVER contain fallback values.

## API Structure
All APIs should: follow consistent naming, return standardized responses, validate permissions, enforce tenant isolation. All backend routes are prefixed with `/api`. See `API_CONTRACTS.md` and `API_VERSIONING.md`.

## Logging & Monitoring
Target logging structure: request IDs, user IDs, tenant IDs, route names, response status, error metadata. Future integrations: Sentry, uptime monitoring, audit/event streaming.

## AI Development Philosophy
AI systems are contributors, not autonomous architects. AI-generated code must follow `ENGINEERING_RULES.md`, inspect existing architecture first, avoid duplicate systems, and preserve consistency. AI systems must NOT create uncontrolled rewrites, introduce conflicting patterns, or silently alter schemas.

## Long-Term Technical Goals
- **Phase 1:** stabilize architecture, modularize backend, improve security, add tests.
- **Phase 2:** strengthen workflows, improve mobile UX, add audit systems, improve billing.
- **Phase 3:** advanced reporting, workflow automation, AI summaries, analytics.
- **Phase 4:** enterprise-grade scalability, ecosystem integrations, advanced operational intelligence.
