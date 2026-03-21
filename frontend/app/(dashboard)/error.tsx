"use client";

import { Button } from "@/components/ui/button";

export default function DashboardSegmentError({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="p-8">
      <h2 className="text-xl font-semibold text-slate-900">Unable to render dashboard segment</h2>
      <p className="mt-2 text-[13px] text-slate-600">Try reloading this view.</p>
      <Button aria-label="Retry dashboard" className="mt-4" onClick={() => reset()}>
        Retry
      </Button>
    </main>
  );
}
