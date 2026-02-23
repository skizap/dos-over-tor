"""Summary reporting module for attack statistics display.

This module provides the SummaryReporter class for displaying formatted
attack summary reports. It handles metrics formatting, timestamp conversion,
and human-readable byte/duration display.

Usage Example:
    >>> from app.reporter import SummaryReporter
    >>> from app.models import AttackSummary
    >>> 
    >>> reporter = SummaryReporter()
    >>> summary = AttackSummary(
    ...     total_hits=1000,
    ...     total_requests=1200,
    ...     duration_seconds=60.5,
    ...     hits_per_second=16.53
    ... )
    >>> reporter.display(summary)
    # Displays formatted attack summary to console
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import AttackSummary

import app.console


class SummaryReporter:
    """Displays formatted attack summary reports.
    
    This class handles the display of AttackSummary data in a human-readable
    format with proper formatting for:
    - Time durations (seconds, minutes, hours)
    - Byte counts (KB, MB, GB, TB)
    - Timestamps (human-readable dates)
    - Response times (ms)
    - HTTP status code distribution
    
    The reporter uses the app.console module for consistent output formatting
    and follows the established codebase patterns for console output.
    
    Attributes:
        None - This is a stateless reporter class.
    """
    
    def display(self, summary: 'AttackSummary') -> None:
        """Display formatted attack summary.
        
        Outputs a comprehensive summary of attack statistics including:
        - Timing information (duration, start/end times)
        - Cumulative metrics (hits, requests, bytes, errors)
        - Performance metrics (hits/sec, response times)
        - HTTP status distribution
        - Active counters (threads, sockets)
        
        Args:
            summary: AttackSummary containing all attack statistics to display.
            
        Example:
            >>> reporter = SummaryReporter()
            >>> summary = AttackSummary(
            ...     total_hits=5000,
            ...     total_requests=5500,
            ...     duration_seconds=120.0,
            ...     hits_per_second=41.67,
            ...     avg_response_time_ms=245.5
            ... )
            >>> reporter.display(summary)
            # Displays formatted summary to console
        """
        # Header
        app.console.hr()
        app.console.system("Attack Summary")
        app.console.hr()
        
        # Timing Information
        app.console.system("Timing:")
        duration_str = self._format_duration(summary.duration_seconds)
        app.console.log(f"  Duration: {duration_str}")
        
        if summary.start_time is not None:
            start_str = self._format_timestamp(summary.start_time)
            app.console.log(f"  Start Time: {start_str}")
        
        if summary.end_time is not None:
            end_str = self._format_timestamp(summary.end_time)
            app.console.log(f"  End Time: {end_str}")
        
        # Cumulative Metrics
        app.console.system("Cumulative Metrics:")
        app.console.log(f"  Total Hits: {summary.total_hits}")
        app.console.log(f"  Total Requests: {summary.total_requests}")
        
        bytes_sent_str = self._format_bytes(summary.total_bytes_sent)
        app.console.log(f"  Bytes Sent: {bytes_sent_str}")
        
        bytes_received_str = self._format_bytes(summary.total_bytes_received)
        app.console.log(f"  Bytes Received: {bytes_received_str}")
        
        # Error rate calculation
        if summary.total_requests > 0:
            error_rate = (summary.total_errors / summary.total_requests) * 100
            app.console.log(f"  Total Errors: {summary.total_errors} ({error_rate:.2f}%)")
        else:
            app.console.log(f"  Total Errors: {summary.total_errors} (0.00%)")
        
        # Performance Metrics
        app.console.system("Performance Metrics:")
        app.console.log(f"  Hits per Second: {summary.hits_per_second:.2f} hits/sec")
        
        # Response times (handle None for slowloris mode)
        if summary.avg_response_time_ms is not None:
            app.console.log(f"  Avg Response Time: {summary.avg_response_time_ms:.2f} ms")
        else:
            app.console.log("  Avg Response Time: N/A")
        
        if summary.min_response_time_ms is not None:
            app.console.log(f"  Min Response Time: {summary.min_response_time_ms:.2f} ms")
        else:
            app.console.log("  Min Response Time: N/A")
        
        if summary.max_response_time_ms is not None:
            app.console.log(f"  Max Response Time: {summary.max_response_time_ms:.2f} ms")
        else:
            app.console.log("  Max Response Time: N/A")
        
        # HTTP Status Distribution
        app.console.system("HTTP Status Distribution:")
        if summary.http_status_counts:
            for status_code, count in sorted(summary.http_status_counts.items()):
                app.console.log(f"  HTTP {status_code}: {count} requests")
        else:
            app.console.log("  No HTTP status codes recorded")
        
        # Active Counters
        app.console.system("Active Counters:")
        app.console.log(f"  Active Threads: {summary.active_threads}")
        
        # Only show active sockets if > 0 (relevant for slowloris mode)
        if summary.active_sockets > 0:
            app.console.log(f"  Active Sockets: {summary.active_sockets}")
        
        # Footer
        app.console.hr()
    
    def _format_bytes(self, bytes_count: int) -> str:
        """Convert bytes to human-readable format.
        
        Converts a byte count to the most appropriate unit (B, KB, MB, GB, TB)
        with 2 decimal places for fractional units.
        
        Args:
            bytes_count: Number of bytes to format.
            
        Returns:
            Formatted string with appropriate unit (e.g., "1.50 MB").
            
        Example:
            >>> reporter._format_bytes(1536)
            '1.50 KB'
            >>> reporter._format_bytes(1572864)
            '1.50 MB'
        """
        if bytes_count < 0:
            return "0 B"
        
        # Define units and their byte thresholds
        units = [
            (1024 ** 4, "TB"),
            (1024 ** 3, "GB"),
            (1024 ** 2, "MB"),
            (1024 ** 1, "KB"),
            (1, "B")
        ]
        
        for threshold, unit in units:
            if bytes_count >= threshold:
                value = bytes_count / threshold
                return f"{value:.2f} {unit}"
        
        return "0 B"
    
    def _format_duration(self, seconds) -> str:
        """Format duration in seconds to human-readable string.
        
        Converts seconds to the most readable format:
        - If < 60 seconds: "X.XX seconds"
        - If >= 60 seconds: "Xh Ym Zs" format
        - Handles None values gracefully
        
        Args:
            seconds: Duration in seconds, or None.
            
        Returns:
            Formatted duration string.
            
        Example:
            >>> reporter._format_duration(45.5)
            '45.50 seconds'
            >>> reporter._format_duration(125.5)
            '0h 2m 5s'
        """
        if seconds is None:
            return "N/A"
        
        if seconds < 60:
            return f"{seconds:.2f} seconds"
        
        # Convert to hours, minutes, seconds
        hours = int(seconds // 3600)
        remaining = seconds % 3600
        minutes = int(remaining // 60)
        secs = int(remaining % 60)
        
        return f"{hours}h {minutes}m {secs}s"
    
    def _format_timestamp(self, unix_timestamp) -> str:
        """Convert Unix timestamp to human-readable format.
        
        Args:
            unix_timestamp: Unix timestamp in seconds, or None.
            
        Returns:
            Formatted timestamp string (YYYY-MM-DD HH:MM:SS), or "N/A" if None.
            
        Example:
            >>> reporter._format_timestamp(1609459200)
            '2021-01-01 00:00:00'
        """
        if unix_timestamp is None:
            return "N/A"
        
        dt = datetime.fromtimestamp(unix_timestamp)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
