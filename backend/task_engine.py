"""
EquineSync — Unified Operational Task Engine.

Implements the architecture described in /app/memory/TASK_ENGINE_ARCHITECTURE.md:
    TaskTemplate (recipe) -> Task (occurrence) -> TaskCompletion (immutable log) -> TaskEvent (fan-out)

All side-effects (timeline, analytics, future notifications) MUST flow through
TaskEvent. Routes must not write side-effect logic inline.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime, timezone, timedelta
import uuid
import logging

from dateutil.rrule import rrulestr

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_TENANT_ID = "default"
MATERIALIZE_HORIZON_DAYS = 14

CATEGORIES = (
    "feed", "medication", "turnout_out", "turnout_in",
    "stall_clean", "farrier", "vet", "rehab", "custom",
)

PRIORITIES = ("critical", "standard", "informational")

TASK_STATUSES = (
    "scheduled", "due", "overdue", "in_progress",
    "completed", "skipped", "cancelled",
)

OUTCOMES = ("done", "partial", "skipped", "refused", "issue")

# Categories that owners may see in the curated portal feed.
# Internal staffing workflows (stall_clean, turnout_in/out alone, generic
# operational delays) are intentionally excluded by default. This is a
# configurable visibility layer per the user's directive.
OWNER_VISIBLE_CATEGORIES = {"medication", "farrier", "vet", "rehab", "feed"}
OWNER_VISIBLE_EVENT_TYPES = {
    "task.completed",  # filtered further by category at query time
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TaskTemplateIn(BaseModel):
    category: Literal["feed", "medication", "turnout_out", "turnout_in",
                       "stall_clean", "farrier", "vet", "rehab", "custom"]
    title: str
    description: Optional[str] = None
    linked_horse_ids: List[str] = Field(default_factory=list)
    linked_location_id: Optional[str] = None
    default_assignee_role: Optional[str] = None
    default_assignee_user_id: Optional[str] = None
    rrule: Optional[str] = None  # RFC 5545 RRULE string; None = one-off
    dtstart: Optional[str] = None  # ISO datetime; anchor for the recurrence
    window_minutes_before: int = 30
    window_minutes_after: int = 120
    priority: Literal["critical", "standard", "informational"] = "standard"
    payload_schema: Dict[str, Any] = Field(default_factory=dict)
    payload_defaults: Dict[str, Any] = Field(default_factory=dict)
    active: bool = True

    @field_validator("rrule")
    @classmethod
    def _validate_rrule(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        try:
            # Quick syntactic validation; full materialization happens later.
            rrulestr(v if v.upper().startswith("RRULE") else f"RRULE:{v}",
                     dtstart=datetime.now(timezone.utc))
        except Exception as exc:
            raise ValueError(f"Invalid RRULE: {exc}") from exc
        return v


class TaskTemplateOut(TaskTemplateIn):
    id: str
    tenant_id: str
    created_by: Optional[str] = None
    created_at: str
    updated_at: str


class AdHocTaskIn(BaseModel):
    """Create a one-off task without a template."""
    category: Literal["feed", "medication", "turnout_out", "turnout_in",
                       "stall_clean", "farrier", "vet", "rehab", "custom"]
    title: str
    linked_horse_ids: List[str] = Field(default_factory=list)
    linked_location_id: Optional[str] = None
    assignee_user_id: Optional[str] = None
    assignee_role: Optional[str] = None
    scheduled_at: str  # ISO
    priority: Literal["critical", "standard", "informational"] = "standard"
    payload: Dict[str, Any] = Field(default_factory=dict)
    window_minutes_before: int = 30
    window_minutes_after: int = 120
    notes: Optional[str] = None


class TaskPatch(BaseModel):
    title: Optional[str] = None
    assignee_user_id: Optional[str] = None
    assignee_role: Optional[str] = None
    scheduled_at: Optional[str] = None
    priority: Optional[Literal["critical", "standard", "informational"]] = None
    notes: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class CompleteBody(BaseModel):
    client_completion_id: str
    completed_at: Optional[str] = None  # client-reported; defaults to now
    outcome: Literal["done", "partial", "skipped", "refused", "issue"] = "done"
    payload_actual: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

    @field_validator("client_completion_id")
    @classmethod
    def _ccid_non_empty(cls, v: str) -> str:
        if not v or len(v) < 6:
            raise ValueError("client_completion_id must be a non-empty stable id (>=6 chars)")
        return v


class BulkCompleteItem(BaseModel):
    task_id: str
    client_completion_id: str
    completed_at: Optional[str] = None
    outcome: Literal["done", "partial", "skipped", "refused", "issue"] = "done"
    payload_actual: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class BulkCompleteBody(BaseModel):
    items: List[BulkCompleteItem]
    shared_note: Optional[str] = None


class SkipBody(BaseModel):
    client_completion_id: str
    reason: Optional[str] = None
    refused: bool = False  # True => outcome=refused; False => skipped
    notes: Optional[str] = None


class ReassignBody(BaseModel):
    assignee_user_id: Optional[str] = None
    assignee_role: Optional[str] = None


# ---------------------------------------------------------------------------
# Engine — pure functions on a Mongo db handle
# ---------------------------------------------------------------------------

class TaskEngine:
    """Owns lifecycle, materialization, completion, and event fan-out.

    Stateless besides the db handle; safe to instantiate per-request.
    """

    def __init__(self, db, analytics_track=None):
        self.db = db
        self._track = analytics_track or (lambda *a, **kw: None)

    # -- index bootstrap --------------------------------------------------
    async def ensure_indexes(self):
        await self.db.tasks.create_index([("tenant_id", 1), ("scheduled_at", 1), ("status", 1)])
        await self.db.tasks.create_index([("tenant_id", 1), ("linked_horse_ids", 1), ("scheduled_at", -1)])
        await self.db.tasks.create_index([("tenant_id", 1), ("assignee_user_id", 1), ("status", 1)])
        await self.db.tasks.create_index([("tenant_id", 1), ("template_id", 1), ("scheduled_at", 1)])
        await self.db.task_templates.create_index([("tenant_id", 1), ("active", 1), ("category", 1)])
        await self.db.task_completions.create_index(
            [("task_id", 1), ("client_completion_id", 1)], unique=True,
        )
        await self.db.task_completions.create_index([("tenant_id", 1), ("completed_at", -1)])
        await self.db.task_events.create_index([("tenant_id", 1), ("subject_horse_ids", 1), ("occurred_at", -1)])
        await self.db.task_events.create_index([("tenant_id", 1), ("actor_user_id", 1), ("occurred_at", -1)])
        await self.db.task_events.create_index([("tenant_id", 1), ("event_type", 1), ("occurred_at", -1)])
        # Phase-B: indexes for engine-projected health collections
        await self.db.vet_records.create_index([("horse_id", 1), ("date", -1)])
        await self.db.vet_records.create_index([("linked_task_id", 1)])
        await self.db.farrier_history.create_index([("horse_id", 1), ("date", -1)])
        await self.db.farrier_history.create_index([("linked_task_id", 1)])

    # -- materialization --------------------------------------------------
    def _expand_rrule(self, template: dict, horizon: datetime) -> List[datetime]:
        rule = template.get("rrule")
        dtstart_raw = template.get("dtstart")
        if not rule:
            # one-off: emit a single occurrence at dtstart (if in horizon window)
            if dtstart_raw:
                return [parse_iso(dtstart_raw)]
            return []
        dtstart = parse_iso(dtstart_raw) if dtstart_raw else now_utc()
        rrule_str = rule if rule.upper().startswith("RRULE") else f"RRULE:{rule}"
        try:
            rule_obj = rrulestr(rrule_str, dtstart=dtstart)
        except Exception:
            logger.exception("Invalid rrule for template %s", template.get("id"))
            return []
        # Bound by 14-day horizon AND a sane upper count to avoid runaway loops.
        start_window = now_utc() - timedelta(days=1)
        return [o for o in rule_obj.between(start_window, horizon, inc=True)][:500]

    @staticmethod
    def _build_task_doc(template: dict, occ: datetime, tenant_id: str) -> dict:
        wb = int(template.get("window_minutes_before", 30) or 0)
        wa = int(template.get("window_minutes_after", 120) or 0)
        now_iso = iso(now_utc())
        return {
            "id": new_id(),
            "tenant_id": tenant_id,
            "template_id": template["id"],
            "category": template["category"],
            "title": template["title"],
            "linked_horse_ids": list(template.get("linked_horse_ids", [])),
            "linked_location_id": template.get("linked_location_id"),
            "assignee_user_id": template.get("default_assignee_user_id"),
            "assignee_role": template.get("default_assignee_role"),
            "scheduled_at": iso(occ),
            "window_start": iso(occ - timedelta(minutes=wb)),
            "window_end": iso(occ + timedelta(minutes=wa)),
            "priority": template.get("priority", "standard"),
            "status": "scheduled",
            "payload": dict(template.get("payload_defaults") or {}),
            "notes": None,
            "client_completion_id": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }

    async def _existing_occurrence_times(self, tenant_id: str, template_id: str) -> set:
        existing = await self.db.tasks.find(
            {
                "tenant_id": tenant_id,
                "template_id": template_id,
                "scheduled_at": {"$gte": iso(now_utc() - timedelta(days=1))},
            },
            {"_id": 0, "scheduled_at": 1},
        ).to_list(2000)
        return {row["scheduled_at"] for row in existing}

    async def materialize_template(self, template: dict) -> int:
        """Create future Task occurrences for this template up to the horizon.
        Idempotent: existing tasks at the same scheduled_at are kept untouched.
        """
        if not template.get("active", True):
            return 0
        horizon = now_utc() + timedelta(days=MATERIALIZE_HORIZON_DAYS)
        occurrences = self._expand_rrule(template, horizon)
        if not occurrences:
            return 0

        tenant_id = template.get("tenant_id", DEFAULT_TENANT_ID)
        existing_times = await self._existing_occurrence_times(tenant_id, template["id"])

        new_docs = [
            self._build_task_doc(template, occ, tenant_id)
            for occ in occurrences
            if iso(occ) not in existing_times
        ]
        if not new_docs:
            return 0
        await self.db.tasks.insert_many(new_docs)
        for doc in new_docs:
            await self.emit_event(
                tenant_id=tenant_id,
                event_type="task.created",
                task=doc,
                actor_user_id=None,
            )
        return len(new_docs)

    async def materialize_all(self, tenant_id: str = DEFAULT_TENANT_ID) -> int:
        templates = await self.db.task_templates.find(
            {"tenant_id": tenant_id, "active": True},
            {"_id": 0},
        ).to_list(500)
        total = 0
        for tpl in templates:
            total += await self.materialize_template(tpl)
        return total

    # -- lifecycle helpers ------------------------------------------------
    @staticmethod
    def _derive_status(task: dict, current: Optional[datetime] = None) -> str:
        """Lazy status derivation for the read path. Persisted status wins
        for terminal states; for live tasks we compute against the wall clock.
        """
        persisted = task.get("status", "scheduled")
        if persisted in ("completed", "skipped", "cancelled", "in_progress"):
            return persisted
        now = current or now_utc()
        ws = parse_iso(task["window_start"]) if task.get("window_start") else None
        we = parse_iso(task["window_end"]) if task.get("window_end") else None
        if we and now > we:
            return "overdue"
        if ws and now >= ws:
            return "due"
        return "scheduled"

    # -- event fan-out ---------------------------------------------------
    async def emit_event(self, *, tenant_id: str, event_type: str, task: dict,
                         actor_user_id: Optional[str],
                         extra: Optional[dict] = None):
        # subject horses are always the task's linked horses (denormalized)
        event_doc = {
            "id": new_id(),
            "tenant_id": tenant_id,
            "event_type": event_type,
            "task_id": task.get("id"),
            "category": task.get("category"),
            "actor_user_id": actor_user_id,
            "subject_horse_ids": list(task.get("linked_horse_ids", []) or []),
            "location_id": task.get("linked_location_id"),
            "occurred_at": iso(now_utc()),
            "payload_snapshot": {
                "title": task.get("title"),
                "priority": task.get("priority"),
                "scheduled_at": task.get("scheduled_at"),
                "payload": task.get("payload"),
                **(extra or {}),
            },
        }
        await self.db.task_events.insert_one(event_doc)

    # -- completion helpers ---------------------------------------------
    @staticmethod
    def _build_completion_doc(task_id: str, body: CompleteBody, user: dict,
                              tenant_id: str) -> dict:
        completed_at = body.completed_at or iso(now_utc())
        return {
            "id": new_id(),
            "tenant_id": tenant_id,
            "task_id": task_id,
            "completed_by_user_id": user["id"],
            "completed_at": completed_at,
            "server_received_at": iso(now_utc()),
            "outcome": body.outcome,
            "payload_actual": body.payload_actual,
            "notes": body.notes,
            "media_ids": [],
            "client_completion_id": body.client_completion_id,
            "voided": False,
            "voided_by_user_id": None,
            "voided_reason": None,
        }

    @staticmethod
    def _outcome_to_status(outcome: str) -> str:
        # refused behaves operationally as skipped; outcome preserved on completion.
        if outcome in ("skipped", "refused"):
            return "skipped"
        return "completed"

    async def _append_duplicate_note(self, canonical: dict, body: CompleteBody, user: dict):
        completed_at = body.completed_at or iso(now_utc())
        extra_note = (
            f"Also marked {body.outcome} by {user.get('full_name', 'user')} @ {completed_at}"
        )
        existing_notes = canonical.get("notes") or ""
        new_notes = (existing_notes + ("\n" if existing_notes else "") + extra_note)[:2000]
        await self.db.task_completions.update_one(
            {"id": canonical["id"]}, {"$set": {"notes": new_notes}},
        )

    # -- category post-completion hooks ------------------------------
    # Phase-B (Feb 20 2026): vet/farrier completions write back to the legacy
    # historical collections so the existing Health page + analytics see the
    # outcome immediately. Engine remains source of truth; these rows are
    # denormalized projections for read-paths that haven't migrated yet.

    @staticmethod
    def _build_vet_record(task: dict, body: CompleteBody, completion_id: str) -> dict:
        pa = body.payload_actual or {}
        snap = task.get("payload") or {}
        horse_ids = task.get("linked_horse_ids") or []
        return {
            "id": new_id(),
            "horse_id": horse_ids[0] if horse_ids else None,
            "horse_ids": horse_ids,  # multi-horse support without breaking single-horse readers
            "type": pa.get("type") or snap.get("type") or "exam",
            "title": task.get("title") or "Vet visit",
            "date": (body.completed_at or iso(now_utc())).split("T")[0],
            "vet_name": pa.get("vet_name") or snap.get("vet_name"),
            "notes": pa.get("notes") or body.notes,
            "document_url": pa.get("document_url"),
            "cost": float(pa.get("cost") or 0),
            "follow_up_due": pa.get("follow_up_due"),
            "linked_task_id": task.get("id"),
            "linked_completion_id": completion_id,
            "source": "task_engine",
            "created_at": iso(now_utc()),
        }

    @staticmethod
    def _build_farrier_record(task: dict, body: CompleteBody, completion_id: str) -> dict:
        pa = body.payload_actual or {}
        snap = task.get("payload") or {}
        horse_ids = task.get("linked_horse_ids") or []
        return {
            "id": new_id(),
            "horse_id": horse_ids[0] if horse_ids else None,
            "horse_ids": horse_ids,
            "farrier_name": pa.get("farrier_name") or snap.get("farrier_name"),
            "shoes_on": pa.get("shoes_on") or snap.get("shoes_on") or [],
            "trim_notes": pa.get("trim_notes") or body.notes,
            "cost": float(pa.get("cost") or 0),
            "date": (body.completed_at or iso(now_utc())).split("T")[0],
            "next_visit_due": pa.get("next_visit_due"),
            "linked_task_id": task.get("id"),
            "linked_completion_id": completion_id,
            "source": "task_engine",
            "created_at": iso(now_utc()),
        }

    async def _auto_schedule_follow_up(self, task: dict, follow_up_due: str,
                                       tenant_id: str, actor_user_id: Optional[str]):
        """Create a one-off task occurrence for the next scheduled vet/farrier visit."""
        if not follow_up_due:
            return None
        # Parse to ISO; accept either YYYY-MM-DD or full ISO
        try:
            if "T" in follow_up_due:
                sched = parse_iso(follow_up_due)
            else:
                sched = datetime.fromisoformat(f"{follow_up_due}T09:00:00+00:00")
        except Exception:
            logger.warning("follow_up_due unparseable: %r", follow_up_due)
            return None
        wb = 60 * 24  # 24h before
        wa = 60 * 24 * 2  # 48h after — vet/farrier visits often slip
        doc = {
            "id": new_id(),
            "tenant_id": tenant_id,
            "template_id": None,
            "category": task.get("category"),
            "title": f"Follow-up: {task.get('title')}",
            "linked_horse_ids": list(task.get("linked_horse_ids") or []),
            "linked_location_id": task.get("linked_location_id"),
            "assignee_user_id": task.get("assignee_user_id"),
            "assignee_role": task.get("assignee_role"),
            "scheduled_at": iso(sched),
            "window_start": iso(sched - timedelta(minutes=wb)),
            "window_end": iso(sched + timedelta(minutes=wa)),
            "priority": task.get("priority", "standard"),
            "status": "scheduled",
            "payload": dict(task.get("payload") or {}),
            "notes": "Auto-scheduled from prior visit",
            "client_completion_id": None,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
            "parent_task_id": task.get("id"),
        }
        await self.db.tasks.insert_one(doc)
        await self.emit_event(
            tenant_id=tenant_id,
            event_type="task.created",
            task=doc,
            actor_user_id=actor_user_id,
            extra={"reason": "follow_up_auto_scheduled"},
        )
        return doc["id"]

    async def _post_complete_hooks(self, task: dict, body: CompleteBody,
                                    completion: dict, user: dict, tenant_id: str) -> dict:
        """Run category-specific side effects. All failures are logged but never
        block the completion path — operational realism over strict consistency.
        Returns a dict of side-effect outputs to enrich the TaskEvent snapshot.
        """
        side_effects: Dict[str, Any] = {}
        cat = task.get("category")
        try:
            if cat == "vet" and body.outcome in ("done", "partial"):
                rec = self._build_vet_record(task, body, completion["id"])
                await self.db.vet_records.insert_one(rec)
                side_effects["vet_record_id"] = rec["id"]
                side_effects["cost"] = rec["cost"]
                side_effects["vet_name"] = rec["vet_name"]
                if rec["follow_up_due"]:
                    side_effects["follow_up_task_id"] = await self._auto_schedule_follow_up(
                        task, rec["follow_up_due"], tenant_id, user["id"],
                    )
            elif cat == "farrier" and body.outcome in ("done", "partial"):
                rec = self._build_farrier_record(task, body, completion["id"])
                await self.db.farrier_history.insert_one(rec)
                side_effects["farrier_record_id"] = rec["id"]
                side_effects["cost"] = rec["cost"]
                side_effects["farrier_name"] = rec["farrier_name"]
                if rec["next_visit_due"]:
                    side_effects["follow_up_task_id"] = await self._auto_schedule_follow_up(
                        task, rec["next_visit_due"], tenant_id, user["id"],
                    )
        except Exception:
            logger.exception("post-complete hook failed for task=%s category=%s",
                              task.get("id"), cat)
        return side_effects

    # -- completion ------------------------------------------------------
    async def complete_task(self, task_id: str, body: CompleteBody, user: dict,
                            tenant_id: str = DEFAULT_TENANT_ID) -> dict:
        task = await self.db.tasks.find_one(
            {"id": task_id, "tenant_id": tenant_id}, {"_id": 0},
        )
        if not task:
            raise HTTPException(404, "Task not found")

        # Idempotency: same (task_id, client_completion_id) — return existing.
        existing = await self.db.task_completions.find_one(
            {"task_id": task_id, "client_completion_id": body.client_completion_id},
            {"_id": 0},
        )
        if existing:
            return {"task": task, "completion": existing, "deduped": True}

        canonical = await self.db.task_completions.find_one(
            {"task_id": task_id, "voided": {"$ne": True}}, {"_id": 0},
        )
        completion = self._build_completion_doc(task_id, body, user, tenant_id)

        # Concurrency: a different completion already canonicalized this task.
        if canonical:
            completion["voided"] = True
            completion["voided_reason"] = "duplicate_concurrent_completion"
            await self.db.task_completions.insert_one(completion)
            completion.pop("_id", None)
            await self._append_duplicate_note(canonical, body, user)
            return {"task": task, "completion": canonical, "deduped": False,
                    "duplicate_note_appended": True}

        await self.db.task_completions.insert_one(completion)
        completion.pop("_id", None)

        new_status = self._outcome_to_status(body.outcome)
        await self.db.tasks.update_one(
            {"id": task_id},
            {"$set": {
                "status": new_status,
                "updated_at": iso(now_utc()),
                "client_completion_id": body.client_completion_id,
            }},
        )
        task["status"] = new_status

        # Phase-B post-completion hooks (vet → vet_record; farrier → farrier_history;
        # follow-up auto-scheduling). Side-effect outputs ride along on the event.
        side_effects = await self._post_complete_hooks(task, body, completion, user, tenant_id)

        event_type = "task.skipped" if new_status == "skipped" else "task.completed"
        await self.emit_event(
            tenant_id=tenant_id,
            event_type=event_type,
            task=task,
            actor_user_id=user["id"],
            extra={"outcome": body.outcome, "completion_id": completion["id"],
                   "notes": body.notes,
                   **side_effects},
        )
        try:
            res = self._track(f"task.{body.outcome}", {"task_id": task_id, "category": task.get("category")}, user["id"])
            # _track may be sync or async depending on how the engine was wired.
            if hasattr(res, "__await__"):
                await res
        except Exception:
            logger.debug("analytics track failed", exc_info=True)
        return {"task": task, "completion": completion, "deduped": False}

    async def skip_task(self, task_id: str, body: SkipBody, user: dict,
                        tenant_id: str = DEFAULT_TENANT_ID) -> dict:
        comp = CompleteBody(
            client_completion_id=body.client_completion_id,
            outcome="refused" if body.refused else "skipped",
            payload_actual={"reason": body.reason} if body.reason else {},
            notes=body.notes,
        )
        return await self.complete_task(task_id, comp, user, tenant_id)

    async def void_completion(self, task_id: str, reason: str, user: dict,
                              tenant_id: str = DEFAULT_TENANT_ID) -> dict:
        canonical = await self.db.task_completions.find_one(
            {"task_id": task_id, "voided": {"$ne": True}, "tenant_id": tenant_id},
            {"_id": 0},
        )
        if not canonical:
            raise HTTPException(404, "No active completion to void")
        await self.db.task_completions.update_one(
            {"id": canonical["id"]},
            {"$set": {
                "voided": True,
                "voided_by_user_id": user["id"],
                "voided_reason": reason or "voided",
            }},
        )
        # revert task status to overdue/due based on time
        task = await self.db.tasks.find_one({"id": task_id}, {"_id": 0})
        if task:
            new_status = self._derive_status({**task, "status": "scheduled"})
            await self.db.tasks.update_one(
                {"id": task_id},
                {"$set": {"status": new_status, "updated_at": iso(now_utc())}},
            )
            task["status"] = new_status
            await self.emit_event(
                tenant_id=tenant_id,
                event_type="task.voided",
                task=task,
                actor_user_id=user["id"],
                extra={"reason": reason, "voided_completion_id": canonical["id"]},
            )
        return {"ok": True, "voided_completion_id": canonical["id"]}


# ---------------------------------------------------------------------------
# Router factory — wires the engine into FastAPI
# ---------------------------------------------------------------------------

def build_router(db, get_current_user, analytics_track=None) -> APIRouter:
    engine = TaskEngine(db, analytics_track)
    router = APIRouter()

    # -- templates ------------------------------------------------------
    @router.get("/task-templates")
    async def list_templates(user=Depends(get_current_user),
                             category: Optional[str] = None,
                             active: Optional[bool] = None):
        q: Dict[str, Any] = {"tenant_id": DEFAULT_TENANT_ID}
        if category:
            q["category"] = category
        if active is not None:
            q["active"] = active
        items = await db.task_templates.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return {"items": items}

    @router.post("/task-templates")
    async def create_template(body: TaskTemplateIn, user=Depends(get_current_user)):
        doc = body.model_dump()
        doc.update({
            "id": new_id(),
            "tenant_id": DEFAULT_TENANT_ID,
            "created_by": user["id"],
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        })
        if not doc.get("dtstart"):
            doc["dtstart"] = iso(now_utc())
        await db.task_templates.insert_one(doc)
        created = await db.task_templates.find_one({"id": doc["id"]}, {"_id": 0})
        # Immediately materialize so the Today view reflects it.
        created_count = await engine.materialize_template(created)
        return {"template": created, "materialized": created_count}

    @router.patch("/task-templates/{tpl_id}")
    async def update_template(tpl_id: str, body: TaskTemplateIn, user=Depends(get_current_user)):
        existing = await db.task_templates.find_one({"id": tpl_id, "tenant_id": DEFAULT_TENANT_ID}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Template not found")
        updates = body.model_dump()
        updates["updated_at"] = iso(now_utc())
        await db.task_templates.update_one({"id": tpl_id}, {"$set": updates})
        # Re-materialize future, untouched occurrences.
        # Delete future scheduled (not yet started) tasks; preserve any that
        # are in_progress/completed/skipped/cancelled or have a completion.
        future_cutoff = iso(now_utc())
        await db.tasks.delete_many({
            "tenant_id": DEFAULT_TENANT_ID,
            "template_id": tpl_id,
            "status": "scheduled",
            "scheduled_at": {"$gt": future_cutoff},
        })
        refreshed = await db.task_templates.find_one({"id": tpl_id}, {"_id": 0})
        new_count = await engine.materialize_template(refreshed)
        return {"template": refreshed, "rematerialized": new_count}

    @router.delete("/task-templates/{tpl_id}")
    async def delete_template(tpl_id: str, user=Depends(get_current_user)):
        # soft-delete: set active=False
        r = await db.task_templates.update_one(
            {"id": tpl_id, "tenant_id": DEFAULT_TENANT_ID},
            {"$set": {"active": False, "updated_at": iso(now_utc())}},
        )
        if r.matched_count == 0:
            raise HTTPException(404, "Template not found")
        # cancel future scheduled instances
        await db.tasks.update_many(
            {"tenant_id": DEFAULT_TENANT_ID, "template_id": tpl_id,
             "status": "scheduled"},
            {"$set": {"status": "cancelled", "updated_at": iso(now_utc())}},
        )
        return {"ok": True}

    # -- tasks ----------------------------------------------------------
    @router.get("/tasks")
    async def list_tasks(user=Depends(get_current_user),
                         start: Optional[str] = None,
                         end: Optional[str] = None,
                         horse_id: Optional[str] = None,
                         category: Optional[str] = None,
                         assignee_user_id: Optional[str] = None,
                         status_: Optional[str] = Query(None, alias="status"),
                         priority: Optional[str] = None,
                         limit: int = 200):
        q: Dict[str, Any] = {"tenant_id": DEFAULT_TENANT_ID}
        if start or end:
            q["scheduled_at"] = {}
            if start:
                q["scheduled_at"]["$gte"] = start
            if end:
                q["scheduled_at"]["$lte"] = end
        if horse_id:
            q["linked_horse_ids"] = horse_id
        if category:
            q["category"] = category
        if assignee_user_id:
            q["assignee_user_id"] = assignee_user_id
        if priority:
            q["priority"] = priority
        items = await db.tasks.find(q, {"_id": 0}).sort("scheduled_at", 1).to_list(min(limit, 1000))
        # lazy status derivation
        now = now_utc()
        for t in items:
            t["status"] = engine._derive_status(t, now)
        if status_:
            items = [t for t in items if t["status"] == status_]
        return {"items": items, "total": len(items)}

    @router.get("/tasks/today")
    async def today_view(user=Depends(get_current_user),
                         date: Optional[str] = None):
        """Returns urgency-grouped Today view."""
        anchor = parse_iso(date) if date else now_utc()
        start = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        items = await db.tasks.find(
            {
                "tenant_id": DEFAULT_TENANT_ID,
                "scheduled_at": {"$gte": iso(start), "$lt": iso(end)},
            },
            {"_id": 0},
        ).sort("scheduled_at", 1).to_list(1000)
        now = now_utc()
        # also pull any overdue from prior days that aren't terminal
        overdue_prior = await db.tasks.find(
            {
                "tenant_id": DEFAULT_TENANT_ID,
                "scheduled_at": {"$lt": iso(start)},
                "status": {"$nin": ["completed", "skipped", "cancelled"]},
            },
            {"_id": 0},
        ).sort("scheduled_at", 1).to_list(500)
        for t in items + overdue_prior:
            t["status"] = engine._derive_status(t, now)

        groups = {
            "overdue_critical": [],
            "due_now": [],
            "upcoming_next_4h": [],
            "later_today": [],
            "completed_today": [],
            "informational": [],
        }
        soon_cutoff = now + timedelta(hours=4)
        for t in overdue_prior + items:
            st = t["status"]
            prio = t.get("priority", "standard")
            sched = parse_iso(t["scheduled_at"])
            if prio == "informational":
                groups["informational"].append(t)
            elif st in ("completed", "skipped"):
                groups["completed_today"].append(t)
            elif st == "overdue" and prio == "critical":
                groups["overdue_critical"].append(t)
            elif st == "overdue":
                # treat non-critical overdue as due_now visually but still surface
                groups["due_now"].append(t)
            elif st == "due":
                groups["due_now"].append(t)
            elif sched <= soon_cutoff:
                groups["upcoming_next_4h"].append(t)
            else:
                groups["later_today"].append(t)
        return {"anchor_date": iso(start), "groups": groups,
                "counts": {k: len(v) for k, v in groups.items()}}

    @router.post("/tasks")
    async def create_task(body: AdHocTaskIn, user=Depends(get_current_user)):
        sched = parse_iso(body.scheduled_at)
        doc = {
            "id": new_id(),
            "tenant_id": DEFAULT_TENANT_ID,
            "template_id": None,
            "category": body.category,
            "title": body.title,
            "linked_horse_ids": body.linked_horse_ids,
            "linked_location_id": body.linked_location_id,
            "assignee_user_id": body.assignee_user_id,
            "assignee_role": body.assignee_role,
            "scheduled_at": iso(sched),
            "window_start": iso(sched - timedelta(minutes=body.window_minutes_before)),
            "window_end": iso(sched + timedelta(minutes=body.window_minutes_after)),
            "priority": body.priority,
            "status": "scheduled",
            "payload": body.payload,
            "notes": body.notes,
            "client_completion_id": None,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
        }
        await db.tasks.insert_one(doc)
        await engine.emit_event(
            tenant_id=DEFAULT_TENANT_ID,
            event_type="task.created",
            task=doc,
            actor_user_id=user["id"],
        )
        out = await db.tasks.find_one({"id": doc["id"]}, {"_id": 0})
        return {"task": out}

    @router.patch("/tasks/{task_id}")
    async def patch_task(task_id: str, body: TaskPatch, user=Depends(get_current_user)):
        existing = await db.tasks.find_one({"id": task_id, "tenant_id": DEFAULT_TENANT_ID}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Task not found")
        if existing.get("status") in ("completed", "cancelled"):
            raise HTTPException(400, "Cannot edit a completed or cancelled task; void first")
        updates: Dict[str, Any] = {"updated_at": iso(now_utc())}
        data = body.model_dump(exclude_unset=True)
        if "scheduled_at" in data and data["scheduled_at"]:
            sched = parse_iso(data["scheduled_at"])
            updates["scheduled_at"] = iso(sched)
            wb = int(existing.get("window_minutes_before", 30) or 30)
            wa = int(existing.get("window_minutes_after", 120) or 120)
            updates["window_start"] = iso(sched - timedelta(minutes=wb))
            updates["window_end"] = iso(sched + timedelta(minutes=wa))
        for f in ("title", "assignee_user_id", "assignee_role", "priority", "notes", "payload"):
            if f in data and data[f] is not None:
                updates[f] = data[f]
        await db.tasks.update_one({"id": task_id}, {"$set": updates})
        updated = await db.tasks.find_one({"id": task_id}, {"_id": 0})
        return {"task": updated}

    @router.post("/tasks/{task_id}/complete")
    async def complete(task_id: str, body: CompleteBody, user=Depends(get_current_user)):
        return await engine.complete_task(task_id, body, user)

    @router.post("/tasks/bulk-complete")
    async def bulk_complete(body: BulkCompleteBody, user=Depends(get_current_user)):
        results = []
        for item in body.items:
            try:
                comp = CompleteBody(
                    client_completion_id=item.client_completion_id,
                    completed_at=item.completed_at,
                    outcome=item.outcome,
                    payload_actual=item.payload_actual,
                    notes=item.notes or body.shared_note,
                )
                res = await engine.complete_task(item.task_id, comp, user)
                results.append({"task_id": item.task_id, "ok": True,
                                 "deduped": res.get("deduped", False)})
            except HTTPException as he:
                results.append({"task_id": item.task_id, "ok": False, "error": he.detail})
            except Exception as e:
                logger.exception("bulk complete failed for %s", item.task_id)
                results.append({"task_id": item.task_id, "ok": False, "error": str(e)})
        succeeded = sum(1 for r in results if r["ok"])
        return {"results": results, "succeeded": succeeded, "total": len(results)}

    @router.post("/tasks/{task_id}/skip")
    async def skip(task_id: str, body: SkipBody, user=Depends(get_current_user)):
        return await engine.skip_task(task_id, body, user)

    @router.post("/tasks/{task_id}/void")
    async def void(task_id: str, body: Dict[str, Any] = None, user=Depends(get_current_user)):
        reason = (body or {}).get("reason") if isinstance(body, dict) else None
        return await engine.void_completion(task_id, reason or "voided", user)

    @router.post("/tasks/{task_id}/reassign")
    async def reassign(task_id: str, body: ReassignBody, user=Depends(get_current_user)):
        existing = await db.tasks.find_one({"id": task_id, "tenant_id": DEFAULT_TENANT_ID}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Task not found")
        updates = {"updated_at": iso(now_utc())}
        data = body.model_dump(exclude_unset=True)
        if "assignee_user_id" in data:
            updates["assignee_user_id"] = data["assignee_user_id"]
        if "assignee_role" in data:
            updates["assignee_role"] = data["assignee_role"]
        await db.tasks.update_one({"id": task_id}, {"$set": updates})
        updated = await db.tasks.find_one({"id": task_id}, {"_id": 0})
        await engine.emit_event(
            tenant_id=DEFAULT_TENANT_ID,
            event_type="task.reassigned",
            task=updated,
            actor_user_id=user["id"],
            extra={"previous_assignee_user_id": existing.get("assignee_user_id")},
        )
        return {"task": updated}

    @router.post("/tasks/materialize")
    async def force_materialize(user=Depends(get_current_user)):
        n = await engine.materialize_all()
        return {"created": n}

    # -- timelines / activity -----------------------------------------
    @router.get("/horses/{horse_id}/timeline")
    async def horse_timeline(horse_id: str,
                              user=Depends(get_current_user),
                              limit: int = 100,
                              owner_view: bool = False):
        q: Dict[str, Any] = {
            "tenant_id": DEFAULT_TENANT_ID,
            "subject_horse_ids": horse_id,
        }
        if owner_view or user.get("role") == "horse_owner":
            q["event_type"] = {"$in": list(OWNER_VISIBLE_EVENT_TYPES)}
            q["category"] = {"$in": list(OWNER_VISIBLE_CATEGORIES)}
        items = await db.task_events.find(q, {"_id": 0}).sort("occurred_at", -1).to_list(min(limit, 500))
        return {"items": items}

    @router.get("/staff/{user_id}/activity")
    async def staff_activity(user_id: str, user=Depends(get_current_user), limit: int = 100):
        items = await db.task_events.find(
            {"tenant_id": DEFAULT_TENANT_ID, "actor_user_id": user_id},
            {"_id": 0},
        ).sort("occurred_at", -1).to_list(min(limit, 500))
        return {"items": items}

    # -- analytics rollup ---------------------------------------------
    @router.get("/tasks/analytics/summary")
    async def analytics_summary(user=Depends(get_current_user),
                                 days: int = 7):
        since = iso(now_utc() - timedelta(days=days))
        completions = await db.task_completions.count_documents(
            {"tenant_id": DEFAULT_TENANT_ID, "voided": {"$ne": True},
             "completed_at": {"$gte": since}}
        )
        overdue = 0
        live = await db.tasks.find(
            {"tenant_id": DEFAULT_TENANT_ID,
             "status": {"$nin": ["completed", "skipped", "cancelled"]}},
            {"_id": 0, "window_end": 1},
        ).to_list(2000)
        now = now_utc()
        for t in live:
            we = parse_iso(t["window_end"]) if t.get("window_end") else None
            if we and now > we:
                overdue += 1

        # per category counts over window
        pipeline = [
            {"$match": {"tenant_id": DEFAULT_TENANT_ID, "occurred_at": {"$gte": since}}},
            {"$group": {"_id": {"event_type": "$event_type", "category": "$category"},
                          "count": {"$sum": 1}}},
        ]
        agg = await db.task_events.aggregate(pipeline).to_list(200)
        by_event_category = [
            {"event_type": r["_id"].get("event_type"),
             "category": r["_id"].get("category"),
             "count": r["count"]}
            for r in agg
        ]
        return {
            "window_days": days,
            "completions": completions,
            "currently_overdue": overdue,
            "by_event_category": by_event_category,
        }

    return router


# ---------------------------------------------------------------------------
# Seeder — used by server.py at startup to ensure demo data exists
# ---------------------------------------------------------------------------

async def seed_demo_templates(db, owner_user_id: Optional[str] = None) -> Dict[str, int]:
    """Idempotent: only seeds if no templates exist."""
    existing = await db.task_templates.count_documents({"tenant_id": DEFAULT_TENANT_ID})
    if existing > 0:
        return {"templates_created": 0, "skipped": True}

    # fetch some horse ids to attach demo templates to
    horses = await db.horses.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(20)
    horse_ids = [h["id"] for h in horses]
    h1 = horse_ids[:3] if horse_ids else []
    h2 = horse_ids[3:6] if len(horse_ids) > 3 else h1

    # anchor today at 6 AM UTC as a stable demo anchor
    today_6am = now_utc().replace(hour=6, minute=0, second=0, microsecond=0)

    templates = [
        {
            "category": "feed", "title": "AM Grain",
            "description": "Morning grain across pasture A",
            "linked_horse_ids": h1,
            "default_assignee_role": "groom",
            "rrule": "FREQ=DAILY", "dtstart": iso(today_6am),
            "window_minutes_before": 30, "window_minutes_after": 120,
            "priority": "standard",
            "payload_defaults": {"feed_type": "Senior Mix", "amount": 2, "unit": "qt"},
        },
        {
            "category": "feed", "title": "PM Grain",
            "linked_horse_ids": h1,
            "default_assignee_role": "groom",
            "rrule": "FREQ=DAILY",
            "dtstart": iso(today_6am.replace(hour=17)),
            "priority": "standard",
            "payload_defaults": {"feed_type": "Senior Mix", "amount": 2, "unit": "qt"},
        },
        {
            "category": "medication", "title": "Bute 1g — Halo",
            "linked_horse_ids": h2[:1],
            "default_assignee_role": "groom",
            "rrule": "FREQ=DAILY", "dtstart": iso(today_6am.replace(hour=7)),
            "priority": "critical",
            "payload_defaults": {"med_name": "Phenylbutazone", "dose": 1, "unit": "g", "route": "oral"},
        },
        {
            "category": "turnout_out", "title": "AM Turnout",
            "linked_horse_ids": horse_ids,
            "default_assignee_role": "groom",
            "rrule": "FREQ=DAILY", "dtstart": iso(today_6am.replace(hour=8)),
            "priority": "standard",
            "payload_defaults": {"paddock_id": "paddock-a", "blanket": False, "fly_mask": True},
        },
        {
            "category": "turnout_in", "title": "PM Bring-in",
            "linked_horse_ids": horse_ids,
            "default_assignee_role": "groom",
            "rrule": "FREQ=DAILY", "dtstart": iso(today_6am.replace(hour=16)),
            "priority": "standard",
            "payload_defaults": {"paddock_id": "paddock-a"},
        },
        {
            "category": "stall_clean", "title": "Stall Pick",
            "linked_horse_ids": horse_ids,
            "default_assignee_role": "groom",
            "rrule": "FREQ=DAILY", "dtstart": iso(today_6am.replace(hour=10)),
            "priority": "informational",
            "payload_defaults": {"level": "pick"},
        },
        {
            "category": "farrier", "title": "Trim & Shoe (6-week cycle)",
            "linked_horse_ids": h2,
            "default_assignee_role": "barn_manager",
            "rrule": "FREQ=WEEKLY;INTERVAL=6;BYDAY=TU",
            "dtstart": iso(today_6am.replace(hour=11)),
            "priority": "standard",
            "payload_defaults": {"farrier_name": "Jordan A.", "shoes_on": ["fronts"]},
        },
        {
            "category": "vet", "title": "Spring Vaccinations",
            "linked_horse_ids": horse_ids,
            "default_assignee_role": "barn_manager",
            "rrule": None,
            "dtstart": iso(today_6am + timedelta(days=2, hours=3)),
            "priority": "standard",
            "payload_defaults": {"vet_name": "Dr. Maren", "reason": "Annual vaccines"},
        },
        {
            "category": "rehab", "title": "Hand-walk 20min",
            "linked_horse_ids": h2[:1],
            "default_assignee_role": "trainer",
            "rrule": "FREQ=DAILY;BYHOUR=9,14",
            "dtstart": iso(today_6am.replace(hour=9)),
            "priority": "standard",
            "payload_defaults": {"activity": "Hand-walking", "duration_min": 20, "intensity": "light"},
        },
    ]

    docs = []
    for t in templates:
        d = {
            "id": new_id(),
            "tenant_id": DEFAULT_TENANT_ID,
            "created_by": owner_user_id,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
            "active": True,
            "description": t.get("description"),
            "linked_location_id": None,
            "default_assignee_user_id": None,
            "window_minutes_before": t.get("window_minutes_before", 30),
            "window_minutes_after": t.get("window_minutes_after", 120),
            "payload_schema": {},
            **t,
        }
        docs.append(d)
    if docs:
        await db.task_templates.insert_many(docs)
    return {"templates_created": len(docs), "skipped": False}
