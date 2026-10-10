"""
Gaze Analyzer module.
Tracks eye contact duration and quality over time.

IMPROVEMENT: Replaced binary majority-vote with an Exponential Moving Average
(EMA) on the is_looking signal. This gives smoother, more natural eye-contact
scores that are resistant to single-frame jitter while still responding quickly
to genuine gaze-away events.
"""

import time
from typing import Optional, Dict, Any
from enum import Enum
import config


class GazeAnalyzer:
    """
    Analyzes eye contact quality based on gaze detection over time.
    """

    def __init__(
        self,
        off_center_timeout: float = config.GAZE_OFF_CENTER_TIMEOUT,
        tolerance_duration: float = config.GAZE_TOLERANCE_DURATION
    ):
        """
        Initialize the gaze analyzer.

        Args:
            off_center_timeout: Seconds of off-center gaze before penalizing.
            tolerance_duration: Short glances are tolerated within this duration.
        """
        self.off_center_timeout = off_center_timeout
        self.tolerance_duration = tolerance_duration

        # State tracking
        self.last_looking_at_camera_time: Optional[float] = None
        self.off_center_start_time: Optional[float] = None

        # Metrics
        self.total_eye_contact_duration = 0.0
        self.total_off_center_duration = 0.0
        self.attention_loss_events = 0
        self.last_update_time = time.time()

        # Track if we've already counted current off-center event
        self._event_counted = False

        # ----------------------------------------------------------------
        # IMPROVEMENT: EMA-based smoothing instead of binary majority vote.
        #
        # The EMA decays toward 0 when not looking and toward 1 when looking.
        # alpha controls responsiveness:
        #   - High alpha → fast response, more jittery
        #   - Low alpha  → smooth, but slower to react
        #
        # alpha = 0.15 means the EMA has an effective window of ~13 frames
        # at 30fps, which is ~0.4s — fast enough to notice real gaze-aways
        # but resistant to single-frame noise.
        # ----------------------------------------------------------------
        self._ema_looking: float = 0.5   # starts neutral
        self._ema_alpha: float = 0.15
        self._looking_threshold: float = 0.5   # EMA above this → "looking"

    def analyze(self, gaze_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze eye contact based on gaze detection results.

        Args:
            gaze_result: Output from GazeDetector.detect()

        Returns:
            Dictionary containing eye contact analysis results.
        """
        current_time = time.time()
        delta_time = current_time - self.last_update_time

        analysis_result = {
            "gaze_detected": gaze_result.get("face_mesh_detected", False),
            "is_looking_at_camera": False,
            "gaze_direction": "unknown",
            "off_center_duration": 0.0,
            "eye_contact_score": 0.5,
            "attention_loss_events": self.attention_loss_events,
            "eye_contact_percentage": self.get_eye_contact_percentage()
        }

        if not analysis_result["gaze_detected"]:
            # When face-mesh is gone, decay the EMA toward 0
            self._ema_looking = self._ema_looking * (1 - self._ema_alpha)
            return analysis_result

        is_looking_raw = gaze_result.get("is_looking_at_camera", False)
        gaze_direction = gaze_result.get("gaze_direction")

        if hasattr(gaze_direction, 'value'):
            analysis_result["gaze_direction"] = gaze_direction.value
        elif gaze_direction:
            analysis_result["gaze_direction"] = str(gaze_direction)

        # ----------------------------------------------------------------
        # IMPROVEMENT: update EMA instead of appending to list
        # ----------------------------------------------------------------
        target = 1.0 if is_looking_raw else 0.0
        self._ema_looking = (
            self._ema_looking * (1 - self._ema_alpha)
            + target * self._ema_alpha
        )

        smoothed_looking = self._ema_looking >= self._looking_threshold
        analysis_result["is_looking_at_camera"] = smoothed_looking

        if smoothed_looking:
            self.last_looking_at_camera_time = current_time
            self.total_eye_contact_duration += delta_time

            if self.off_center_start_time is not None:
                self.total_off_center_duration += current_time - self.off_center_start_time
            self.off_center_start_time = None
            self._event_counted = False

            # Eye contact score maps EMA linearly above threshold (0.5→1.0)
            normalized = min(1.0, (self._ema_looking - self._looking_threshold)
                             / (1.0 - self._looking_threshold))
            analysis_result["eye_contact_score"] = 0.7 + normalized * 0.3

        else:
            if self.off_center_start_time is None:
                self.off_center_start_time = current_time

            off_center_duration = current_time - self.off_center_start_time
            analysis_result["off_center_duration"] = off_center_duration

            if off_center_duration <= self.tolerance_duration:
                # Still within tolerance — slight penalty
                analysis_result["eye_contact_score"] = 0.8

            elif off_center_duration >= self.off_center_timeout:
                # Significant attention loss
                analysis_result["eye_contact_score"] = 0.2

                if not self._event_counted:
                    self.attention_loss_events += 1
                    self._event_counted = True

            else:
                # Gradual decrease using EMA value for smoothness
                progress = (off_center_duration - self.tolerance_duration) / (
                    self.off_center_timeout - self.tolerance_duration
                )
                analysis_result["eye_contact_score"] = max(0.2, 0.8 - progress * 0.6)

        analysis_result["attention_loss_events"] = self.attention_loss_events
        analysis_result["eye_contact_percentage"] = self.get_eye_contact_percentage()

        self.last_update_time = current_time
        return analysis_result

    def get_eye_contact_percentage(self) -> float:
        """
        Calculate the percentage of time with eye contact.

        Returns:
            Eye contact percentage (0-100).
        """
        total_time = self.total_eye_contact_duration + self.total_off_center_duration
        if total_time == 0:
            return 100.0

        return (self.total_eye_contact_duration / total_time) * 100

    def reset(self):
        """Reset analyzer state."""
        self.last_looking_at_camera_time = None
        self.off_center_start_time = None
        self.total_eye_contact_duration = 0.0
        self.total_off_center_duration = 0.0
        self.attention_loss_events = 0
        self.last_update_time = time.time()
        self._event_counted = False
        self._ema_looking = 0.5
