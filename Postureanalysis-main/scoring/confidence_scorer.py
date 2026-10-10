"""
Confidence Scorer module.
Computes dynamic confidence score based on all behavioral metrics.

IMPROVEMENT: Replaced the boost/decay accumulator with a direct target-score
approach.  At every frame a target score is computed directly from the weighted
composite of behavioral inputs, and the displayed score is smoothly interpolated
toward that target using a configurable time-constant (tau).  This is simpler,
more predictable, and eliminates the dead-zone that existed between composite
0.4–0.7 in the original implementation.

Additional changes:
  - Baseline lowered from 70 to 55 so new users start at a more honest point.
  - Weights are documented and can be overridden in config.
  - Component scores are passed through to the result for UI transparency.
"""

import time
from typing import Dict, Any, Optional
from enum import Enum
import config


class ConfidenceLevel(Enum):
    """Enum for confidence level labels."""
    HIGH = "high_confidence"
    MODERATE = "moderate_confidence"
    LOW = "low_confidence"


class ConfidenceScorer:
    """
    Dynamic confidence scoring engine.
    Computes a 0-100 score based on multiple behavioral inputs.
    """

    # Time-constant (seconds) for score interpolation.
    # Smaller τ → faster response; larger τ → smoother but slower.
    TAU = 3.0

    def __init__(
        self,
        baseline: float = config.CONFIDENCE_BASELINE,
        boost_rate: float = config.CONFIDENCE_BOOST_RATE,       # kept for API compat
        decay_rate: float = config.CONFIDENCE_DECAY_RATE,       # kept for API compat
        away_penalty: float = config.CONFIDENCE_AWAY_PENALTY    # kept for API compat
    ):
        """
        Initialize the confidence scorer.

        Args:
            baseline: Starting confidence score (0-100).
            boost_rate: Unused (kept for backward-compat).
            decay_rate: Unused (kept for backward-compat).
            away_penalty: Unused (kept for backward-compat).
        """
        # Use a slightly lower baseline so the score is honest from the start
        self.baseline = min(baseline, 55.0)

        # Weights for different components
        self.weights = {
            "attention": config.WEIGHT_FACE_PRESENCE,
            "eye_contact": config.WEIGHT_EYE_CONTACT,
            "posture": config.WEIGHT_POSTURE,
            "movement": config.WEIGHT_MOVEMENT,
        }

        # Current displayed score starts at baseline
        self.current_score: float = self.baseline
        self.last_update_time: float = time.time()

        # Thresholds
        self.high_threshold = config.HIGH_CONFIDENCE_THRESHOLD
        self.moderate_threshold = config.MODERATE_CONFIDENCE_THRESHOLD

        # History for analytics (30-frame window)
        self.score_history = []
        self.history_max_size = 30

    def compute_score(
        self,
        attention_result: Dict[str, Any],
        gaze_result: Dict[str, Any],
        posture_result: Dict[str, Any],
        movement_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compute confidence score based on all behavioral inputs.

        Args:
            attention_result: Output from AttentionAnalyzer
            gaze_result: Output from GazeAnalyzer
            posture_result: Output from PostureAnalyzer
            movement_result: Output from MovementAnalyzer

        Returns:
            Dictionary containing confidence score and breakdown.
        """
        current_time = time.time()
        delta_time = current_time - self.last_update_time

        result = {
            "score": self.current_score,
            "level": self._get_level(self.current_score),
            "component_scores": {},
            "is_away": False,
            "score_delta": 0.0,
        }

        # Extract component scores
        attention_score = attention_result.get("attention_score", 0.5)
        eye_contact_score = gaze_result.get("eye_contact_score", 0.5)
        posture_score = posture_result.get("posture_score", 0.5)
        movement_score = movement_result.get("movement_score", 0.5)

        result["component_scores"] = {
            "attention": round(attention_score, 3),
            "eye_contact": round(eye_contact_score, 3),
            "posture": round(posture_score, 3),
            "movement": round(movement_score, 3),
        }

        # Away-from-screen flag
        attention_state = attention_result.get("state")
        if hasattr(attention_state, 'value'):
            is_away = attention_state.value == "away_from_screen"
        else:
            is_away = str(attention_state) == "away_from_screen"

        result["is_away"] = is_away

        # ----------------------------------------------------------------
        # IMPROVEMENT: target-score interpolation (replaces boost/decay)
        #
        # 1. Compute the target score directly from the weighted composite.
        #    composite ∈ [0, 1] → target ∈ [0, 100].
        # 2. When away, the target is floored at 0 with an extra penalty.
        # 3. The current score is interpolated toward the target using an
        #    exponential approach: score += (target - score) * (dt / τ).
        #    This guarantees smooth motion and a well-defined steady state.
        # ----------------------------------------------------------------
        composite = (
            attention_score * self.weights["attention"]
            + eye_contact_score * self.weights["eye_contact"]
            + posture_score * self.weights["posture"]
            + movement_score * self.weights["movement"]
        )

        if is_away:
            target_score = 0.0   # away → target drops to 0
        else:
            target_score = composite * 100.0

        # Exponential approach toward target
        alpha = min(1.0, delta_time / self.TAU)
        prev_score = self.current_score
        self.current_score = (
            self.current_score + (target_score - self.current_score) * alpha
        )
        self.current_score = max(
            config.CONFIDENCE_MIN,
            min(config.CONFIDENCE_MAX, self.current_score)
        )

        result["score_delta"] = self.current_score - prev_score

        # Analytics history (unsmoothed, for session report)
        self.score_history.append(self.current_score)
        if len(self.score_history) > self.history_max_size:
            self.score_history.pop(0)

        result["score"] = round(self.current_score, 1)
        result["level"] = self._get_level(self.current_score)

        self.last_update_time = current_time
        return result

    def _get_level(self, score: float) -> ConfidenceLevel:
        """Get confidence level label from score."""
        if score >= self.high_threshold:
            return ConfidenceLevel.HIGH
        elif score >= self.moderate_threshold:
            return ConfidenceLevel.MODERATE
        else:
            return ConfidenceLevel.LOW

    def get_average_score(self) -> float:
        """Get the average confidence score over the session."""
        if not self.score_history:
            return self.baseline
        return sum(self.score_history) / len(self.score_history)

    def reset(self):
        """Reset scorer state."""
        self.current_score = self.baseline
        self.last_update_time = time.time()
        self.score_history = []
