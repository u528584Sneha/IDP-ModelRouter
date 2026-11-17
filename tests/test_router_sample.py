"""
Sample test implementation for Image Model Router.

This file demonstrates how to implement the test cases defined in test_cases.xlsx.
Reference: Test Cases Overview sheet, TC001-TC014 (Router Core tests)

Usage:
    pytest tests/test_router_sample.py -v
"""

import pytest
import sys
from pathlib import Path
from typing import Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import modules under test
from cli_tools.tools.image_model_routing.router import (
    ModelCard,
    _estimate_cost,
    _hard_filter,
    _normalize,
    _score,
    _predict_quality,
    _adapt_weights,
    _select_top_models,
    _build_reasoning,
    get_weight_profile,
    NoEligibleModelError,
    route
)


# ===========================
# Fixtures
# ===========================

@pytest.fixture
def sample_model_card():
    """Create a basic ModelCard for testing.

    Used in: TC008, TC020-TC022
    """
    return ModelCard(
        model_id="test-model-1",
        provider="TestProvider",
        supports_vision=True,
        quality=0.85,
        cost_per_1m_input_tokens_usd=3.0,
        cost_per_1m_output_tokens_usd=15.0,
        cost_is_placeholder=False,
        latency_ms=1500.0,
        context_window=128000,
        max_output_tokens=4096,
        reliability=0.98,
        notes="Test model"
    )


@pytest.fixture
def multiple_model_cards():
    """Create multiple ModelCards with varying attributes.

    Used in: TC004-TC007, TC009-TC013
    """
    return [
        ModelCard(
            model_id="high-quality-model",
            provider="ProviderA",
            supports_vision=True,
            quality=0.95,
            cost_per_1m_input_tokens_usd=5.0,
            cost_per_1m_output_tokens_usd=20.0,
            cost_is_placeholder=False,
            latency_ms=2000.0,
            context_window=200000,
            max_output_tokens=8192,
            reliability=0.99
        ),
        ModelCard(
            model_id="balanced-model",
            provider="ProviderB",
            supports_vision=True,
            quality=0.85,
            cost_per_1m_input_tokens_usd=3.0,
            cost_per_1m_output_tokens_usd=12.0,
            cost_is_placeholder=False,
            latency_ms=1200.0,
            context_window=128000,
            max_output_tokens=4096,
            reliability=0.98
        ),
        ModelCard(
            model_id="cost-effective-model",
            provider="ProviderC",
            supports_vision=True,
            quality=0.75,
            cost_per_1m_input_tokens_usd=1.0,
            cost_per_1m_output_tokens_usd=5.0,
            cost_is_placeholder=False,
            latency_ms=800.0,
            context_window=64000,
            max_output_tokens=2048,
            reliability=0.95
        ),
        ModelCard(
            model_id="low-quality-model",
            provider="ProviderD",
            supports_vision=True,
            quality=0.60,
            cost_per_1m_input_tokens_usd=0.5,
            cost_per_1m_output_tokens_usd=2.0,
            cost_is_placeholder=False,
            latency_ms=500.0,
            context_window=32000,
            max_output_tokens=1024,
            reliability=0.90
        ),
    ]


# ===========================
# Unit Tests: Cost Estimation
# ===========================

