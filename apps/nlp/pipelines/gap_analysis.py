"""Gap analysis pipeline comparing clinical claims to real-world signals."""

from __future__ import annotations

import math

from scipy.stats import t, ttest_1samp

from apps.nlp.schemas import GapDimension, GapReport, Insight


class GapAnalysisPipeline:
    """Statistical gap analysis pipeline for trial-vs-reality dimensions."""

    def __init__(self, dimension_weights: dict[str, float] | None = None) -> None:
        self.dimension_weights = dimension_weights or {
            "efficacy": 0.25,
            "safety": 0.2,
            "tolerability": 0.15,
            "convenience": 0.1,
            "quality_of_life": 0.15,
            "adherence": 0.1,
            "trust": 0.05,
        }

        self.recommendations = {
            "efficacy": "Review endpoint alignment and communication of responder subgroups in field messaging.",
            "safety": "Strengthen safety surveillance communication with explicit risk mitigation guidance.",
            "tolerability": "Prioritize side-effect management kits and physician counseling workflows.",
            "convenience": "Evaluate dosing schedule simplification and patient support logistics.",
            "quality_of_life": "Add patient-reported outcomes emphasis to medical affairs narrative.",
            "adherence": "Launch adherence nudges and refill coaching through patient support programs.",
            "trust": "Increase transparency by publishing plain-language evidence updates.",
        }

    async def analyze_drug(
        self,
        drug_id: str,
        clinical_data: dict,
        patient_reviews: list[dict],
        social_mentions: list[dict],
    ) -> GapReport:
        """Generate full gap report from clinical and real-world aggregates."""
        dimensions: list[GapDimension] = []

        for dimension, clinical_score in clinical_data.items():
            rw_scores = self._collect_dimension_scores(dimension, patient_reviews, social_mentions)
            if not rw_scores:
                rw_scores = [0.0]
            dimensions.append(self._calculate_gap(dimension, float(clinical_score), rw_scores))

        insights = self._generate_insights(dimensions)
        overall_score = self._calculate_overall_score(dimensions)
        return GapReport(drug_id=drug_id, dimensions=dimensions, overall_score=overall_score, insights=insights)

    def _calculate_gap(self, dimension: str, clinical_score: float, rw_scores: list[float]) -> GapDimension:
        """Calculate gap statistics with one-sample t-test and confidence interval."""
        n = len(rw_scores)
        rw_mean = float(sum(rw_scores) / n) if n else 0.0
        gap_magnitude = float(clinical_score - rw_mean)

        if n > 1:
            t_stat, p_value = ttest_1samp(rw_scores, popmean=clinical_score)
            stderr = float((sum((x - rw_mean) ** 2 for x in rw_scores) / (n - 1)) ** 0.5 / math.sqrt(n))
            ci_lower, ci_upper = t.interval(0.95, df=n - 1, loc=rw_mean, scale=stderr)
        else:
            p_value = 1.0
            ci_lower = rw_mean
            ci_upper = rw_mean

        significant = bool((p_value < 0.05) and (abs(gap_magnitude) > 0.15))

        return GapDimension(
            dimension=dimension,
            clinical_score=clinical_score,
            real_world_mean=rw_mean,
            gap_magnitude=gap_magnitude,
            p_value=float(p_value),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            significant=significant,
        )

    def _generate_insights(self, gaps: list[GapDimension]) -> list[Insight]:
        """Create severity-ranked actionable insights from significant dimensions."""
        insights: list[Insight] = []
        for gap in gaps:
            if not gap.significant:
                continue
            magnitude = abs(gap.gap_magnitude)
            if magnitude > 0.5 and gap.p_value < 0.01:
                severity = "critical"
            elif magnitude > 0.3 and gap.p_value < 0.05:
                severity = "high"
            else:
                severity = "moderate"

            recommendation = self.recommendations.get(
                gap.dimension,
                "Review cross-functional evidence strategy for this dimension.",
            )
            insights.append(
                Insight(
                    dimension=gap.dimension,
                    severity=severity,
                    recommendation=recommendation,
                )
            )
        return insights

    def _calculate_overall_score(self, gaps: list[GapDimension]) -> float:
        """Compute weighted overall gap pressure score across dimensions."""
        weighted_sum = 0.0
        weight_total = 0.0
        for gap in gaps:
            weight = self.dimension_weights.get(gap.dimension, 0.0)
            weighted_sum += abs(gap.gap_magnitude) * weight
            weight_total += weight
        if weight_total == 0:
            return 0.0
        return float(weighted_sum / weight_total)

    @staticmethod
    def _collect_dimension_scores(dimension: str, patient_reviews: list[dict], social_mentions: list[dict]) -> list[float]:
        """Collect dimension score samples from review and social payloads."""
        combined = patient_reviews + social_mentions
        scores: list[float] = []
        for item in combined:
            value = item.get(dimension)
            if isinstance(value, (int, float)):
                scores.append(float(value))
        return scores
