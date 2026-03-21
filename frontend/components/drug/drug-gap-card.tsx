/** KPI card summarizing claim versus real-world score for a drug. */
import type { GapMetric } from "@/types/gap";

type DrugGapCardProps = {
  drugName: string;
  claimScore: number;
  realWorldScore: number;
};

export function DrugGapCard({ drugName, claimScore, realWorldScore }: DrugGapCardProps) {
  const metric: GapMetric = {
    metricName: "efficacy-perception-gap",
    claimScore,
    realWorldScore,
    delta: claimScore - realWorldScore,
  };

  return (
    <article className="rounded-lg border border-ink/10 bg-panel p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-ink">{drugName}</h2>
      <p className="mt-2 text-sm text-ink/70">Claim: {metric.claimScore.toFixed(2)}</p>
      <p className="text-sm text-ink/70">Real-world: {metric.realWorldScore.toFixed(2)}</p>
      <p className="mt-2 text-sm font-semibold text-accent">Delta: {metric.delta.toFixed(2)}</p>
    </article>
  );
}