class TestCostEstimation:
    """Test cases for _estimate_cost function.

    Reference: TC008
    """

    def test_basic_cost_calculation(self, sample_model_card):
        """TC008: Test cost estimation formula accuracy.

        Formula: cost = (input_tokens/1e6)*cost_input + (output_tokens/1e6)*cost_output
        """
        input_tokens = 1000
        expected_output_tokens = 500

        # Expected: (1000/1e6)*3.0 + (500/1e6)*15.0
        # = 0.003 + 0.0075 = 0.0105
        expected_cost = 0.0105

        result = _estimate_cost(sample_model_card, input_tokens, expected_output_tokens)

        assert abs(result - expected_cost) < 0.000001, \
            f"Cost calculation incorrect: got {result}, expected {expected_cost}"

    def test_cost_with_zero_input_tokens(self, sample_model_card):
        """TC053: Test cost estimation with zero input tokens."""
        result = _estimate_cost(sample_model_card, 0, 500)

        # Only output cost: (500/1e6)*15.0 = 0.0075
        expected = 0.0075
        assert abs(result - expected) < 0.000001

    def test_cost_with_zero_output_tokens(self, sample_model_card):
        """Test cost estimation with zero output tokens."""
        result = _estimate_cost(sample_model_card, 1000, 0)

        # Only input cost: (1000/1e6)*3.0 = 0.003
        expected = 0.003
        assert abs(result - expected) < 0.000001

    def test_cost_with_large_token_counts(self, sample_model_card):
        """TC054: Test cost estimation with very large token counts."""
        input_tokens = 100000
        expected_output_tokens = 50000

        # (100000/1e6)*3.0 + (50000/1e6)*15.0 = 0.3 + 0.75 = 1.05
        expected_cost = 1.05

        result = _estimate_cost(sample_model_card, input_tokens, expected_output_tokens)

        assert abs(result - expected_cost) < 0.000001


# ===========================
# Unit Tests: Hard Filtering
# ===========================

class TestHardFilter:
    """Test cases for _hard_filter function.

    Reference: TC004-TC007
    """

    def test_quality_floor_filter(self, multiple_model_cards):
        """TC004: Test that models below quality floor are filtered out."""
        quality_floor = 0.80
        input_tokens = 1000
        expected_output_tokens = 500

        result = _hard_filter(
            multiple_model_cards,
            quality_floor,
            input_tokens,
            expected_output_tokens
        )

        # Should filter out: low-quality-model (0.60) and cost-effective-model (0.75)
        # Should keep: high-quality-model (0.95) and balanced-model (0.85)
        assert len(result['eligible']) == 2
        assert len(result['filtered_out']) == 2

        eligible_qualities = [card.quality for card in result['eligible']]
        assert all(q >= quality_floor for q in eligible_qualities)

        # Check filtered out reasons
        filtered_reasons = [f['reason'] for f in result['filtered_out']]
        assert all('quality' in reason for reason in filtered_reasons)

    def test_context_window_filter(self):
        """TC005: Test context window capacity check."""
        small_context_model = ModelCard(
            model_id="small-context",
            provider="Test",
            supports_vision=True,
            quality=0.90,
            cost_per_1m_input_tokens_usd=3.0,
            cost_per_1m_output_tokens_usd=15.0,
            cost_is_placeholder=False,
            latency_ms=1000.0,
            context_window=2000,  # Small context window
            max_output_tokens=4096,
            reliability=0.98
        )

        # Request needs: (1500 + 600) * 1.05 = 2205 tokens > 2000
        result = _hard_filter(
            [small_context_model],
            quality_floor=0.0,
            input_tokens=1500,
            expected_output_tokens=600
        )

        assert len(result['eligible']) == 0
        assert len(result['filtered_out']) == 1
        assert 'context_window' in result['filtered_out'][0]['reason'].lower()

    def test_max_output_tokens_filter(self):
        """TC006: Test max output tokens capacity check."""
        limited_output_model = ModelCard(
            model_id="limited-output",
            provider="Test",
            supports_vision=True,
            quality=0.90,
            cost_per_1m_input_tokens_usd=3.0,
            cost_per_1m_output_tokens_usd=15.0,
            cost_is_placeholder=False,
            latency_ms=1000.0,
            context_window=128000,
            max_output_tokens=1000,  # Limited output
            reliability=0.98
        )

        # Request needs 1500 output tokens > 1000
        result = _hard_filter(
            [limited_output_model],
            quality_floor=0.0,
            input_tokens=1000,
            expected_output_tokens=1500
        )

        assert len(result['eligible']) == 0
        assert len(result['filtered_out']) == 1
        assert 'max_output' in result['filtered_out'][0]['reason'].lower()

    def test_vision_support_filter(self):
        """TC007: Test that only vision-capable models pass filter."""
        non_vision_model = ModelCard(
            model_id="text-only",
            provider="Test",
            supports_vision=False,  # Not vision capable
            quality=0.95,
            cost_per_1m_input_tokens_usd=2.0,
            cost_per_1m_output_tokens_usd=10.0,
            cost_is_placeholder=False,
            latency_ms=800.0,
            context_window=128000,
            max_output_tokens=4096,
            reliability=0.99
        )

        result = _hard_filter(
            [non_vision_model],
            quality_floor=0.0,
            input_tokens=1000,
            expected_output_tokens=500
        )

        assert len(result['eligible']) == 0
        assert len(result['filtered_out']) == 1
        assert result['filtered_out'][0]['reason'] == 'missing_feature:vision'

    def test_unlimited_context_window(self):
        """TC035: Test that None context_window (unlimited) passes filter."""
        unlimited_model = ModelCard(
            model_id="unlimited-context",
            provider="Test",
            supports_vision=True,
            quality=0.90,
            cost_per_1m_input_tokens_usd=3.0,
            cost_per_1m_output_tokens_usd=15.0,
            cost_is_placeholder=False,
            latency_ms=1000.0,
            context_window=None,  # Unlimited
            max_output_tokens=None,  # Unlimited
            reliability=0.98
        )

        # Request with huge token requirements
        result = _hard_filter(
            [unlimited_model],
            quality_floor=0.0,
            input_tokens=1000000,
            expected_output_tokens=100000
        )

        # Should pass because unlimited capacity
        assert len(result['eligible']) == 1
        assert len(result['filtered_out']) == 0


