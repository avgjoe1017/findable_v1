"""Tests for the comparison engine module."""

import pytest

from worker.testing.comparison import (
    SiteComparison,
    ValidationMetrics,
    ValidationReport,
    calculate_metrics,
    compare_all,
    compare_site,
    generate_insights,
    generate_recommendations,
    get_site_citation_rate,
)
from worker.testing.corpus import SiteCategory, TestSite
from worker.testing.ground_truth import GroundTruthResult, ProviderResponse
from worker.testing.pipeline import PillarScores, PipelineResult


class TestSiteComparison:
    """Tests for SiteComparison dataclass."""

    def test_create_comparison(self):
        """SiteComparison can be created with all fields."""
        comparison = SiteComparison(
            site_url="https://moz.com",
            site_name="Moz",
            site_domain="moz.com",
            site_category="known_cited",
            predicted_score=75.0,
            predicted_findable=True,
            prediction_confidence="high",
            queries_analyzed=10,
            queries_cited=7,
            citation_rate=0.7,
            actually_cited=True,
            prediction_correct=True,
            prediction_type="true_positive",
            score_vs_citation_delta=5.0,
        )

        assert comparison.site_domain == "moz.com"
        assert comparison.predicted_findable is True
        assert comparison.prediction_type == "true_positive"

    def test_roundtrip_serialization(self):
        """SiteComparison survives roundtrip serialization."""
        original = SiteComparison(
            site_url="https://test.com",
            site_name="Test",
            site_domain="test.com",
            site_category="competitor",
            predicted_score=60.0,
            predicted_findable=True,
            prediction_confidence="medium",
            queries_analyzed=5,
            queries_cited=2,
            citation_rate=0.4,
            actually_cited=True,
            prediction_correct=True,
            prediction_type="true_positive",
            score_vs_citation_delta=20.0,
        )

        data = original.to_dict()
        restored = SiteComparison.from_dict(data)

        assert restored.site_domain == original.site_domain
        assert restored.predicted_score == original.predicted_score
        assert restored.prediction_type == original.prediction_type


class TestValidationMetrics:
    """Tests for ValidationMetrics dataclass."""

    def test_create_metrics(self):
        """ValidationMetrics can be created with all fields."""
        metrics = ValidationMetrics(
            total_sites=20,
            sites_with_predictions=18,
            sites_with_ground_truth=20,
            sites_compared=18,
            true_positives=8,
            true_negatives=6,
            false_positives=2,
            false_negatives=2,
            accuracy=0.78,
            precision=0.80,
            recall=0.80,
            f1_score=0.80,
            optimism_rate=0.11,
            pessimism_rate=0.11,
            score_citation_correlation=0.65,
            mean_absolute_error=12.5,
        )

        assert metrics.total_sites == 20
        assert metrics.accuracy == 0.78
        assert metrics.f1_score == 0.80

    def test_roundtrip_serialization(self):
        """ValidationMetrics survives roundtrip serialization."""
        original = ValidationMetrics(
            total_sites=10,
            sites_with_predictions=10,
            sites_with_ground_truth=10,
            sites_compared=10,
            true_positives=5,
            true_negatives=3,
            false_positives=1,
            false_negatives=1,
            accuracy=0.8,
            precision=0.83,
            recall=0.83,
            f1_score=0.83,
            optimism_rate=0.1,
            pessimism_rate=0.1,
            score_citation_correlation=0.7,
            mean_absolute_error=10.0,
        )

        data = original.to_dict()
        restored = ValidationMetrics.from_dict(data)

        assert restored.total_sites == original.total_sites
        assert restored.accuracy == original.accuracy


