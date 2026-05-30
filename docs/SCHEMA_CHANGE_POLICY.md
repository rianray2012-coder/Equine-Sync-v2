# SCHEMA_CHANGE_POLICY.md
# Schema Change Policy

## Purpose
Protect data integrity.

## Rules
Never:
- remove fields without review
- rename fields without a migration plan
- alter ownership relationships casually

## Required Process
1. Document change
2. Update `DATA_MODEL.md`
3. Review tenant implications
4. Review permission implications
5. Create migration plan
6. Add tests

## Migration Notes
Every schema change requires:
- reason
- affected entities
- rollback plan
