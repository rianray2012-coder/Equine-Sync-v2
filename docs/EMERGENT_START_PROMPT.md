# EMERGENT_START_PROMPT.md

You are helping develop **EquineSync**, a production-grade equine operations SaaS platform.

Before coding, read the documentation in `/docs` (physically `/app/docs` in this workspace), especially:

- `MASTER_INDEX.md`
- `PRODUCT_VISION.md`
- `ENGINEERING_RULES.md`
- `ARCHITECTURE.md`
- `DATA_MODEL.md`
- `API_CONTRACTS.md`
- `ROLE_PERMISSION_MATRIX.md`
- `OWNER_TRUST_FRAMEWORK.md`

## Important rules

1. Do not rebuild the app from scratch.
2. Do not make broad uncontrolled changes.
3. Implement one clearly scoped objective at a time.
4. Preserve existing working functionality.
5. Avoid duplicate systems.
6. Follow existing architecture patterns.
7. Do not bypass permissions or tenant isolation.
8. Do not modify schemas without updating `DATA_MODEL.md` (see `SCHEMA_CHANGE_POLICY.md`).
9. Add or update tests for meaningful changes.
10. Explain the implementation plan before coding.

Your job is to improve EquineSync incrementally from prototype into production-ready SaaS.

> **Path note:** The start prompt references `/docs`. In this Emergent workspace the project root is `/app`, so the docs live at `/app/docs`. Treat the two as equivalent.
