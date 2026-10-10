"""
Attention Analyzer module.
Tracks face presence and determines attention state over time.

IMPROVEMENT: Uses the face detection confidence score (0.0–1.0) instead of a
binary face_present flag.  Partial occlusion (side profile, hand in front of
face) now produces a partial attention score rather than hard-zero, and the
score decays exponentially rather than dropping linearly so a quick glance away
doesn't produce an instant "away from screen" reading.
"""

import time
from typing import Optional, Dict, Any
from enum import Enum
import config


class AttentionState(Enum):
    """Enum for attention states."""
    FULLY_ATTENTIVE = "fully_attentive"
    TEMPORARILY_DISTRACTED = "temporarily_distracted"
    AWAY_FROM_SCREEN = "away_from_screen"
    UNKNOWN = "unknown"


class AttentionAnalyzer:
    """
    Analyzes attention state based on face presence over time.
    """

    def __init__(
        self,
        face_absence_timeout: float = config.FACE_ABSENCE_TIMEOUT,
        distraction_timeout: float = config.DISTRACTION_TIMEOUT
    ):
        """
        Initialize the attention analyzer.

        Args:
            face_absence_timeout: Seconds before marking as away from screen.
            distraction_timeout: Seconds before counting as distraction event.
        """
        self.face_absence_timeout = face_absence_timeout
        self.distraction_timeout = distraction_timeout

        # State tracking
        self.current_state = AttentionState.UNKNOWN
        self.last_face_seen_time: Optional[float] = None
        self.face_absence_start: Optional[float] = None

        # Metrics
        self.distraction_events = 0
        self.total_away_duration = 0.0
        self.total_attentive_duration = 0.0
        self.last_update_time = time.time()

        self._distraction_counted = False

        # IMPROVEMENT: EMA-smoothed confidence to avoid instant drops on single-
        # frame detection failures (blink, momentary occlusion, etc.)
        self._ema_confidence: float = 0.0
        self._ema_alpha: float = 0.20    # ~5-frame effective window at 30 fps
        self._presence_threshold: float = 0.40   # EMA confidence to count as present

    def analyze(self, face_detection_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze attention state based on face detection results.

        Args:
            face_detection_result: Output from FaceDetector.detect()

        Returns:
            Dictionary containing attention analysis results.
        """
        current_time = time.time()
        delta_time = current_time - self.last_update_time

        # Use raw detection confidence (0=not found, >0=found with that score)
        raw_confidence: float = 0.0
        if face_detection_result.get("face_present", False):
            raw_confidence = float(face_detection_result.get("confidence", 0.8))

        # IMPROVEMENT: smooth confidence with EMA so single-frame flickers
        # don't flip the attention state
        self._ema_confidence = (
            self._ema_confidence * (1 - self._ema_alpha)
            + raw_confidence * self._ema_alpha
        )

        # Determine presence from smoothed confidence
        face_present = self._ema_confidence >= self._presence_threshold

        analysis_result = {
            "state": self.current_state,
            "face_present": face_present,
            "face_confidence": self._ema_confidence,
            "seconds_since_face": 0.0,
            "distraction_events": self.distraction_events,
            "attention_score": 1.0,
            "total_away_duration": self.total_away_duration,
            "total_attentive_duration": self.total_attentive_duration
        }

        if face_present:
            if self.face_absence_start is not None:
                absence_duration = current_time - self.face_absence_start
                self.total_away_duration += absence_duration

            self.last_face_seen_time = current_time
            self.face_absence_start = None
            self._distraction_counted = False

            self.current_state = AttentionState.FULLY_ATTENTIVE
            self.total_attentive_duration += delta_time

            # IMPROVEMENT: attention score scales with EMA confidence so a
            # partial detection (profile face, low score) gives partial credit
            normalized_conf = min(1.0, self._ema_confidence / 1.0)
            analysis_result["attention_score"] = max(0.5, normalized_conf)
            analysis_result["state"] = self.current_state

        else:
            if self.face_absence_start is None:
                self.face_absence_start = current_time

            absence_duration = current_time - self.face_absence_start
            analysis_result["seconds_since_face"] = absence_duration

            if absence_duration >= self.face_absence_timeout:
                self.current_state = AttentionState.AWAY_FROM_SCREEN
                # IMPROVEMENT: exponential decay instead of instant 0
                analysis_result["attention_score"] = max(
                    0.0,
                    0.3 * (0.5 ** (absence_duration / self.face_absence_timeout))
                )

                if not self._distraction_counted and absence_duration >= self.distraction_timeout:
                    self.distraction_events += 1
                    self._distraction_counted = True

            elif absence_duration > 0.5:
                self.current_state = AttentionState.TEMPORARILY_DISTRACTED
                # Smooth decay using EMA confidence value
                analysis_result["attention_score"] = max(
                    0.3,
                    1.0 - (absence_duration / self.face_absence_timeout)
                )

            analysis_result["state"] = self.current_state

        analysis_result["distraction_events"] = self.distraction_events
        analysis_result["total_away_duration"] = self.total_away_duration
        analysis_result["total_attentive_duration"] = self.total_attentive_duration

        self.last_update_time = current_time
        return analysis_result

    def get_attention_percentage(self) -> float:
        """
        Calculate the percentage of time the user was attentive.

        Returns:
            Attention percentage (0-100).
        """
        total_time = self.total_attentive_duration + self.total_away_duration
        if total_time == 0:
            return 100.0

        return (self.total_attentive_duration / total_time) * 100

    def reset(self):
        """Reset all metrics."""
        self.current_state = AttentionState.UNKNOWN
        self.last_face_seen_time = None
        self.face_absence_start = None
        self.distraction_events = 0
        self.total_away_duration = 0.0
        self.total_attentive_duration = 0.0
        self.last_update_time = time.time()
        self._distraction_counted = False
        self._ema_confidence = 0.0
