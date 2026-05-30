# ROLE_PERMISSION_MATRIX.md
# EquineSync Role Permission Matrix

## Purpose
This document defines role-based access and operational permissions across the EquineSync platform. All permission logic should: be centralized, follow least-privilege principles, support tenant isolation, avoid inline role checks. **This document is the authoritative source for permission behavior.**

> **Current-state note:** The live code has only a minimal `require_setup_role` helper (admin/barn_manager gate) in `routes/auth.py`. There is no centralized permission service yet and the matrix below is **not** enforced end-to-end. Implementation is sequenced in Phase 4. See `KNOWN_TECH_DEBT.md` → "Inconsistent Permission Logic".

## Core Roles
- Admin
- Barn Manager
- Trainer
- Barn Staff
- Lesson Student (Non-horse Owner)
- Lesson Student (Horse Owner)
- Horse Owner
- Rider
- Parent
- Veterinarian
- Farrier

## Permission Legend
- **Full** = unrestricted access
- **Limited** = restricted visibility or actions
- **Own Only** = only records associated with owned horses
- **None** = no access

## Horse Management
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| View Horse | Full | Full | Full | Limited | Own Only |
| Create Horse | Full | Full | Limited | None | None |
| Edit Horse | Full | Full | Limited | None | None |
| Archive Horse | Full | Full | None | None | None |

## Care Tasks
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| View Tasks | Full | Full | Full | Assigned Only | Own Horse Limited |
| Create Tasks | Full | Full | Full | None | Limited |
| Complete Tasks | Full | Full | Full | Assigned Only | Limited |
| Reassign Tasks | Full | Full | Limited | None | None |

## Medications
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| View Medications | Full | Full | Full | Assigned Only | Own Horse |
| Edit Medications | Full | Full | Limited | None | None |
| Administer Medication | Full | Full | Full | Assigned Only | Own Horse |

## Billing for Boarding
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| View Invoices | Full | Full | None | None | Own Only |
| Create Invoices | Full | Full | None | None | None |
| Edit Invoices | Full | Full | None | None | None |
| Record Payments | Full | Full | None | None | Limited |

## Billing for Training
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| View Invoices | Full | Limited | Full | None | Own Only |
| Create Invoices | Full | Limited | Full | None | None |
| Edit Invoices | Full | Limited | Full | None | None |
| Record Payments | Full | Full | Full | None | Limited |

## Owner Communications
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| Send Owner Updates | Full | Full | Full | None | None |
| View Owner Updates | Full | Full | Full | Limited | Own Only |
| Upload Photos | Full | Full | Full | Limited | Limited |

## Incident Reports
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| Create Incident Report | Full | Full | Full | Assigned Only | Own Horse Only |
| View Incident Reports | Full | Full | Full | Limited | Own Horse Only |
| Resolve Incident Reports | Full | Full | Limited | None | None |

## Reporting
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| View Operational Reports | Full | Full | Limited | None | None |
| View Financial Reports | Full | Full | None | None | None |
| View Owner Reports | Full | Full | Full | Limited | Own Only |

## User Management
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| Create Users | Full | Full | Limited | None | None |
| Edit Users | Full | Full | Limited | None | None |
| Assign Roles | Full | Limited | Limited | None | None |

## Audit Logs
| Action | Admin | Barn Manager | Trainer | Barn Staff | Owner |
|---|---|---|---|---|---|
| View Audit Logs | Full | Limited | None | None | None |

## Permission Principles
1. **Tenant Isolation** — Users may only access records associated with their barn.
2. **Least Privilege** — Users should only access information required for their role.
3. **Owner Visibility** — Owners should only see records related to horses they own.
4. **Centralized Validation** — Permission logic should live in centralized permission systems, not inline route checks.

## Future Role Expansion
Potential future roles: Assistant Trainer, Barn Accountant, Client Coordinator, Stable Hand, Hauling Coordinator, Show Manager.

## Future Permission System Goals
Granular field-level permissions, temporary permissions, delegated access, audit-based permission review, role inheritance.
