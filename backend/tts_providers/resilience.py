"""
TTS Resilience System

Provides robust fault tolerance for TTS operations:
- Health monitoring with automatic recovery detection
- Circuit breaker pattern to prevent cascade failures
- Retry queue for failed generations
- User notifications on service issues
- Metrics collection for monitoring
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import json
from pathlib import Path

from utils.logger import logger


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Provider failing, reject requests
    HALF_OPEN = "half_open"  # Testing if provider recovered


@dataclass
class ProviderHealth:
    """Health metrics for a TTS provider"""
    provider_name: str
    is_healthy: bool = True
    consecutive_failures: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_check_time: Optional[datetime] = None
    average_latency_ms: float = 0.0
    circuit_state: CircuitState = CircuitState.CLOSED
    error_messages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "is_healthy": self.is_healthy,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "circuit_state": self.circuit_state.value,
            "average_latency_ms": self.average_latency_ms,
            "success_rate": self._success_rate(),
        }

    def _success_rate(self) -> float:
        total = self.total_failures + self.total_successes
        if total == 0:
            return 1.0
        return self.total_successes / total


@dataclass
class RetryableRequest:
    """A TTS request that can be retried"""
    request_id: str
    text: str
    voice: str
    output_path: str
    provider: Optional[str]
    created_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    callback: Optional[Callable] = None

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries


class CircuitBreaker:
    """
    Circuit breaker implementation for TTS providers.

    Prevents repeated calls to failing providers, allowing them
    time to recover while automatically testing for recovery.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds
        self.half_open_max_calls = half_open_max_calls

        self._states: Dict[str, CircuitState] = {}
        self._failure_counts: Dict[str, int] = {}
        self._last_failure_times: Dict[str, datetime] = {}
        self._half_open_calls: Dict[str, int] = {}

    def get_state(self, provider: str) -> CircuitState:
        """Get current circuit state for a provider"""
        if provider not in self._states:
            self._states[provider] = CircuitState.CLOSED
            return CircuitState.CLOSED

        state = self._states[provider]

        # Check if we should transition from OPEN to HALF_OPEN
        if state == CircuitState.OPEN:
            last_failure = self._last_failure_times.get(provider)
            if last_failure:
                elapsed = (datetime.now() - last_failure).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._states[provider] = CircuitState.HALF_OPEN
                    self._half_open_calls[provider] = 0
                    logger.info(f"Circuit for {provider} transitioning to HALF_OPEN")
                    return CircuitState.HALF_OPEN

        return state

    def is_allowed(self, provider: str) -> bool:
        """Check if a request to the provider is allowed"""
        state = self.get_state(provider)

        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            return False
        else:  # HALF_OPEN
            calls = self._half_open_calls.get(provider, 0)
            return calls < self.half_open_max_calls

    def record_success(self, provider: str) -> None:
        """Record a successful call"""
        state = self.get_state(provider)

        if state == CircuitState.HALF_OPEN:
            self._half_open_calls[provider] = self._half_open_calls.get(provider, 0) + 1
            if self._half_open_calls[provider] >= self.half_open_max_calls:
                # Enough successes in half-open, close the circuit
                self._states[provider] = CircuitState.CLOSED
                self._failure_counts[provider] = 0
                logger.info(f"Circuit for {provider} CLOSED after recovery")

        elif state == CircuitState.CLOSED:
            # Reset failure count on success
            self._failure_counts[provider] = 0

    def record_failure(self, provider: str) -> None:
        """Record a failed call"""
        self._failure_counts[provider] = self._failure_counts.get(provider, 0) + 1
        self._last_failure_times[provider] = datetime.now()

        state = self.get_state(provider)

        if state == CircuitState.HALF_OPEN:
            # Failure during recovery test, reopen circuit
            self._states[provider] = CircuitState.OPEN
            logger.warning(f"Circuit for {provider} reopened after HALF_OPEN failure")

        elif state == CircuitState.CLOSED:
            if self._failure_counts[provider] >= self.failure_threshold:
                self._states[provider] = CircuitState.OPEN
                logger.warning(
                    f"Circuit for {provider} OPENED after {self.failure_threshold} failures"
                )