# ===========================
# Unit Tests: Normalization
# ===========================

class TestNormalization:
    """Test cases for _normalize function.

    Reference: TC009-TC010
    """

    def test_quality_normalization(self, multiple_model_cards):
        """TC009: Test min-max scaling for quality."""
        # Create predicted quality and cost dicts
        predicted_quality = {card.model_id: card.quality for card in multiple_model_cards}
        predicted_cost = {card.model_id: 0.01 for card in multiple_model_cards}  # Dummy costs

        result = _normalize(multiple_model_cards, predicted_quality, predicted_cost)

        # Quality range: 0.60 (low-quality) to 0.95 (high-quality)
        # Min (0.60) should normalize to 0.0
        # Max (0.95) should normalize to 1.0
        assert abs(result['quality']['low-quality-model'] - 0.0) < 0.01
        assert abs(result['quality']['high-quality-model'] - 1.0) < 0.01

        # Balanced model (0.85) should be: (0.85-0.60)/(0.95-0.60) = 0.25/0.35 ≈ 0.714
        assert abs(result['quality']['balanced-model'] - 0.714) < 0.01

    def test_cost_normalization_inverted(self, multiple_model_cards):
        """TC010: Test that cost is inverted (lower cost = higher score)."""
        predicted_quality = {card.model_id: card.quality for card in multiple_model_cards}

        # Compute actual costs
        predicted_cost = {
            card.model_id: _estimate_cost(card, 1000, 500)
            for card in multiple_model_cards
        }

        result = _normalize(multiple_model_cards, predicted_quality, predicted_cost)

        # Lower cost should have HIGHER normalized score (inverted)
        cost_effective_score = result['cost']['cost-effective-model']
        high_quality_score = result['cost']['high-quality-model']

        # cost-effective-model has lower cost, so should have higher score
        assert cost_effective_score > high_quality_score, \
            "Cost normalization should be inverted (lower cost = higher score)"

    def test_all_same_values_normalization(self):
        """TC052: Test normalization when all models have same value."""
        identical_models = [
            ModelCard(
                model_id=f"model-{i}",
                provider="Test",
                supports_vision=True,
                quality=0.80,  # Same for all
                cost_per_1m_input_tokens_usd=3.0,
                cost_per_1m_output_tokens_usd=15.0,
                cost_is_placeholder=False,
                latency_ms=1000.0,
                context_window=128000,
                max_output_tokens=4096,
                reliability=0.98
            )
            for i in range(3)
        ]

        predicted_quality = {card.model_id: card.quality for card in identical_models}
        predicted_cost = {card.model_id: 0.01 for card in identical_models}

        result = _normalize(identical_models, predicted_quality, predicted_cost)

        # When all values are the same, all should normalize to 1.0
        for model_id in result['quality']:
            assert result['quality'][model_id] == 1.0


