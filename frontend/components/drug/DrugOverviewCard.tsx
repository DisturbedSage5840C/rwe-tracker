import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function DrugOverviewCard({
  perceptionScore,
  trialScore,
  gapScore,
  isLoading,
}: {
  perceptionScore: number;
  trialScore: number;
  gapScore: number;
  isLoading: boolean;
}) {
  if (isLoading) {
    return <Skeleton className="h-[180px] w-full" />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Overall Perception</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-3 gap-4">
        <div>
          <p className="text-[12px] text-slate-500">Perception score</p>
          <p className="text-2xl font-semibold text-blue-600">{(perceptionScore * 100).toFixed(2)}%</p>
        </div>
        <div>
          <p className="text-[12px] text-slate-500">Clinical score</p>
          <p className="text-2xl font-semibold text-green-600">{(trialScore * 100).toFixed(2)}%</p>
        </div>
        <div>
          <p className="text-[12px] text-slate-500">Gap score</p>
          <p className="text-2xl font-semibold text-red-500">{(gapScore * 100).toFixed(2)}%</p>
        </div>
      </CardContent>
    </Card>
  );
}
