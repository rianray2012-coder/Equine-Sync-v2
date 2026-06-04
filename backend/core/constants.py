"""Shared role constants (Phase 3G).

Relocated verbatim from ``server.py``. Used by the invites/onboarding routers.
"""

ROLES = ["admin", "barn_manager", "trainer", "groom", "working_student",
         "horse_owner", "rider", "parent", "veterinarian", "farrier"]

ROLE_LABELS = {
    "admin": "Stable Owner / Admin", "barn_manager": "Barn Manager", "trainer": "Trainer",
    "groom": "Groom", "working_student": "Working Student", "horse_owner": "Horse Owner",
    "rider": "Rider", "parent": "Parent / Guardian", "veterinarian": "Veterinarian", "farrier": "Farrier",
}
