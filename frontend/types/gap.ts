/** Shared frontend types for gap analysis payloads. */
export type GapMetric = {
  metricName: string;
  claimScore: number;
  realWorldScore: number;
  delta: number;
};

export type GapAnalysisResponse = {
  drug_name?: string;
  drugName?: string;
  metrics: GapMetric[];
};
