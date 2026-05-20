import React from "react";
import {
  Building2, MapPin, Users, Cat, GraduationCap,
  UtensilsCrossed, Package, UserPlus, Calendar, Rocket,
} from "lucide-react";

/**
 * Shared metadata for onboarding steps. Used by Dashboard's "setup concierge"
 * card and the Onboarding wizard. Single source of truth for icons + labels.
 */
export const STEP_META = {
  barn:           { label: "Barn Profile",        icon: Building2 },
  locations:      { label: "Locations",           icon: MapPin },
  owners:         { label: "Owners & Clients",    icon: Users },
  horses:         { label: "Horse Profiles",      icon: Cat },
  riders:         { label: "Riders",              icon: GraduationCap },
  feed_templates: { label: "Feed Templates",      icon: UtensilsCrossed },
  inventory:      { label: "Inventory",           icon: Package },
  staff:          { label: "Team & Staff",        icon: UserPlus },
  schedules:      { label: "Recurring Schedules", icon: Calendar },
  review:         { label: "Review & Launch",     icon: Rocket },
};
