import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full border px-2 py-0.5 text-[12px] font-semibold", {
  variants: {
    variant: {
      default: "border-transparent bg-blue-600 text-white",
      secondary: "border-transparent bg-slate-100 text-slate-700",
      destructive: "border-transparent bg-red-500 text-white",
      success: "border-transparent bg-green-500 text-white",
      warning: "border-transparent bg-yellow-500 text-slate-900",
      outline: "border-slate-200 text-slate-700",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

export interface BadgeProps extends HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
