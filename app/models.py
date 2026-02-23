"""
Data models for the DoS-over-Tor attack framework.

This module defines the core dataclasses used throughout the application:
- AttackResult: Individual attack round results
- AttackConfig: Consolidated attack configuration
- AttackSummary: End-of-run cumulative statistics
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class AttackResult:
    """
    Represents the result of an individual attack round.
    
    This dataclass replaces the previous `(num_hits, http_status)` tuple pattern
    used throughout the codebase. It provides comprehensive tracking of each
    attack attempt including hits, HTTP status, data transfer, response time,
    and error counts.
    
    Attributes:
        num_hits: Number of successful hits in this attack round.
        http_status: HTTP status code returned (e.g., 200, 404, 500).
            None if the connection failed before receiving a response.
        bytes_sent: Estimated bytes sent in this attack round.
            This is a best-effort estimate and may not be exact.
        bytes_received: Estimated bytes received in this attack round.
            This is a best-effort estimate and may not be exact.
        response_time_ms: Response time in milliseconds.
            None for attacks like slowloris that don't track response times.
        errors: Count of errors/exceptions encountered during this round.
    """
    num_hits: int = 0
    http_status: Optional[int] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    response_time_ms: Optional[float] = None
    errors: int = 0


@dataclass
class AttackConfig:
    """
    Consolidated configuration for an attack run.
    
    This dataclass centralizes all configuration parameters that were previously
    scattered across CLI initialization, weapon factories, and individual weapons.
    It supports all attack modes: 'singleshot', 'fullauto', and 'slowloris'.
    
    Core Configuration:
        mode: Attack mode - 'singleshot', 'fullauto', or 'slowloris'.
        target: Target URL or domain to attack.
        num_threads: Number of soldier threads to spawn.
        http_method: HTTP method to use for requests (e.g., 'GET', 'POST').
        cache_buster: Whether to add cache-busting query strings to requests.
    
    Tor Configuration:
        tor_address: Tor service address (typically '127.0.0.1').
        tor_proxy_port: Tor SOCKS proxy port (default: 9050).
        tor_ctrl_port: Tor control port for identity rotation (default: 9051).
        identity_rotation_interval: Seconds between Tor identity rotations.
            None for no rotation.
    
    Mode-Specific Configuration:
        slowloris_num_sockets: Number of sockets per thread for slowloris mode.
        fullauto_max_urls: Maximum URLs to discover per thread in fullauto mode (default: 500).
        fullauto_max_time: Maximum crawl time in seconds per thread in fullauto mode (default: 180).
    """
    # Core configuration
    mode: str
    target: str
    num_threads: int = 10
    http_method: str = 'GET'
    cache_buster: bool = False
    
    # Tor configuration
    tor_address: str = '127.0.0.1'
    tor_proxy_port: int = 9050
    tor_ctrl_port: int = 9051
    identity_rotation_interval: Optional[int] = None
    
    # Mode-specific configuration
    slowloris_num_sockets: int = 100
    fullauto_max_urls: int = 500
    fullauto_max_time: int = 180


@dataclass
class AttackSummary:
    """
    End-of-run cumulative statistics for an attack session.
    
    This dataclass aggregates results from all attack rounds across all threads
    to provide comprehensive reporting. It's designed to be populated throughout
    an attack run and finalized when the attack completes.
    
    Note: Response time fields (avg_response_time_ms, min_response_time_ms,
    max_response_time_ms) will be None for slowloris attacks as they don't
    track individual response times.
    
    Cumulative Metrics:
        total_hits: Total number of successful hits across all threads.
        total_bytes_sent: Total bytes sent across all threads.
        total_bytes_received: Total bytes received across all threads.
        total_errors: Total errors encountered across all threads.
        total_requests: Total number of requests made.
    
    Performance Metrics:
        avg_response_time_ms: Average response time in milliseconds.
        min_response_time_ms: Minimum response time observed.
        max_response_time_ms: Maximum response time observed.
        hits_per_second: Average hits per second.
    
    Status Tracking:
        http_status_counts: Dictionary mapping HTTP status codes to counts.
            Uses field(default_factory=dict) to avoid mutable default issues.
        active_threads: Number of currently active threads.
        active_sockets: Number of currently active sockets (for slowloris).
    
    Timing Information:
        start_time: Unix timestamp when attack started.
        end_time: Unix timestamp when attack ended.
        duration_seconds: Total duration of the attack in seconds.
    """
    # Cumulative metrics
    total_hits: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    total_errors: int = 0
    total_requests: int = 0
    
    # Performance metrics
    avg_response_time_ms: Optional[float] = None
    min_response_time_ms: Optional[float] = None
    max_response_time_ms: Optional[float] = None
    hits_per_second: float = 0.0
    
    # Status tracking
    http_status_counts: dict[int, int] = field(default_factory=dict)
    active_threads: int = 0
    active_sockets: int = 0
    
    # Timing information
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration_seconds: Optional[float] = None
