"""
Gaze Detector module using MediaPipe Face Mesh.
Tracks eye gaze direction using iris landmarks.

IMPROVEMENT: Per-session iris center calibration.
The first CALIBRATION_FRAMES frames where iris ratios are readable are used
to establish the individual user's personal "center" gaze position, rather
than assuming it equals the geometric center (0.5, 0.5).  Different people,
different cameras, and different camera angles all shift the resting iris
position — this calibration step corrects for all of them.
"""

import mediapipe.python.solutions.face_mesh as mp_face_mesh
import numpy as np
from typing import Optional, Dict, Any, Tuple
from enum import Enum
import config


class GazeDirection(Enum):
    """Enum for gaze direction classification."""
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    DOWN = "down"
    UP = "up"
    UNKNOWN = "unknown"


class GazeDetector:
    """
    Gaze tracking using MediaPipe Face Mesh iris landmarks.
    """

    # Key Face Mesh landmark indices
    # Left eye landmarks
    LEFT_EYE_LEFT_CORNER = 33
    LEFT_EYE_RIGHT_CORNER = 133
    LEFT_EYE_TOP = 159
    LEFT_EYE_BOTTOM = 145
    LEFT_IRIS_CENTER = 468

    # Right eye landmarks
    RIGHT_EYE_LEFT_CORNER = 362
    RIGHT_EYE_RIGHT_CORNER = 263
    RIGHT_EYE_TOP = 386
    RIGHT_EYE_BOTTOM = 374
    RIGHT_IRIS_CENTER = 473

    # Number of frames used to build the personal center baseline
    CALIBRATION_FRAMES = 30

    def __init__(
        self,
        min_detection_confidence: float = config.FACE_MESH_CONFIDENCE,
        min_tracking_confidence: float = config.FACE_MESH_CONFIDENCE
    ):
        """
        Initialize the gaze detector.

        Args:
            min_detection_confidence: Minimum confidence for face mesh detection.
            min_tracking_confidence: Minimum confidence for tracking.
        """
        self.face_mesh = mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # Enables iris landmarks (indices 468-477)
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

        # Classification threshold (deviation from *calibrated* center)
        self.center_threshold = config.GAZE_CENTER_THRESHOLD

        # --- Calibration state ---
        self._calib_frames = 0
        self.calibration_complete = False
        # Personal center baseline — start at geometric center, update via EMA
        self.center_h: float = 0.5
        self.center_v: float = 0.5

        self.last_gaze: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Detect gaze direction from the frame.

        Args:
            frame: BGR image from OpenCV.

        Returns:
            Dictionary containing gaze information.
        """
        rgb_frame = frame[:, :, ::-1]
        results = self.face_mesh.process(rgb_frame)

        detection_result = {
            "face_mesh_detected": False,
            "gaze_direction": GazeDirection.UNKNOWN,
            "gaze_vector": None,
            "left_eye_ratio": None,
            "right_eye_ratio": None,
            "average_ratio": None,
            "is_looking_at_camera": False,
            "calibrated": self.calibration_complete,
        }

        if not results.multi_face_landmarks:
            self.last_gaze = detection_result
            return detection_result

        landmarks = results.multi_face_landmarks[0].landmark
        detection_result["face_mesh_detected"] = True

        left_ratio = self._calculate_eye_gaze_ratio(
            landmarks,
            self.LEFT_EYE_LEFT_CORNER,
            self.LEFT_EYE_RIGHT_CORNER,
            self.LEFT_EYE_TOP,
            self.LEFT_EYE_BOTTOM,
            self.LEFT_IRIS_CENTER,
        )
        right_ratio = self._calculate_eye_gaze_ratio(
            landmarks,
            self.RIGHT_EYE_LEFT_CORNER,
            self.RIGHT_EYE_RIGHT_CORNER,
            self.RIGHT_EYE_TOP,
            self.RIGHT_EYE_BOTTOM,
            self.RIGHT_IRIS_CENTER,
        )

        if left_ratio is not None and right_ratio is not None:
            detection_result["left_eye_ratio"] = left_ratio
            detection_result["right_eye_ratio"] = right_ratio

            avg_h = (left_ratio["horizontal"] + right_ratio["horizontal"]) / 2
            avg_v = (left_ratio["vertical"] + right_ratio["vertical"]) / 2

            detection_result["average_ratio"] = {"horizontal": avg_h, "vertical": avg_v}
            detection_result["gaze_vector"] = (avg_h, avg_v)

            # Update personal center calibration during the first N frames
            self._update_calibration(avg_h, avg_v)

            # Classify relative to calibrated personal center
            detection_result["gaze_direction"] = self._classify_gaze(avg_h, avg_v)
            detection_result["is_looking_at_camera"] = (
                detection_result["gaze_direction"] == GazeDirection.CENTER
            )

        detection_result["calibrated"] = self.calibration_complete
        self.last_gaze = detection_result
        return detection_result

    def reset_calibration(self):
        """Reset the iris center calibration (call at session start)."""
        self._calib_frames = 0
        self.calibration_complete = False
        self.center_h = 0.5
        self.center_v = 0.5

    def get_gaze_direction_string(self) -> str:
        """Get the current gaze direction as a string."""
        if self.last_gaze is None:
            return "unknown"
        return self.last_gaze["gaze_direction"].value

    def close(self):
        """Release resources."""
        self.face_mesh.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _update_calibration(self, h: float, v: float):
        """
        Accumulate frames to build a personal iris center baseline using EMA.

        Uses an exponential moving average so that later observations (when the
        user is more settled) contribute progressively more than early frames.
        """
        if self.calibration_complete:
            return

        self._calib_frames += 1

        # EMA alpha — heavier weight on recent frames
        alpha = 2.0 / (self.CALIBRATION_FRAMES + 1)
        self.center_h = self.center_h * (1 - alpha) + h * alpha
        self.center_v = self.center_v * (1 - alpha) + v * alpha

        if self._calib_frames >= self.CALIBRATION_FRAMES:
            self.calibration_complete = True

    def _calculate_eye_gaze_ratio(
        self,
        landmarks,
        left_corner_idx: int,
        right_corner_idx: int,
        top_idx: int,
        bottom_idx: int,
        iris_center_idx: int,
    ) -> Optional[Dict[str, float]]:
        """
        Calculate gaze ratio for a single eye.

        The ratio indicates the position of the iris within the eye bounds.
          Horizontal: 0.0 = looking left, 0.5 = geometric center, 1.0 = right
          Vertical:   0.0 = looking up,   0.5 = geometric center, 1.0 = down

        Returns:
            Dictionary with horizontal and vertical ratios, or None.
        """
        try:
            left_corner = landmarks[left_corner_idx]
            right_corner = landmarks[right_corner_idx]
            top = landmarks[top_idx]
            bottom = landmarks[bottom_idx]
            iris_center = landmarks[iris_center_idx]

            eye_width = right_corner.x - left_corner.x
            eye_height = bottom.y - top.y

            if eye_width <= 0 or eye_height <= 0:
                return None

            horizontal_ratio = (iris_center.x - left_corner.x) / eye_width
            vertical_ratio = (iris_center.y - top.y) / eye_height

            # Clamp to valid range
            horizontal_ratio = max(0.0, min(1.0, horizontal_ratio))
            vertical_ratio = max(0.0, min(1.0, vertical_ratio))

            return {"horizontal": horizontal_ratio, "vertical": vertical_ratio}

        except (IndexError, ZeroDivisionError):
            return None

    def _classify_gaze(self, horizontal: float, vertical: float) -> GazeDirection:
        """
        Classify gaze direction based on deviation from the *calibrated* center.

        Uses self.center_h / self.center_v (personal baseline) instead of the
        hardcoded 0.5 assumption used in the original implementation.

        Args:
            horizontal: Horizontal iris ratio (0-1).
            vertical:   Vertical iris ratio (0-1).

        Returns:
            GazeDirection enum value.
        """
        h_deviation = horizontal - self.center_h
        v_deviation = vertical - self.center_v

        if (abs(h_deviation) < self.center_threshold and
                abs(v_deviation) < self.center_threshold):
            return GazeDirection.CENTER

        if abs(h_deviation) > abs(v_deviation):
            if h_deviation < -self.center_threshold:
                return GazeDirection.LEFT
            elif h_deviation > self.center_threshold:
                return GazeDirection.RIGHT
        else:
            if v_deviation < -self.center_threshold:
                return GazeDirection.UP
            elif v_deviation > self.center_threshold:
                return GazeDirection.DOWN

        return GazeDirection.CENTER
