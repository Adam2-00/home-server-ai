"""
Circuit Breaker Pattern for External API Calls
Prevents cascading failures when external services are down.
"""
import time
import threading
from enum import Enum
from typing import Callable, Optional, Any
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """
    Circuit breaker pattern for resilient external API calls.
    
    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        
        @breaker
        def call_external_api():
            return requests.get('https://api.example.com')
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        name: str = "default"
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        
        self._lock = threading.Lock()
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap function with circuit breaker."""
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: Original exception if call fails
        """
        with self._lock:
            state = self._state
            
            if state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"Circuit {self.name} entering HALF_OPEN state")
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit {self.name} is OPEN. "
                        f"Retry after {self._get_retry_after():.0f}s"
                    )
            
            elif state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpen(
                        f"Circuit {self.name} HALF_OPEN limit reached"
                    )
                self._half_open_calls += 1
        
        # Execute the call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.recovery_timeout
    
    def _get_retry_after(self) -> float:
        """Get seconds until retry is allowed."""
        if self._last_failure_time is None:
            return 0
        elapsed = time.time() - self._last_failure_time
        return max(0, self.recovery_timeout - elapsed)
    
    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    logger.info(f"Circuit {self.name} recovered, closing")
                    self._reset()
            else:
                self._failure_count = max(0, self._failure_count - 1)
    
    def _on_failure(self):
        """Handle failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit {self.name} failed in HALF_OPEN, opening")
                self._state = CircuitState.OPEN
            elif self._failure_count >= self._failure_threshold:
                logger.error(
                    f"Circuit {self.name} reached {self._failure_count} failures, "
                    f"opening for {self._recovery_timeout}s"
                )
                self._state = CircuitState.OPEN
    
    def _reset(self):
        """Reset circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state
    
    @property
    def metrics(self) -> dict:
        """Get circuit metrics."""
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure": self._last_failure_time,
                "retry_after": self._get_retry_after()
            }


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass


# Global circuit breakers for common services
OPENAI_BREAKER = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60.0,
    name="openai_api"
)

ANTHROPIC_BREAKER = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60.0,
    name="anthropic_api"
)

DOCKER_BREAKER = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    name="docker_daemon"
)


# Example usage
if __name__ == "__main__":
    # Test circuit breaker
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5.0, name="test")
    
    @breaker
    def flaky_function():
        import secrets
        # Use secrets for cryptographically secure randomness
        if secrets.randbelow(10) < 7:  # 70% failure rate
            raise Exception("Random failure")
        return "Success"
    
    for i in range(10):
        try:
            result = flaky_function()
            print(f"Call {i}: {result}")
        except CircuitBreakerOpen:
            print(f"Call {i}: Circuit breaker OPEN")
        except Exception as e:
            print(f"Call {i}: {e}")
        time.sleep(0.5)
        
    print(f"\nFinal metrics: {breaker.metrics}")
