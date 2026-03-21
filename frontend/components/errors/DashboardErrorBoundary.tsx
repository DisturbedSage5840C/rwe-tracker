"use client";

import { Component, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type Props = {
  children: ReactNode;
};

type State = {
  hasError: boolean;
  message: string;
};

export class DashboardErrorBoundary extends Component<Props, State> {
  public constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  public static getDerivedStateFromError(error: unknown): State {
    return { hasError: true, message: error instanceof Error ? error.message : "Unexpected dashboard error" };
  }

  public render() {
    if (this.state.hasError) {
      return (
        <Card className="mx-auto mt-8 max-w-3xl">
          <CardHeader>
            <CardTitle>Dashboard failed to load</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-[13px] text-slate-600">{this.state.message}</p>
            <Button aria-label="Reload dashboard" onClick={() => window.location.reload()}>
              Reload
            </Button>
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}