# ===========================
# Unit Tests: Scoring
# ===========================

class TestScoring:
    """Test cases for _score function.

    Reference: TC011
    """

    def test_weighted_dot_product(self):
        """TC011: Test weighted score calculation."""
        model_id = "test-model"

        normalized = {
            'quality': {model_id: 0.8},
            'cost': {model_id: 0.6},
            'latency': {model_id: 0.7}
        }

        weights = {
            'quality': 0.5,
            'cost': 0.3,
            'latency': 0.2
        }

        # Expected: 0.5*0.8 + 0.3*0.6 + 0.2*0.7 = 0.4 + 0.18 + 0.14 = 0.72
        expected_score = 0.72

        result = _score(model_id, normalized, weights)

        assert abs(result - expected_score) < 0.001


# ===========================
# Unit Tests: Complexity
# ===========================

class TestComplexityHandling:
    """Test cases for complexity-related functions.

    Reference: TC020-TC025
    """

    def test_quality_prediction_without_complexity(self, sample_model_card):
        """TC022: Test quality when no complexity provided."""
        result = _predict_quality(sample_model_card, complexity_norm=None)

        # Should return base quality unchanged
        assert result == sample_model_card.quality

    def test_quality_degradation_with_high_complexity(self, sample_model_card):
        """TC020: Test quality degradation with high complexity."""
        high_complexity_norm = 0.9

        result = _predict_quality(sample_model_card, complexity_norm=high_complexity_norm)

        # Quality should be degraded (lower than base)
        assert result < sample_model_card.quality, \
            f"Expected quality degradation, got {result} vs base {sample_model_card.quality}"

    def test_quality_with_low_complexity(self, sample_model_card):
        """TC021: Test quality with low complexity."""
        low_complexity_norm = 0.1

        result = _predict_quality(sample_model_card, complexity_norm=low_complexity_norm)

        # Quality should be minimally affected or close to base
        assert result >= sample_model_card.quality * 0.95  # Allow max 5% degradation

    def test_weight_adaptation_no_complexity(self):
        """TC025: Test weights unchanged when no complexity."""
        weights = {'quality': 0.5, 'cost': 0.3, 'latency': 0.2}

        result = _adapt_weights(weights, complexity_norm=None)

        assert result == weights

    def test_weight_adaptation_high_complexity(self):
        """TC023: Test weight shift for hard documents."""
        weights = {'quality': 0.4, 'cost': 0.3, 'latency': 0.3}
        high_complexity_norm = 0.9

        result = _adapt_weights(weights, complexity_norm=high_complexity_norm)

        # Quality weight should increase
        assert result['quality'] > weights['quality'], \
            "Quality weight should increase for high complexity"

        # Cost + latency should decrease
        assert (result['cost'] + result['latency']) < (weights['cost'] + weights['latency'])

    def test_weight_adaptation_low_complexity(self):
        """TC024: Test weight shift for easy documents."""
        weights = {'quality': 0.4, 'cost': 0.3, 'latency': 0.3}
        low_complexity_norm = 0.1

        result = _adapt_weights(weights, complexity_norm=low_complexity_norm)

        # Quality weight should decrease
        assert result['quality'] < weights['quality'], \
            "Quality weight should decrease for low complexity"

        # Cost + latency should increase
        assert (result['cost'] + result['latency']) > (weights['cost'] + weights['latency'])


# ===========================
# Unit Tests: Model Selection
# ===========================

