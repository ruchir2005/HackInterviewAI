"""
Movement Analyzer module.
Detects nervousness and stability through landmark displacement analysis.

Approach:
  - Track RMS displacement of 5 upper-body landmarks frame-to-frame.
  - Displacement is scaled ×1000 to bring it into a human-readable range.
  - Outlier clamping: single-frame spikes >3× recent mean are clamped to avoid
    camera-move / re-seat artifacts causing brief "highly nervous" readings.
  - Exponential-decay weighted mean gives more importance to recent motion.
  - Thresholds are compared directly to raw displacement (not body-normalised),
    because the config thresholds were empirically tuned for the ×1000 scale.
"""

import numpy as np
from typing import Optional, Dict, Any, List
from enum import Enum
from collections import deque
import config


class NervousnessLevel(Enum):
    """Enum for nervousness classification."""
    CALM = "calm"
    SLIGHTLY_NERVOUS = "slightly_nervous"
    HIGHLY_NERVOUS = "highly_nervous"
    UNKNOWN = "unknown"


class MovementAnalyzer:
    """
    Analyzes movement patterns to detect nervousness and stability.
    Uses frame-to-frame landmark displacement tracking.
    """

    def __init__(
        self,
        window_size: int = config.MOVEMENT_WINDOW_SIZE,
        calm_threshold: float = config.CALM_MOVEMENT_THRESHOLD,
        nervous_threshold: float = config.NERVOUS_MOVEMENT_THRESHOLD
    ):
        """
        Initialize the movement analyzer.

        Args:
            window_size: Number of frames for rolling average.
            calm_threshold: Max displacement (×1000 scale) for calm.
            nervous_threshold: Displacement threshold (×1000 scale) for highly nervous.
        """
        self.window_size = window_size
        self.calm_threshold = calm_threshold        # default 2.0
        self.nervous_threshold = nervous_threshold  # default 8.0

        # Landmark history
        self.landmark_history: deque = deque(maxlen=window_size)
        self.displacement_history: deque = deque(maxlen=window_size)

        # Metrics
        self.total_frames = 0
        self.calm_frames = 0
        self.slightly_nervous_frames = 0
        self.highly_nervous_frames = 0

        # Smoothed score history
        self.score_history: deque = deque(maxlen=10)

        # Body-scale reference — used only for outlier detection ratio
        self._shoulder_scale: float = 0.20

    def analyze(self, pose_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze movement from pose detection results.

        Args:
            pose_result: Output from PoseDetector.detect()

        Returns:
            Dictionary containing movement analysis results.
        """
        analysis_result = {
            "movement_detected": False,
            "nervousness_level": NervousnessLevel.UNKNOWN,
            "displacement": 0.0,
            "average_displacement": 0.0,
            "movement_score": 1.0,   # 1.0 = calm, 0.0 = highly nervous
            "is_stable": True
        }

        if not pose_result.get("pose_detected", False):
            return analysis_result

        analysis_result["movement_detected"] = True
        landmarks = pose_result.get("landmarks", {})

        # Update body-scale reference (used only for outlier clamping ratio)
        self._update_shoulder_scale(landmarks)

        # Extract positions for tracked landmarks
        current_positions = self._extract_key_positions(landmarks)
        if current_positions is None:
            return analysis_result

        # Calculate raw displacement from previous frame
        displacement = 0.0
        if len(self.landmark_history) > 0:
            prev_positions = self.landmark_history[-1]
            displacement = self._calculate_displacement(prev_positions, current_positions)

            # Outlier clamping: if a single frame jumps >4× the rolling mean
            # it is almost certainly a camera-move / re-seat artifact.
            # We use the normalised ratio (displacement / shoulder_scale) so
            # the check is body-size invariant, but we clamp the raw value.
            if len(self.displacement_history) >= 5:
                recent_mean = float(np.mean(list(self.displacement_history)[-8:]))
                if recent_mean > 0:
                    norm_ratio = displacement / max(self._shoulder_scale * 1000, 0.01)
                    norm_mean_ratio = recent_mean / max(self._shoulder_scale * 1000, 0.01)
                    if norm_ratio > 4.0 * norm_mean_ratio:
                        displacement = recent_mean  # clamp to rolling mean

        # Store raw displacement for scoring
        self.landmark_history.append(current_positions)
        self.displacement_history.append(displacement)

        analysis_result["displacement"] = displacement

        # Exponential-decay weighted average (recent frames count more)
        avg_displacement = self._decay_weighted_mean(self.displacement_history)
        analysis_result["average_displacement"] = avg_displacement

        # Classify and score against raw thresholds
        nervousness_level, is_stable = self._classify_nervousness(avg_displacement)
        analysis_result["nervousness_level"] = nervousness_level
        analysis_result["is_stable"] = is_stable

        self.total_frames += 1
        if nervousness_level == NervousnessLevel.CALM:
            self.calm_frames += 1
        elif nervousness_level == NervousnessLevel.SLIGHTLY_NERVOUS:
            self.slightly_nervous_frames += 1
        elif nervousness_level == NervousnessLevel.HIGHLY_NERVOUS:
            self.highly_nervous_frames += 1

        movement_score = self._calculate_movement_score(avg_displacement)
        self.score_history.append(movement_score)
        analysis_result["movement_score"] = float(np.mean(self.score_history))
        return analysis_result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _update_shoulder_scale(self, landmarks: Dict):
        """Track inter-shoulder distance (normalised coords) via EMA."""
        ls = landmarks.get("left_shoulder")
        rs = landmarks.get("right_shoulder")
        if ls and rs:
            dist = abs(rs["x"] - ls["x"])
            if dist > 0.01:
                self._shoulder_scale = self._shoulder_scale * 0.95 + dist * 0.05

    def _extract_key_positions(self, landmarks: Dict) -> Optional[np.ndarray]:
        """
        Extract key landmark positions for movement tracking.

        Returns:
            numpy array of positions or None if key landmarks missing.
        """
        key_landmarks = ["nose", "left_shoulder", "right_shoulder", "left_ear", "right_ear"]
        positions = []

        for name in key_landmarks:
            lm = landmarks.get(name)
            if lm is not None:
                positions.append([lm["x"], lm["y"]])
            else:
                if len(positions) > 0:
                    positions.append(positions[-1])   # repeat last known
                else:
                    return None

        return np.array(positions)

    def _calculate_displacement(
        self,
        prev_positions: np.ndarray,
        current_positions: np.ndarray
    ) -> float:
        """
        Calculate RMS displacement between frames.

        Returns:
            RMS of Euclidean distances for all tracked landmarks, scaled ×1000.
            Typical values:  ~1 = micro-jitter,  ~3-5 = normal motion,  ~10+ = fidgeting.
        """
        if prev_positions.shape != current_positions.shape:
            return 0.0

        distances = np.linalg.norm(current_positions - prev_positions, axis=1)
        rms_displacement = float(np.sqrt(np.mean(distances ** 2)))
        return rms_displacement * 1000

    @staticmethod
    def _decay_weighted_mean(history: deque, decay: float = 0.90) -> float:
        """
        Compute an exponential-decay weighted mean.
        More recent values have higher weight.
        """
        if not history:
            return 0.0
        arr = np.array(list(history))
        n = len(arr)
        weights = np.array([decay ** (n - 1 - i) for i in range(n)])
        weights /= weights.sum()
        return float(np.dot(arr, weights))

    def _classify_nervousness(self, avg_displacement: float) -> tuple:
        """
        Classify nervousness level.
        Thresholds are in raw ×1000 displacement units (empirically tuned).

        Returns:
            Tuple of (NervousnessLevel, is_stable)
        """
        if avg_displacement <= self.calm_threshold:
            return NervousnessLevel.CALM, True
        elif avg_displacement <= self.nervous_threshold:
            return NervousnessLevel.SLIGHTLY_NERVOUS, True
        else:
            return NervousnessLevel.HIGHLY_NERVOUS, False

    def _calculate_movement_score(self, avg_displacement: float) -> float:
        """
        Calculate a 0-1 score. 1.0 = perfectly calm, 0.0 = highly nervous.
        """
        if avg_displacement <= self.calm_threshold:
            return 1.0
        elif avg_displacement >= self.nervous_threshold:
            return 0.0
        else:
            progress = (avg_displacement - self.calm_threshold) / (
                self.nervous_threshold - self.calm_threshold
            )
            return 1.0 - progress

    # ------------------------------------------------------------------
    # Analytics helpers
    # ------------------------------------------------------------------

    def get_nervousness_percentage(self) -> Dict[str, float]:
        """Get percentage breakdown of nervousness levels."""
        if self.total_frames == 0:
            return {"calm": 100, "slightly_nervous": 0, "highly_nervous": 0}

        return {
            "calm": (self.calm_frames / self.total_frames) * 100,
            "slightly_nervous": (self.slightly_nervous_frames / self.total_frames) * 100,
            "highly_nervous": (self.highly_nervous_frames / self.total_frames) * 100,
        }

    def reset(self):
        """Reset analyzer state."""
        self.landmark_history.clear()
        self.displacement_history.clear()
        self.total_frames = 0
        self.calm_frames = 0
        self.slightly_nervous_frames = 0
        self.highly_nervous_frames = 0
        self.score_history.clear()
        self._shoulder_scale = 0.20
