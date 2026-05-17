import React from "react";
import { PageHeader, Card } from "../components/Primitives";
import { Sparkles } from "lucide-react";

export default function Placeholder({ title, eyebrow = "Coming soon", description }) {
  return (
    <div data-testid={`placeholder-${title.toLowerCase().replace(/\s/g, '-')}`}>
      <PageHeader eyebrow={eyebrow} title={title} subtitle={description} />
      <Card hover={false} className="text-center py-16">
        <Sparkles strokeWidth={1.4} className="mx-auto mb-4 text-equine-champagne" />
        <h3 className="font-display text-3xl mb-2">This module is in the next release</h3>
        <p className="text-equine-platinum/60 max-w-lg mx-auto">
          The {title} workspace is queued for the next iteration. The data model and demo seeds are already in place — UI is ready to be wired in.
        </p>
      </Card>
    </div>
  );
}
