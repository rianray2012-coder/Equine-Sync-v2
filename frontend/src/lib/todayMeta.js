/**
 * Shared static metadata for the unified "Today" view. Extracted so that
 * future filtered surfaces (Rehab, Turnout, etc.) can render the same
 * iconography + tones without duplicating the catalogue.
 */
import {
  UtensilsCrossed, Pill, Trees, BedDouble, Hammer, Stethoscope, Activity, Circle,
} from "lucide-react";

export const CATEGORY_META = {
  feed:        { label: "Feed",       icon: UtensilsCrossed, accent: "saddle" },
  medication:  { label: "Medication", icon: Pill,            accent: "critical" },
  turnout_out: { label: "Turnout",    icon: Trees,           accent: "info" },
  turnout_in:  { label: "Bring-in",   icon: Trees,           accent: "info" },
  stall_clean: { label: "Stall",      icon: BedDouble,       accent: "neutral" },
  farrier:     { label: "Farrier",    icon: Hammer,          accent: "brass" },
  vet:         { label: "Vet",        icon: Stethoscope,     accent: "warning" },
  rehab:       { label: "Rehab",      icon: Activity,        accent: "brass" },
  custom:      { label: "Task",       icon: Circle,          accent: "neutral" },
};

export const GROUP_META = {
  overdue_critical: { label: "Overdue · Critical",       tone: "critical",  always: true },
  due_now:          { label: "Due now",                  tone: "warning",   always: true },
  upcoming_next_4h: { label: "Upcoming · next 4 hours",  tone: "info",      always: true },
  later_today:      { label: "Later today",              tone: "neutral",   collapsed: true },
  completed_today:  { label: "Completed today",          tone: "success",   collapsed: true },
  informational:    { label: "Informational",            tone: "neutral",   collapsed: true },
};

export const GROUP_ORDER = [
  "overdue_critical",
  "due_now",
  "upcoming_next_4h",
  "later_today",
  "completed_today",
  "informational",
];
