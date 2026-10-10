"""
Behavioral Analysis Engine - Main Orchestrator.
Combines all components into a unified interface for behavioral analysis.
"""

import time
from typing import Dict, Any, Optional, Callable
import numpy as np

# Import camera
from camera import CameraCapture

# Import detectors
from detectors.face_detector import FaceDetector
from detectors.pose_detector import PoseDetector
from detectors.gaze_detector import GazeDetector

# Import analyzers
from analyzers.attention_analyzer import AttentionAnalyzer
from analyzers.posture_analyzer import PostureAnalyzer
from analyzers.gaze_analyzer import GazeAnalyzer
from analyzers.movement_analyzer import MovementAnalyzer

# Import scoring
from scoring.confidence_scorer import ConfidenceScorer
from scoring.feedback_generator import FeedbackGenerator

# Import analytics
from analytics.session_analytics import SessionAnalytics
from analytics.report_generator import ReportGenerator

import config


class BehaviorAnalysisEngine:
    """
    Main orchestrator for behavioral analysis.
    Provides a unified interface for analyzing user behavior during interviews.
    
    Can be used as:
    1. Standalone module with analyze_frame() method
    2. With built-in camera handling using run() method
    3. Imported and integrated into other applications
    """
    
    def __init__(self, use_camera: bool = True):
        """
        Initialize the behavior analysis engine.
        
        Args:
            use_camera: Whether to initialize built-in camera capture.
        """
        self.use_camera = use_camera
        
        # Initialize detectors
        self.face_detector = FaceDetector()
        self.pose_detector = PoseDetector()
        self.gaze_detector = GazeDetector()
        
        # Initialize analyzers
        self.attention_analyzer = AttentionAnalyzer()
        self.posture_analyzer = PostureAnalyzer()
        self.gaze_analyzer = GazeAnalyzer()
        self.movement_analyzer = MovementAnalyzer()
        
        # Initialize scoring
        self.confidence_scorer = ConfidenceScorer()
        self.feedback_generator = FeedbackGenerator()
        
        # Initialize analytics
        self.session_analytics = SessionAnalytics()
        self.report_generator = ReportGenerator()
        
        # Camera (optional)
        self.camera: Optional[CameraCapture] = None
        if use_camera:
            self.camera = CameraCapture()
        
        # State
        self.is_running = False
        self.frame_count = 0
        self.start_time: Optional[float] = None
        
        # Callbacks
        self._on_frame_callback: Optional[Callable] = None
        self._on_feedback_callback: Optional[Callable] = None
    
    def analyze_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Analyze a single frame and return all behavioral metrics.
        
        This is the main entry point for external integration.
        Pass in a BGR frame from OpenCV and get comprehensive analysis.
        
        Args:
            frame: BGR image (numpy array from cv2).
            
        Returns:
            Dictionary containing all analysis results.
        """
        self.frame_count += 1
        
        # Run detectors
        face_result = self.face_detector.detect(frame)
        pose_result = self.pose_detector.detect(frame)
        gaze_result = self.gaze_detector.detect(frame)
        
        # Run analyzers
        attention_result = self.attention_analyzer.analyze(face_result)
        posture_result = self.posture_analyzer.analyze(pose_result)
        gaze_analysis = self.gaze_analyzer.analyze(gaze_result)
        movement_result = self.movement_analyzer.analyze(pose_result)
        
        # Compute confidence score
        confidence_result = self.confidence_scorer.compute_score(
            attention_result,
            gaze_analysis,
            posture_result,
            movement_result
        )
        
        # Generate feedback
        feedback = self.feedback_generator.generate(
            attention_result,
            gaze_analysis,
            posture_result,
            movement_result,
            confidence_result
        )
        
        # Record analytics
        self.session_analytics.record(
            attention_result,
            gaze_analysis,
            posture_result,
            movement_result,
            confidence_result
        )
        
        # Compile results
        result = {
            "frame_number": self.frame_count,
            "detections": {
                "face": face_result,
                "pose": pose_result,
                "gaze": gaze_result
            },
            "analysis": {
                "attention": attention_result,
                "posture": posture_result,
                "eye_contact": gaze_analysis,
                "movement": movement_result
            },
            "scores": {
                "confidence": confidence_result,
                "attention_score": attention_result.get("attention_score", 0.5),
                "posture_score": posture_result.get("posture_score", 0.5),
                "eye_contact_score": gaze_analysis.get("eye_contact_score", 0.5),
                "movement_score": movement_result.get("movement_score", 0.5)
            },
            "feedback": {
                "messages": [fb.message for fb in feedback],
                "primary": self.feedback_generator.get_primary_feedback()
            }
        }
        
        return result
    
    def get_current_state(self) -> Dict[str, Any]:
        """
        Get a simplified view of the current behavioral state.
        Useful for UI updates and quick status checks.
        
        Returns:
            Simplified state dictionary.
        """
        summary = self.session_analytics.get_summary()
        
        return {
            "confidence_score": round(self.confidence_scorer.current_score, 1),
            "confidence_level": self.confidence_scorer._get_level(
                self.confidence_scorer.current_score
            ).value,
            "is_attentive": self.attention_analyzer.current_state.value == "fully_attentive",
            "posture_calibrated": self.posture_analyzer.calibration_complete,
            "feedback": self.feedback_generator.get_primary_feedback(),
            "session_duration": summary.get("session_duration_seconds", 0),
            "frames_processed": self.frame_count
        }
    
    def start_session(self):
        """Start a new analysis session."""
        self.is_running = True
        self.frame_count = 0
        self.start_time = time.time()
        self.session_analytics.start_session()
        # Reset per-session gaze calibration so each user gets their own
        # personal iris center baseline instead of the hardcoded (0.5, 0.5).
        if hasattr(self.gaze_detector, 'reset_calibration'):
            self.gaze_detector.reset_calibration()
    
    def end_session(self) -> Dict[str, Any]:
        """
        End the current session and generate report.
        
        Returns:
            Final session report.
        """
        self.is_running = False
        
        summary = self.session_analytics.get_summary()
        time_series = self.session_analytics.get_time_series()
        
        report = self.report_generator.generate_report(
            summary,
            time_series,
            include_time_series=True
        )
        
        return report
    
    def get_json_report(self, include_time_series: bool = False) -> str:
        """
        Get JSON-formatted session report.
        
        Args:
            include_time_series: Whether to include detailed time-series data.
            
        Returns:
            JSON string.
        """
        summary = self.session_analytics.get_summary()
        time_series = self.session_analytics.get_time_series() if include_time_series else None
        
        return self.report_generator.generate_json_report(
            summary,
            time_series,
            include_time_series
        )
    
    def reset(self):
        """Reset all components for a new session."""
        self.attention_analyzer.reset()
        self.posture_analyzer.reset()
        self.gaze_analyzer.reset()
        self.movement_analyzer.reset()
        self.confidence_scorer.reset()
        self.feedback_generator.reset()
        self.session_analytics.reset()
        self.frame_count = 0
        self.start_time = None
        # Reset gaze calibration so the new session builds a fresh iris baseline
        if hasattr(self.gaze_detector, 'reset_calibration'):
            self.gaze_detector.reset_calibration()
    
    def set_on_frame_callback(self, callback: Callable):
        """
        Set callback to be called after each frame is analyzed.
        
        Args:
            callback: Function that receives (frame, analysis_result).
        """
        self._on_frame_callback = callback
    
    def set_on_feedback_callback(self, callback: Callable):
        """
        Set callback to be called when new feedback is generated.
        
        Args:
            callback: Function that receives feedback message string.
        """
        self._on_feedback_callback = callback
    
    def close(self):
        """Release all resources."""
        self.face_detector.close()
        self.pose_detector.close()
        self.gaze_detector.close()
        
        if self.camera:
            self.camera.stop()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


# Convenience function for quick integration
def create_engine(with_camera: bool = False) -> BehaviorAnalysisEngine:
    """
    Factory function to create a BehaviorAnalysisEngine.
    
    Args:
        with_camera: Whether to include built-in camera handling.
        
    Returns:
        Configured BehaviorAnalysisEngine instance.
    """
    return BehaviorAnalysisEngine(use_camera=with_camera)
