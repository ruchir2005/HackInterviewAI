"""
Posture Analyzer module.
Analyzes upper-body posture using pose landmarks.

IMPROVEMENTS:
  1. Calibration window shifted to frames 30-60 (skipping initial setup chaos).
  2. Z-depth lean detection removed — webcam z-coords are too noisy to trust.
  3. Posture history uses exponential-decay weighting so stale bad frames
     don't linger as long in the smoothed score.
"""

import numpy as np
from typing import Optional, Dict, Any
from enum import Enum
from collections import deque
import config


class PostureType(Enum):
    """Enum for posture types."""
    UPRIGHT = "upright"
    SLOUCHING = "slouching"
    LEANING_FORWARD = "leaning_forward"
    LEANING_BACKWARD = "leaning_backward"
    HEAD_TILT_LEFT = "head_tilt_left"
    HEAD_TILT_RIGHT = "head_tilt_right"
    UNKNOWN = "unknown"


class PostureQuality(Enum):
    """Enum for posture quality levels."""
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNKNOWN = "unknown"


class PostureAnalyzer:
    """
    Analyzes posture using pose landmarks.
    Detects slouching, shoulder tilt, and head tilt.
    """

    # Calibration is collected between these frame numbers so that camera-
    # setup fidgeting (frames 0-29) is excluded from the baseline.
    CALIB_START_FRAME = 30
    CALIB_END_FRAME = 60

    def __init__(
        self,
        upright_threshold: float = config.POSTURE_UPRIGHT_THRESHOLD,
        slouch_threshold: float = config.POSTURE_SLOUCH_THRESHOLD,
        lean_forward_threshold: float = config.POSTURE_LEAN_FORWARD_THRESHOLD,
        lean_back_threshold: float = config.POSTURE_LEAN_BACK_THRESHOLD,
        head_tilt_threshold: float = config.POSTURE_HEAD_TILT_THRESHOLD
    ):
        """
        Initialize the posture analyzer.

        Args:
            upright_threshold: Max shoulder angle for upright posture.
            slouch_threshold: Shoulder drop indicating slouch.
            lean_forward_threshold: Nose forward threshold (kept for API compat).
            lean_back_threshold: Nose backward threshold (kept for API compat).
            head_tilt_threshold: Head tilt angle threshold.
        """
        self.upright_threshold = upright_threshold
        self.slouch_threshold = slouch_threshold
        self.lean_forward_threshold = lean_forward_threshold   # kept for compat
        self.lean_back_threshold = lean_back_threshold         # kept for compat
        self.head_tilt_threshold = head_tilt_threshold

        # Baseline calibration
        self.baseline_shoulder_y: Optional[float] = None
        self.baseline_shoulder_width: Optional[float] = None  # NEW: body-scale ref
        self.calibration_frames = 0   # counts ALL frames seen (for window logic)
        self.calibration_complete = False

        # Metrics tracking
        self.total_frames = 0
        self.good_posture_frames = 0
        self.acceptable_posture_frames = 0
        self.poor_posture_frames = 0

        # IMPROVEMENT: exponential-decay weighted history using a deque
        self.posture_history: deque = deque(maxlen=15)
        self._decay_weight = 0.92   # each older sample is multiplied by this

    def analyze(self, pose_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze posture from pose detection results.

        Args:
            pose_result: Output from PoseDetector.detect()

        Returns:
            Dictionary containing posture analysis results.
        """
        analysis_result = {
            "posture_detected": False,
            "posture_type": PostureType.UNKNOWN,
            "posture_quality": PostureQuality.UNKNOWN,
            "issues": [],
            "shoulder_angle": None,
            "posture_score": 0.5,
            "calibrated": self.calibration_complete
        }

        if not pose_result.get("pose_detected", False):
            # Still increment frame counter so calibration window advances
            self.calibration_frames += 1
            return analysis_result

        analysis_result["posture_detected"] = True
        landmarks = pose_result.get("landmarks", {})

        # Get key landmarks
        left_shoulder = landmarks.get("left_shoulder")
        right_shoulder = landmarks.get("right_shoulder")
        nose = landmarks.get("nose")
        left_ear = landmarks.get("left_ear")
        right_ear = landmarks.get("right_ear")

        if not all([left_shoulder, right_shoulder, nose]):
            self.calibration_frames += 1
            return analysis_result

        # Calculate metrics
        shoulder_angle = self._calculate_shoulder_tilt(left_shoulder, right_shoulder)
        analysis_result["shoulder_angle"] = shoulder_angle

        # Shoulder width — used to normalise drop threshold
        shoulder_width = abs(right_shoulder["x"] - left_shoulder["x"])

        self.calibration_frames += 1

        # --- Calibration window: frames 30-60 ---
        if not self.calibration_complete:
            if self.calibration_frames >= self.CALIB_START_FRAME:
                self._calibrate(left_shoulder, right_shoulder, shoulder_width)
            # Until calibration is complete, return unknown quality
            analysis_result["posture_quality"] = PostureQuality.UNKNOWN
            return analysis_result

        issues = []
        posture_type = PostureType.UPRIGHT

        # 1. Shoulder tilt (uneven shoulders) — threshold: 15°
        if abs(shoulder_angle) > 15:
            if shoulder_angle > 0:
                issues.append("right_shoulder_low")
            else:
                issues.append("left_shoulder_low")

        # 2. Slouching — shoulder Y drop normalised by shoulder width
        #    (body-size invariant).
        #    Original raw threshold was 0.08 frame-height.
        #    For a typical shoulder_width ≈ 0.25 frame-width:
        #      0.08 / 0.25 = 0.32 → use 0.32 as the normalised threshold.
        avg_shoulder_y = (left_shoulder["y"] + right_shoulder["y"]) / 2
        if self.baseline_shoulder_y is not None and self.baseline_shoulder_width:
            shoulder_drop = avg_shoulder_y - self.baseline_shoulder_y
            norm_drop = shoulder_drop / max(self.baseline_shoulder_width, 0.05)
            if norm_drop > 0.32:   # equivalent to ~8% of frame height for typical body scale
                posture_type = PostureType.SLOUCHING
                issues.append("slouching")

        # 3. Head tilt using ears (only flag >20°)
        if left_ear and right_ear:
            head_tilt = self._calculate_head_tilt(left_ear, right_ear)
            if abs(head_tilt) > 20:
                if head_tilt > 0:
                    posture_type = PostureType.HEAD_TILT_RIGHT
                    issues.append("head_tilted_right")
                else:
                    posture_type = PostureType.HEAD_TILT_LEFT
                    issues.append("head_tilted_left")

        # NOTE: Z-depth lean detection intentionally removed.
        # Standard webcam z-coordinates are unreliable (noisy depth estimates
        # from a flat 2-D sensor) and produced too many false positives.

        # Determine quality
        if len(issues) == 0:
            posture_quality = PostureQuality.GOOD
            self.good_posture_frames += 1
        elif len(issues) == 1:
            posture_quality = PostureQuality.ACCEPTABLE
            self.acceptable_posture_frames += 1
        else:
            posture_quality = PostureQuality.POOR
            self.poor_posture_frames += 1

        self.total_frames += 1

        # IMPROVEMENT: exponential-decay weighted score
        posture_score = self._calculate_posture_score(issues, shoulder_angle)
        smoothed_score = self._decay_weighted_mean(posture_score)

        analysis_result["posture_type"] = posture_type
        analysis_result["posture_quality"] = posture_quality
        analysis_result["issues"] = issues
        analysis_result["posture_score"] = smoothed_score

        return analysis_result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calibrate(
        self,
        left_shoulder: Dict,
        right_shoulder: Dict,
        shoulder_width: float
    ):
        """Calibrate baseline posture from frames 30–60."""
        frames_in_window = self.calibration_frames - self.CALIB_START_FRAME

        avg_shoulder_y = (left_shoulder["y"] + right_shoulder["y"]) / 2

        if frames_in_window == 0:
            # First calibration frame — initialise
            self.baseline_shoulder_y = avg_shoulder_y
            self.baseline_shoulder_width = shoulder_width
        else:
            # EMA update — give more weight to later (settled) frames
            alpha = 0.15
            self.baseline_shoulder_y = (
                self.baseline_shoulder_y * (1 - alpha) + avg_shoulder_y * alpha
            )
            self.baseline_shoulder_width = (
                self.baseline_shoulder_width * (1 - alpha) + shoulder_width * alpha
            )

        if self.calibration_frames >= self.CALIB_END_FRAME:
            self.calibration_complete = True

    def _decay_weighted_mean(self, new_score: float) -> float:
        """
        Add new_score to history and return an exponentially decay-weighted mean.

        More recent scores get exponentially higher weight.
        """
        self.posture_history.append(new_score)
        n = len(self.posture_history)
        weights = np.array([self._decay_weight ** (n - 1 - i) for i in range(n)])
        weights /= weights.sum()
        return float(np.dot(list(self.posture_history), weights))

    def _calculate_shoulder_tilt(
        self,
        left_shoulder: Dict,
        right_shoulder: Dict
    ) -> float:
        """Calculate shoulder tilt angle in degrees."""
        dx = right_shoulder["x"] - left_shoulder["x"]
        dy = right_shoulder["y"] - left_shoulder["y"]
        return float(np.degrees(np.arctan2(dy, dx)))

    def _calculate_head_tilt(self, left_ear: Dict, right_ear: Dict) -> float:
        """Calculate head tilt angle in degrees."""
        dx = right_ear["x"] - left_ear["x"]
        dy = right_ear["y"] - left_ear["y"]
        return float(np.degrees(np.arctan2(dy, dx)))

    def _calculate_posture_score(self, issues: list, shoulder_angle: float) -> float:
        """Calculate a 0-1 posture score based on detected issues."""
        base_score = 1.0

        issue_penalties = {
            "slouching": 0.20,
            "head_tilted_left": 0.10,
            "head_tilted_right": 0.10,
            "left_shoulder_low": 0.06,
            "right_shoulder_low": 0.06,
        }

        for issue in issues:
            base_score -= issue_penalties.get(issue, 0.05)

        # Penalise shoulder tilt angles beyond 5°
        if abs(shoulder_angle) > 5:
            angle_penalty = min(0.12, (abs(shoulder_angle) - 5) / 90 * 0.18)
            base_score -= angle_penalty

        return max(0.0, min(1.0, base_score))

    # ------------------------------------------------------------------
    # Analytics helpers
    # ------------------------------------------------------------------

    def get_quality_percentage(self) -> Dict[str, float]:
        """Get percentage breakdown of posture quality over time."""
        if self.total_frames == 0:
            return {"good": 0, "acceptable": 0, "poor": 0}

        return {
            "good": (self.good_posture_frames / self.total_frames) * 100,
            "acceptable": (self.acceptable_posture_frames / self.total_frames) * 100,
            "poor": (self.poor_posture_frames / self.total_frames) * 100,
        }

    def reset(self):
        """Reset analyzer state."""
        self.baseline_shoulder_y = None
        self.baseline_shoulder_width = None
        self.calibration_frames = 0
        self.calibration_complete = False
        self.total_frames = 0
        self.good_posture_frames = 0
        self.acceptable_posture_frames = 0
        self.poor_posture_frames = 0
        self.posture_history.clear()
