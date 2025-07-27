"""
Latency tracking for monitoring real-time performance
Tracks response times throughout the audio pipeline
"""
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    """Container for latency metrics"""
    audio_receive_times: List[float] = field(default_factory=list)
    transcript_process_times: List[float] = field(default_factory=list)
    response_generation_times: List[float] = field(default_factory=list)
    tts_generation_times: List[float] = field(default_factory=list)
    audio_send_times: List[float] = field(default_factory=list)
    end_to_end_times: List[float] = field(default_factory=list)
    
    def get_summary(self) -> Dict[str, Dict[str, float]]:
        """
        Get summary statistics for all metrics
        
        Returns:
            Dictionary with mean, median, min, max for each metric
        """
        summary = {}
        
        metric_names = {
            "audio_receive": self.audio_receive_times,
            "transcript_process": self.transcript_process_times,
            "response_generation": self.response_generation_times,
            "tts_generation": self.tts_generation_times,
            "audio_send": self.audio_send_times,
            "end_to_end": self.end_to_end_times
        }
        
        for name, times in metric_names.items():
            if times:
                summary[name] = {
                    "mean": statistics.mean(times),
                    "median": statistics.median(times),
                    "min": min(times),
                    "max": max(times),
                    "count": len(times)
                }
            else:
                summary[name] = {
                    "mean": 0.0,
                    "median": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "count": 0
                }
        
        return summary


class LatencyTracker:
    """
    Tracks latency at various points in the audio processing pipeline
    """
    
    def __init__(self, stream_id: str, max_samples: int = 1000):
        """
        Initialize latency tracker
        
        Args:
            stream_id: Unique identifier for the stream
            max_samples: Maximum number of samples to keep per metric
        """
        self.stream_id = stream_id
        self.max_samples = max_samples
        self.metrics = LatencyMetrics()
        
        # Timing markers for ongoing operations
        self.markers: Dict[str, float] = {}
        
        # Track pipeline stages
        self.audio_received_at: Optional[float] = None
        self.transcript_started_at: Optional[float] = None
        self.response_started_at: Optional[float] = None
        self.tts_started_at: Optional[float] = None
        self.audio_sent_at: Optional[float] = None
        
        logger.info(f"LatencyTracker initialized for stream {stream_id}")
    
    def mark(self, marker_name: str):
        """
        Set a timing marker
        
        Args:
            marker_name: Name of the marker
        """
        self.markers[marker_name] = time.time()
    
    def measure(self, start_marker: str, end_marker: str) -> Optional[float]:
        """
        Measure time between two markers
        
        Args:
            start_marker: Name of start marker
            end_marker: Name of end marker
            
        Returns:
            Time in milliseconds or None if markers not found
        """
        start = self.markers.get(start_marker)
        end = self.markers.get(end_marker)
        
        if start is None or end is None:
            return None
        
        return (end - start) * 1000  # Convert to milliseconds
    
    def record_audio_received(self):
        """Record when audio is received from Twilio"""
        now = time.time()
        self.audio_received_at = now
        
        # If we have a complete cycle, calculate end-to-end latency
        if hasattr(self, '_last_audio_sent_at'):
            end_to_end = (now - self._last_audio_sent_at) * 1000
            self._add_metric('end_to_end_times', end_to_end)
    
    def record_transcript_started(self):
        """Record when transcript processing starts"""
        now = time.time()
        self.transcript_started_at = now
        
        if self.audio_received_at:
            latency = (now - self.audio_received_at) * 1000
            self._add_metric('audio_receive_times', latency)
    
    def record_transcript_processed(self):
        """Record when transcript processing completes"""
        now = time.time()
        
        if self.transcript_started_at:
            latency = (now - self.transcript_started_at) * 1000
            self._add_metric('transcript_process_times', latency)
            self.response_started_at = now
    
    def record_response_generated(self):
        """Record when AI response is generated"""
        now = time.time()
        
        if self.response_started_at:
            latency = (now - self.response_started_at) * 1000
            self._add_metric('response_generation_times', latency)
            self.tts_started_at = now
    
    def record_tts_generated(self):
        """Record when TTS audio is generated"""
        now = time.time()
        
        if self.tts_started_at:
            latency = (now - self.tts_started_at) * 1000
            self._add_metric('tts_generation_times', latency)
    
    def record_audio_sent(self):
        """Record when audio is sent back to Twilio"""
        now = time.time()
        self.audio_sent_at = now
        self._last_audio_sent_at = now
        
        if self.tts_started_at:
            latency = (now - self.tts_started_at) * 1000
            self._add_metric('audio_send_times', latency)
        
        # Calculate total response time
        if self.audio_received_at:
            total_latency = (now - self.audio_received_at) * 1000
            logger.debug(f"Total response latency: {total_latency:.2f}ms")
    
    def _add_metric(self, metric_name: str, value: float):
        """
        Add a metric value, maintaining max samples limit
        
        Args:
            metric_name: Name of the metric list
            value: Value to add
        """
        metric_list = getattr(self.metrics, metric_name)
        metric_list.append(value)
        
        # Trim to max samples
        if len(metric_list) > self.max_samples:
            metric_list.pop(0)
        
        # Log if latency is high
        if value > 1500:  # More than 1.5 seconds
            logger.warning(f"High latency detected for {metric_name}: {value:.2f}ms")
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics and statistics
        
        Returns:
            Dictionary with metrics and statistics
        """
        summary = self.metrics.get_summary()
        
        # Calculate average response time
        avg_response_time = 0.0
        if summary.get('end_to_end', {}).get('count', 0) > 0:
            avg_response_time = summary['end_to_end']['mean']
        
        return {
            "stream_id": self.stream_id,
            "timestamp": datetime.utcnow().isoformat(),
            "avg_response_time": avg_response_time,
            "metrics_summary": summary,
            "active_markers": list(self.markers.keys())
        }
    
    def reset(self):
        """Reset all metrics and markers"""
        self.metrics = LatencyMetrics()
        self.markers.clear()
        self.audio_received_at = None
        self.transcript_started_at = None
        self.response_started_at = None
        self.tts_started_at = None
        self.audio_sent_at = None
        logger.debug(f"LatencyTracker reset for stream {self.stream_id}")