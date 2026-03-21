"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
}

export function Progress({ value, className, ...props }: ProgressProps) {
  const safeValue = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("relative h-2 w-full overflow-hidden rounded-full bg-slate-200", className)} {...props}>
      <div className="h-full bg-blue-600 transition-all" style={{ width: `${safeValue}%` }} />
    </div>
  );
}
