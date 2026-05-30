# AI_CODING_PROMPTS.md
# AI Coding Prompts

## Purpose
This document contains standardized prompts for AI-assisted development. All major development work should begin by consulting: `PRODUCT_VISION.md`, `ENGINEERING_RULES.md`, `DATA_MODEL.md`, `API_CONTRACTS.md`.

---

## Universal Development Prompt
Read: `PRODUCT_VISION.md`, `ENGINEERING_RULES.md`, `DATA_MODEL.md`.
Then:
1. Inspect current architecture.
2. Identify correct files to modify.
3. Explain implementation plan.
4. Preserve existing functionality.
5. Avoid duplicate systems.
6. Follow architecture patterns.
7. Update tests.
8. Update documentation.

**Do not begin coding until the implementation plan is complete.**

---

## Feature Development Prompt
Analyze the existing codebase and architecture. Implement ONLY the requested feature.
Requirements: preserve existing behavior, follow engineering rules, use existing patterns, update tests, update documentation.
Explain: files modified, risks, future considerations.

---

## Refactor Prompt
Inspect existing architecture. Refactor ONLY the specified module.
Do not: introduce new patterns, modify unrelated modules, change API behavior.
Provide: implementation plan, risks, migration notes.

---

## Security Audit Prompt
Review: authentication, authorization, tenant isolation, secrets handling, API security.
Identify: critical risks, high risks, medium risks.
Provide remediation recommendations.

---

## Bug Fix Prompt
Identify: root cause, affected modules, safest fix.
Implement the smallest viable fix. Avoid architectural changes unless required.

---

## Mobile Optimization Prompt
Review workflow for mobile usage. Optimize: layout, spacing, touch targets, performance. Preserve existing functionality.

---

## Testing Prompt
Review feature. Create: happy-path tests, edge-case tests, permission tests, tenant isolation tests. Report coverage gaps.