class TestGetSiteCitationRate:
    """Tests for get_site_citation_rate function."""

    def test_calculates_citation_rate(self):
        """Calculates correct citation rate."""
        ground_truth = [
            GroundTruthResult(
                query="q1",
                query_id="1",
                category="informational",
                all_cited_domains=["moz.com", "ahrefs.com"],
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
            GroundTruthResult(
                query="q2",
                query_id="2",
                category="informational",
                all_cited_domains=["moz.com"],
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
            GroundTruthResult(
                query="q3",
                query_id="3",
                category="informational",
                all_cited_domains=["semrush.com"],
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
        ]

        analyzed, cited, rate = get_site_citation_rate("moz.com", ground_truth)

        assert analyzed == 3
        assert cited == 2
        assert rate == pytest.approx(0.667, rel=0.01)

    def test_handles_subdomain_matching(self):
        """Matches subdomains correctly."""
        ground_truth = [
            GroundTruthResult(
                query="q1",
                query_id="1",
                category="informational",
                all_cited_domains=["blog.moz.com"],
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
        ]

        analyzed, cited, rate = get_site_citation_rate("moz.com", ground_truth)

        assert cited == 1  # Should match blog.moz.com

    def test_ignores_error_responses(self):
        """Ignores queries where all providers errored."""
        ground_truth = [
            GroundTruthResult(
                query="q1",
                query_id="1",
                category="informational",
                all_cited_domains=["moz.com"],
                provider_responses=[
                    ProviderResponse(provider="mock", model="", response_text="", error="API error")
                ],
            ),
            GroundTruthResult(
                query="q2",
                query_id="2",
                category="informational",
                all_cited_domains=["moz.com"],
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
        ]

        analyzed, cited, rate = get_site_citation_rate("moz.com", ground_truth)

        assert analyzed == 1  # Only the non-error query


class TestCompareSite:
    """Tests for compare_site function."""

    def test_true_positive(self):
        """Correctly identifies true positive."""
        site = TestSite(
            url="https://moz.com",
            name="Moz",
            category=SiteCategory.KNOWN_CITED,
        )
        pipeline = PipelineResult(
            url="https://moz.com",
            domain="moz.com",
            status="success",
            overall_score=75.0,
            pillar_scores=PillarScores(),
        )
        ground_truth = [
            GroundTruthResult(
                query="q1",
                query_id="1",
                category="informational",
                all_cited_domains=["moz.com"],
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
        ]

        comparison = compare_site(
            site, pipeline, ground_truth, findable_threshold=50.0, citation_threshold=0.1
        )

        assert comparison is not None
        assert comparison.prediction_type == "true_positive"
        assert comparison.prediction_correct is True

    def test_true_negative(self):
        """Correctly identifies true negative."""
        site = TestSite(
            url="https://unknown.com",
            name="Unknown",
            category=SiteCategory.KNOWN_UNCITED,
        )
        pipeline = PipelineResult(
            url="https://unknown.com",
            domain="unknown.com",
            status="success",
            overall_score=30.0,
            pillar_scores=PillarScores(),
        )
        ground_truth = [
            GroundTruthResult(
                query="q1",
                query_id="1",
                category="informational",
                all_cited_domains=["moz.com"],  # unknown.com not cited
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
        ]

        comparison = compare_site(
            site, pipeline, ground_truth, findable_threshold=50.0, citation_threshold=0.1
        )

        assert comparison is not None
        assert comparison.prediction_type == "true_negative"
        assert comparison.prediction_correct is True

    def test_false_positive(self):
        """Correctly identifies false positive (optimistic)."""
        site = TestSite(
            url="https://overrated.com",
            name="Overrated",
            category=SiteCategory.COMPETITOR,
        )
        pipeline = PipelineResult(
            url="https://overrated.com",
            domain="overrated.com",
            status="success",
            overall_score=80.0,  # High score
            pillar_scores=PillarScores(),
        )
        ground_truth = [
            GroundTruthResult(
                query="q1",
                query_id="1",
                category="informational",
                all_cited_domains=["moz.com"],  # overrated.com not cited
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
        ]

        comparison = compare_site(
            site, pipeline, ground_truth, findable_threshold=50.0, citation_threshold=0.1
        )

        assert comparison is not None
        assert comparison.prediction_type == "false_positive"
        assert comparison.prediction_correct is False

    def test_false_negative(self):
        """Correctly identifies false negative (pessimistic)."""
        site = TestSite(
            url="https://underrated.com",
            name="Underrated",
            category=SiteCategory.KNOWN_CITED,
        )
        pipeline = PipelineResult(
            url="https://underrated.com",
            domain="underrated.com",
            status="success",
            overall_score=30.0,  # Low score
            pillar_scores=PillarScores(),
        )
        ground_truth = [
            GroundTruthResult(
                query="q1",
                query_id="1",
                category="informational",
                all_cited_domains=["underrated.com"],  # Actually cited!
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
        ]

        comparison = compare_site(
            site, pipeline, ground_truth, findable_threshold=50.0, citation_threshold=0.1
        )

        assert comparison is not None
        assert comparison.prediction_type == "false_negative"
        assert comparison.prediction_correct is False

    def test_returns_none_without_ground_truth(self):
        """Returns None when no ground truth data."""
        site = TestSite(
            url="https://test.com",
            name="Test",
            category=SiteCategory.OWN_PROPERTY,
        )
        pipeline = PipelineResult(
            url="https://test.com",
            domain="test.com",
            status="success",
            overall_score=60.0,
            pillar_scores=PillarScores(),
        )

        comparison = compare_site(site, pipeline, [], findable_threshold=50.0)

        assert comparison is None


class TestCalculateMetrics:
    """Tests for calculate_metrics function."""

    def test_calculates_correct_accuracy(self):
        """Calculates correct accuracy metric."""
        comparisons = [
            SiteComparison(
                site_url="a.com",
                site_name="A",
                site_domain="a.com",
                site_category="known_cited",
                predicted_score=80,
                predicted_findable=True,
                prediction_confidence="high",
                queries_analyzed=10,
                queries_cited=8,
                citation_rate=0.8,
                actually_cited=True,
                prediction_correct=True,
                prediction_type="true_positive",
                score_vs_citation_delta=0,
            ),
            SiteComparison(
                site_url="b.com",
                site_name="B",
                site_domain="b.com",
                site_category="known_uncited",
                predicted_score=30,
                predicted_findable=False,
                prediction_confidence="low",
                queries_analyzed=10,
                queries_cited=0,
                citation_rate=0.0,
                actually_cited=False,
                prediction_correct=True,
                prediction_type="true_negative",
                score_vs_citation_delta=30,
            ),
            SiteComparison(
                site_url="c.com",
                site_name="C",
                site_domain="c.com",
                site_category="competitor",
                predicted_score=70,
                predicted_findable=True,
                prediction_confidence="high",
                queries_analyzed=10,
                queries_cited=0,
                citation_rate=0.0,
                actually_cited=False,
                prediction_correct=False,
                prediction_type="false_positive",
                score_vs_citation_delta=70,
            ),
            SiteComparison(
                site_url="d.com",
                site_name="D",
                site_domain="d.com",
                site_category="known_cited",
                predicted_score=40,
                predicted_findable=False,
                prediction_confidence="low",
                queries_analyzed=10,
                queries_cited=8,
                citation_rate=0.8,
                actually_cited=True,
                prediction_correct=False,
                prediction_type="false_negative",
                score_vs_citation_delta=-40,
            ),
        ]

        metrics = calculate_metrics(comparisons)

        assert metrics.total_sites == 4
        assert metrics.true_positives == 1
        assert metrics.true_negatives == 1
        assert metrics.false_positives == 1
        assert metrics.false_negatives == 1
        assert metrics.accuracy == 0.5  # 2 correct out of 4

    def test_handles_empty_list(self):
        """Handles empty comparisons list."""
        metrics = calculate_metrics([])

        assert metrics.total_sites == 0
        assert metrics.accuracy == 0.0

    def test_calculates_precision_recall(self):
        """Calculates precision and recall correctly."""
        # 3 TP, 1 FP, 1 FN
        comparisons = [
            SiteComparison(
                site_url=f"{i}.com",
                site_name=str(i),
                site_domain=f"{i}.com",
                site_category="known_cited",
                predicted_score=80,
                predicted_findable=True,
                prediction_confidence="high",
                queries_analyzed=10,
                queries_cited=8,
                citation_rate=0.8,
                actually_cited=True,
                prediction_correct=True,
                prediction_type="true_positive",
                score_vs_citation_delta=0,
            )
            for i in range(3)
        ] + [
            SiteComparison(
                site_url="fp.com",
                site_name="FP",
                site_domain="fp.com",
                site_category="competitor",
                predicted_score=70,
                predicted_findable=True,
                prediction_confidence="high",
                queries_analyzed=10,
                queries_cited=0,
                citation_rate=0.0,
                actually_cited=False,
                prediction_correct=False,
                prediction_type="false_positive",
                score_vs_citation_delta=70,
            ),
            SiteComparison(
                site_url="fn.com",
                site_name="FN",
                site_domain="fn.com",
                site_category="known_cited",
                predicted_score=30,
                predicted_findable=False,
                prediction_confidence="low",
                queries_analyzed=10,
                queries_cited=8,
                citation_rate=0.8,
                actually_cited=True,
                prediction_correct=False,
                prediction_type="false_negative",
                score_vs_citation_delta=-50,
            ),
        ]

        metrics = calculate_metrics(comparisons)

        # Precision = TP / (TP + FP) = 3 / 4 = 0.75
        assert metrics.precision == 0.75

        # Recall = TP / (TP + FN) = 3 / 4 = 0.75
        assert metrics.recall == 0.75


class TestGenerateInsights:
    """Tests for generate_insights function."""

    def test_generates_accuracy_insight(self):
        """Generates accuracy-based insights."""
        metrics = ValidationMetrics(
            total_sites=10,
            sites_with_predictions=10,
            sites_with_ground_truth=10,
            sites_compared=10,
            true_positives=8,
            true_negatives=0,
            false_positives=1,
            false_negatives=1,
            accuracy=0.8,
            precision=0.89,
            recall=0.89,
            f1_score=0.89,
            optimism_rate=0.1,
            pessimism_rate=0.1,
            score_citation_correlation=0.7,
            mean_absolute_error=10.0,
        )

        insights = generate_insights(metrics, [])

        assert any("accuracy" in i.lower() for i in insights)

    def test_detects_optimism_bias(self):
        """Detects optimism bias."""
        metrics = ValidationMetrics(
            total_sites=10,
            sites_with_predictions=10,
            sites_with_ground_truth=10,
            sites_compared=10,
            true_positives=3,
            true_negatives=2,
            false_positives=4,
            false_negatives=1,
            accuracy=0.5,
            precision=0.43,
            recall=0.75,
            f1_score=0.55,
            optimism_rate=0.4,
            pessimism_rate=0.1,  # High optimism
            score_citation_correlation=0.5,
            mean_absolute_error=20.0,
        )

        insights = generate_insights(metrics, [])

        assert any("optimism" in i.lower() for i in insights)


class TestGenerateRecommendations:
    """Tests for generate_recommendations function."""

    def test_recommends_raising_threshold(self):
        """Recommends raising threshold when too many false positives."""
        metrics = ValidationMetrics(
            total_sites=10,
            sites_with_predictions=10,
            sites_with_ground_truth=10,
            sites_compared=10,
            true_positives=3,
            true_negatives=2,
            false_positives=4,
            false_negatives=1,  # FP >> FN
            accuracy=0.5,
            precision=0.43,
            recall=0.75,
            f1_score=0.55,
            optimism_rate=0.4,
            pessimism_rate=0.1,
            score_citation_correlation=0.5,
            mean_absolute_error=20.0,
        )

        recs = generate_recommendations(metrics, [])

        assert any("raising" in r.lower() or "threshold" in r.lower() for r in recs)

    def test_recommends_sample_size(self):
        """Recommends larger sample size when too few comparisons."""
        metrics = ValidationMetrics(
            total_sites=5,
            sites_with_predictions=5,
            sites_with_ground_truth=5,
            sites_compared=5,
            true_positives=3,
            true_negatives=1,
            false_positives=1,
            false_negatives=0,
            accuracy=0.8,
            precision=0.75,
            recall=1.0,
            f1_score=0.86,
            optimism_rate=0.2,
            pessimism_rate=0.0,
            score_citation_correlation=0.6,
            mean_absolute_error=15.0,
        )

        recs = generate_recommendations(metrics, [])

        assert any("corpus" in r.lower() or "sample" in r.lower() for r in recs)


class TestCompareAll:
    """Tests for compare_all function."""

    def test_generates_validation_report(self):
        """Generates a complete validation report."""
        sites = [
            TestSite(url="https://moz.com", name="Moz", category=SiteCategory.KNOWN_CITED),
            TestSite(
                url="https://unknown.com", name="Unknown", category=SiteCategory.KNOWN_UNCITED
            ),
        ]
        pipeline_results = [
            PipelineResult(
                url="https://moz.com",
                domain="moz.com",
                status="success",
                overall_score=80.0,
                pillar_scores=PillarScores(),
            ),
            PipelineResult(
                url="https://unknown.com",
                domain="unknown.com",
                status="success",
                overall_score=30.0,
                pillar_scores=PillarScores(),
            ),
        ]
        ground_truth = [
            GroundTruthResult(
                query="q1",
                query_id="1",
                category="informational",
                all_cited_domains=["moz.com"],
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
        ]

        report = compare_all(
            sites=sites,
            pipeline_results=pipeline_results,
            ground_truth_results=ground_truth,
            run_id="test-run",
            corpus_name="test",
        )

        assert report.run_id == "test-run"
        assert report.corpus_name == "test"
        assert len(report.site_comparisons) == 2
        assert report.metrics is not None
        assert report.metrics.sites_compared == 2

    def test_calculates_category_metrics(self):
        """Calculates metrics by category."""
        sites = [
            TestSite(url="https://moz.com", name="Moz", category=SiteCategory.KNOWN_CITED),
            TestSite(
                url="https://competitor.com", name="Competitor", category=SiteCategory.COMPETITOR
            ),
        ]
        pipeline_results = [
            PipelineResult(
                url="https://moz.com",
                domain="moz.com",
                status="success",
                overall_score=70.0,
                pillar_scores=PillarScores(),
            ),
            PipelineResult(
                url="https://competitor.com",
                domain="competitor.com",
                status="success",
                overall_score=60.0,
                pillar_scores=PillarScores(),
            ),
        ]
        ground_truth = [
            GroundTruthResult(
                query="q1",
                query_id="1",
                category="informational",
                all_cited_domains=["moz.com", "competitor.com"],
                provider_responses=[ProviderResponse(provider="mock", model="", response_text="")],
            ),
        ]

        report = compare_all(
            sites=sites,
            pipeline_results=pipeline_results,
            ground_truth_results=ground_truth,
            run_id="test",
        )

        assert "known_cited" in report.metrics_by_category
        assert "competitor" in report.metrics_by_category

    def test_roundtrip_serialization(self):
        """ValidationReport survives roundtrip serialization."""
        original = ValidationReport(
            run_id="test-run",
            corpus_name="test",
            total_sites=2,
            total_queries=5,
            metrics=ValidationMetrics(
                total_sites=2,
                sites_with_predictions=2,
                sites_with_ground_truth=2,
                sites_compared=2,
                true_positives=1,
                true_negatives=1,
                false_positives=0,
                false_negatives=0,
                accuracy=1.0,
                precision=1.0,
                recall=1.0,
                f1_score=1.0,
                optimism_rate=0.0,
                pessimism_rate=0.0,
                score_citation_correlation=0.9,
                mean_absolute_error=5.0,
            ),
            insights=["Good accuracy!"],
            recommendations=["Continue monitoring"],
        )

        data = original.to_dict()
        restored = ValidationReport.from_dict(data)

        assert restored.run_id == original.run_id
        assert restored.metrics.accuracy == original.metrics.accuracy
        assert restored.insights == original.insights