class TestModelSelection:
    """Test cases for _select_top_models function.

    Reference: TC012-TC013
    """

    def test_top_model_selection(self):
        """TC012: Test that highest scoring model is selected."""
        candidates_scored = [
            {'model_id': 'model-1', 'provider': 'A', 'score': 0.85},
            {'model_id': 'model-2', 'provider': 'B', 'score': 0.72},
            {'model_id': 'model-3', 'provider': 'C', 'score': 0.68},
        ]

        result = _select_top_models(candidates_scored, n=3)

        assert result['models'][0]['model_id'] == 'model-1'
        assert result['models'][0]['score'] == 0.85

    def test_provider_diversity_constraint(self):
        """TC013: Test 3rd model provider diversity rule."""
        candidates_scored = [
            {'model_id': 'model-1', 'provider': 'OpenAI', 'score': 0.85},
            {'model_id': 'model-2', 'provider': 'OpenAI', 'score': 0.82},
            {'model_id': 'model-3', 'provider': 'OpenAI', 'score': 0.78},
            {'model_id': 'model-4', 'provider': 'Anthropic', 'score': 0.75},
        ]

        result = _select_top_models(candidates_scored, n=3)

        # Rank 1 & 2 both OpenAI, so rank 3 should be from different provider
        assert result['models'][0]['provider'] == 'OpenAI'
        assert result['models'][1]['provider'] == 'OpenAI'
        assert result['models'][2]['provider'] == 'Anthropic'  # Different provider
        assert result['diversity_constraint_applied'] == True
        assert result['diversity_constraint_satisfied'] == True


# ===========================
# Integration Tests
# ===========================

class TestEndToEndRouting:
    """Integration tests for complete routing pipeline.

    Reference: TC047-TC050
    """

    @pytest.mark.skip(reason="Requires benchmark files - run separately")
    def test_end_to_end_bol_routing(self):
        """TC047: Test complete routing pipeline for BOL documents."""
        decision = route(
            doc_type='bol',
            input_tokens=1000,
            expected_output_tokens=512,
            profile_name='balanced',
            quality_floor=0.0
        )

        # Verify decision structure
        assert 'chosen' in decision
        assert 'eligible_ranked' in decision
        assert 'reasoning' in decision
        assert 'top_models' in decision

        # Verify chosen model
        assert decision['chosen']['model_id'] is not None
        assert decision['chosen']['score'] > 0

        # Verify ranking
        assert len(decision['eligible_ranked']) > 0
        scores = [c['score'] for c in decision['eligible_ranked']]
        assert scores == sorted(scores, reverse=True)  # Should be descending


# ===========================
# Edge Cases
# ===========================

class TestEdgeCases:
    """Test edge cases and error conditions.

    Reference: TC014, TC051-TC055
    """

    def test_no_eligible_models_error(self, multiple_model_cards):
        """TC014: Test error when all models filtered out."""
        # Set quality floor above all models
        with pytest.raises(NoEligibleModelError) as exc_info:
            _hard_filter(
                multiple_model_cards,
                quality_floor=1.0,  # Impossible to meet
                input_tokens=1000,
                expected_output_tokens=500
            )

            # If _hard_filter doesn't raise, route() should
            # This is a simplified test; actual test would call route()

        # Note: _hard_filter returns dict, so we'd need to test via route()
        # This is a placeholder showing the pattern

    def test_single_model_available(self):
        """TC051: Test routing when only one model passes filter."""
        single_model = [
            ModelCard(
                model_id="only-model",
                provider="Test",
                supports_vision=True,
                quality=0.95,
                cost_per_1m_input_tokens_usd=3.0,
                cost_per_1m_output_tokens_usd=15.0,
                cost_is_placeholder=False,
                latency_ms=1000.0,
                context_window=128000,
                max_output_tokens=4096,
                reliability=0.98
            )
        ]

        result = _hard_filter(single_model, 0.0, 1000, 500)

        assert len(result['eligible']) == 1
        # Routing should still work with single model


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