class TTSHealthMonitor:
    """
    Monitors health of TTS providers and triggers alerts.

    Performs periodic health checks and maintains provider metrics.
    """

    def __init__(
        self,
        check_interval: int = 60,  # seconds
        alert_callback: Optional[Callable[[str, str], Awaitable[None]]] = None
    ):
        self.check_interval = check_interval
        self.alert_callback = alert_callback

        self._health_data: Dict[str, ProviderHealth] = {}
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._latency_samples: Dict[str, deque] = {}
        self._max_latency_samples = 100

    def get_health(self, provider: str) -> ProviderHealth:
        """Get health data for a provider"""
        if provider not in self._health_data:
            self._health_data[provider] = ProviderHealth(provider_name=provider)
        return self._health_data[provider]

    def record_success(self, provider: str, latency_ms: float) -> None:
        """Record a successful TTS generation"""
        health = self.get_health(provider)
        health.is_healthy = True
        health.consecutive_failures = 0
        health.total_successes += 1
        health.last_success_time = datetime.now()

        # Update latency tracking
        if provider not in self._latency_samples:
            self._latency_samples[provider] = deque(maxlen=self._max_latency_samples)
        self._latency_samples[provider].append(latency_ms)

        # Calculate average latency
        samples = list(self._latency_samples[provider])
        health.average_latency_ms = sum(samples) / len(samples) if samples else 0

    def record_failure(self, provider: str, error: str) -> None:
        """Record a failed TTS generation"""
        health = self.get_health(provider)
        health.consecutive_failures += 1
        health.total_failures += 1
        health.last_failure_time = datetime.now()

        # Keep last 10 error messages
        health.error_messages.append(f"{datetime.now().isoformat()}: {error}")
        health.error_messages = health.error_messages[-10:]

        # Mark unhealthy after 3 consecutive failures
        if health.consecutive_failures >= 3:
            if health.is_healthy:
                health.is_healthy = False
                self._trigger_alert(
                    provider,
                    f"Provider {provider} marked unhealthy after {health.consecutive_failures} failures"
                )

    def _trigger_alert(self, provider: str, message: str) -> None:
        """Trigger an alert for provider issues"""
        logger.warning(f"TTS Alert: {message}")

        if self.alert_callback:
            asyncio.create_task(self.alert_callback(provider, message))

    async def start_monitoring(self, check_func: Callable[[str], Awaitable[bool]]) -> None:
        """Start periodic health monitoring"""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(
            self._monitoring_loop(check_func)
        )
        logger.info("TTS health monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop health monitoring"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("TTS health monitoring stopped")

    async def _monitoring_loop(self, check_func: Callable[[str], Awaitable[bool]]) -> None:
        """Background monitoring loop"""
        while self._monitoring:
            try:
                for provider in list(self._health_data.keys()):
                    try:
                        is_available = await check_func(provider)
                        health = self.get_health(provider)
                        health.last_check_time = datetime.now()

                        if is_available and not health.is_healthy:
                            # Provider recovered
                            health.is_healthy = True
                            health.consecutive_failures = 0
                            self._trigger_alert(
                                provider,
                                f"Provider {provider} has recovered"
                            )
                    except Exception as e:
                        logger.debug(f"Health check failed for {provider}: {e}")

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(5)

    def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health data for all providers"""
        return {
            provider: health.to_dict()
            for provider, health in self._health_data.items()
        }


class TTSRetryQueue:
    """
    Queue for retrying failed TTS generations.

    Stores failed requests and retries them with exponential backoff.
    """

    def __init__(
        self,
        max_queue_size: int = 100,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        storage_path: Optional[Path] = None
    ):
        self.max_queue_size = max_queue_size
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.storage_path = storage_path

        self._queue: deque = deque(maxlen=max_queue_size)
        self._processing = False
        self._process_task: Optional[asyncio.Task] = None

        # Load persisted queue
        if storage_path:
            self._load_queue()

    def _load_queue(self) -> None:
        """Load persisted queue from disk"""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            data = json.loads(self.storage_path.read_text())
            for item in data.get("queue", []):
                request = RetryableRequest(
                    request_id=item["request_id"],
                    text=item["text"],
                    voice=item["voice"],
                    output_path=item["output_path"],
                    provider=item.get("provider"),
                    created_at=datetime.fromisoformat(item["created_at"]),
                    retry_count=item.get("retry_count", 0),
                    max_retries=item.get("max_retries", 3),
                    last_error=item.get("last_error"),
                )
                self._queue.append(request)
            logger.info(f"Loaded {len(self._queue)} requests from retry queue")
        except Exception as e:
            logger.warning(f"Failed to load retry queue: {e}")

    def _save_queue(self) -> None:
        """Persist queue to disk"""
        if not self.storage_path:
            return

        try:
            data = {
                "queue": [
                    {
                        "request_id": r.request_id,
                        "text": r.text,
                        "voice": r.voice,
                        "output_path": r.output_path,
                        "provider": r.provider,
                        "created_at": r.created_at.isoformat(),
                        "retry_count": r.retry_count,
                        "max_retries": r.max_retries,
                        "last_error": r.last_error,
                    }
                    for r in self._queue
                ],
                "saved_at": datetime.now().isoformat(),
            }
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save retry queue: {e}")

    def add(self, request: RetryableRequest) -> bool:
        """Add a request to the retry queue"""
        if len(self._queue) >= self.max_queue_size:
            logger.warning("Retry queue full, dropping oldest request")
            self._queue.popleft()

        request.retry_count += 1
        self._queue.append(request)
        self._save_queue()

        logger.info(
            f"Added request {request.request_id} to retry queue "
            f"(attempt {request.retry_count}/{request.max_retries})"
        )
        return True

    def get_next(self) -> Optional[RetryableRequest]:
        """Get next request to retry"""
        if not self._queue:
            return None
        return self._queue.popleft()

    def _calculate_delay(self, retry_count: int) -> float:
        """Calculate exponential backoff delay"""
        delay = self.base_delay * (2 ** retry_count)
        return min(delay, self.max_delay)

    async def start_processing(
        self,
        generate_func: Callable[[RetryableRequest], Awaitable[bool]]
    ) -> None:
        """Start processing retry queue"""
        if self._processing:
            return

        self._processing = True
        self._process_task = asyncio.create_task(
            self._processing_loop(generate_func)
        )
        logger.info("TTS retry queue processing started")

    async def stop_processing(self) -> None:
        """Stop processing retry queue"""
        self._processing = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        self._save_queue()
        logger.info("TTS retry queue processing stopped")

    async def _processing_loop(
        self,
        generate_func: Callable[[RetryableRequest], Awaitable[bool]]
    ) -> None:
        """Background processing loop"""
        while self._processing:
            try:
                request = self.get_next()

                if not request:
                    await asyncio.sleep(5)
                    continue

                if not request.can_retry():
                    logger.warning(
                        f"Request {request.request_id} exceeded max retries, dropping"
                    )
                    continue

                # Calculate delay based on retry count
                delay = self._calculate_delay(request.retry_count)
                logger.info(
                    f"Retrying request {request.request_id} in {delay:.1f}s "
                    f"(attempt {request.retry_count}/{request.max_retries})"
                )
                await asyncio.sleep(delay)

                # Attempt generation
                try:
                    success = await generate_func(request)
                    if success:
                        logger.info(f"Request {request.request_id} succeeded on retry")
                        if request.callback:
                            request.callback(True, request.output_path)
                    else:
                        # Failed, add back to queue
                        self.add(request)
                except Exception as e:
                    request.last_error = str(e)
                    self.add(request)

                self._save_queue()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry queue processing error: {e}")
                await asyncio.sleep(5)

    @property
    def queue_size(self) -> int:
        """Get current queue size"""
        return len(self._queue)

    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status"""
        return {
            "size": len(self._queue),
            "max_size": self.max_queue_size,
            "is_processing": self._processing,
            "requests": [
                {
                    "request_id": r.request_id,
                    "retry_count": r.retry_count,
                    "created_at": r.created_at.isoformat(),
                    "last_error": r.last_error,
                }
                for r in list(self._queue)[:10]  # First 10 only
            ],
        }


class TTSResilienceManager:
    """
    Central manager for TTS resilience features.

    Coordinates circuit breaker, health monitoring, and retry queue.
    """

    def __init__(
        self,
        alert_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
        storage_dir: Optional[Path] = None
    ):
        self.circuit_breaker = CircuitBreaker()
        self.health_monitor = TTSHealthMonitor(alert_callback=alert_callback)
        self.retry_queue = TTSRetryQueue(
            storage_path=storage_dir / "tts_retry_queue.json" if storage_dir else None
        )

        self._providers: Dict[str, Any] = {}

    def register_provider(self, name: str, provider: Any) -> None:
        """Register a provider for monitoring"""
        self._providers[name] = provider
        self.health_monitor.get_health(name)  # Initialize health data
        self.circuit_breaker.get_state(name)  # Initialize circuit state

    async def execute_with_resilience(
        self,
        provider_name: str,
        operation: Callable[[], Awaitable[Any]],
        fallback_providers: Optional[List[str]] = None
    ) -> Any:
        """
        Execute a TTS operation with full resilience support.

        - Checks circuit breaker before calling
        - Records success/failure metrics
        - Falls back to other providers if needed
        - Tracks latency

        Args:
            provider_name: Primary provider to use
            operation: Async operation to execute
            fallback_providers: List of fallback provider names

        Returns:
            Result of the operation

        Raises:
            Exception if all providers fail
        """
        providers_to_try = [provider_name] + (fallback_providers or [])
        last_error = None

        for provider in providers_to_try:
            # Check circuit breaker
            if not self.circuit_breaker.is_allowed(provider):
                logger.debug(f"Circuit open for {provider}, skipping")
                continue

            start_time = time.time()

            try:
                result = await operation()
                latency_ms = (time.time() - start_time) * 1000

                # Record success
                self.circuit_breaker.record_success(provider)
                self.health_monitor.record_success(provider, latency_ms)

                return result

            except Exception as e:
                last_error = e
                latency_ms = (time.time() - start_time) * 1000

                # Record failure
                self.circuit_breaker.record_failure(provider)
                self.health_monitor.record_failure(provider, str(e))

                logger.warning(f"TTS provider {provider} failed: {e}")

        # All providers failed
        if last_error:
            raise last_error
        raise RuntimeError("No TTS providers available")

    def is_provider_healthy(self, provider: str) -> bool:
        """Check if a provider is healthy"""
        return self.health_monitor.get_health(provider).is_healthy

    def get_healthy_providers(self) -> List[str]:
        """Get list of healthy providers"""
        return [
            name for name, health in self.health_monitor._health_data.items()
            if health.is_healthy
        ]

    async def start(
        self,
        check_func: Callable[[str], Awaitable[bool]],
        retry_func: Callable[[RetryableRequest], Awaitable[bool]]
    ) -> None:
        """Start all resilience features"""
        await self.health_monitor.start_monitoring(check_func)
        await self.retry_queue.start_processing(retry_func)

    async def stop(self) -> None:
        """Stop all resilience features"""
        await self.health_monitor.stop_monitoring()
        await self.retry_queue.stop_processing()

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all resilience features"""
        return {
            "health": self.health_monitor.get_all_health(),
            "circuit_breaker": {
                provider: self.circuit_breaker.get_state(provider).value
                for provider in self._providers.keys()
            },
            "retry_queue": self.retry_queue.get_queue_status(),
        }


# Singleton instance
_resilience_manager: Optional[TTSResilienceManager] = None


def get_resilience_manager(
    alert_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
    storage_dir: Optional[Path] = None
) -> TTSResilienceManager:
    """Get or create the resilience manager singleton"""
    global _resilience_manager
    if _resilience_manager is None:
        _resilience_manager = TTSResilienceManager(
            alert_callback=alert_callback,
            storage_dir=storage_dir
        )
    return _resilience_manager
