"""
Retry Utilities
Provides retry logic with exponential backoff for transient failures.
"""
import time
import random
import functools
from typing import Callable, Type, Tuple, Optional


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator that retries a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential calculation
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback called on each retry with (attempt, exception, delay)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt >= max_retries:
                        raise last_exception
                    
                    # Calculate delay with exponential backoff and jitter
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0, delay * 0.1)
                    sleep_time = delay + jitter
                    
                    if on_retry:
                        on_retry(attempt + 1, e, sleep_time)
                    
                    time.sleep(sleep_time)
            
            raise last_exception  # Should not reach here
        
        return wrapper
    return decorator


def retry_network_operation(max_retries: int = 3):
    """Specialized retry decorator for network operations."""
    return retry_with_backoff(
        max_retries=max_retries,
        base_delay=1.0,
        max_delay=30.0,
        exceptions=(ConnectionError, TimeoutError, OSError)
    )


def retry_subprocess(max_retries: int = 2):
    """Specialized retry decorator for subprocess calls."""
    import subprocess
    return retry_with_backoff(
        max_retries=max_retries,
        base_delay=0.5,
        max_delay=5.0,
        exceptions=(subprocess.SubprocessError, OSError)
    )


class RetryContext:
    """Context manager for retry logic with state tracking."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.exceptions = exceptions
        self.attempts = 0
        self.last_exception = None
    
    def __enter__(self):
        self.attempts = 0
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return True
        
        if not issubclass(exc_type, self.exceptions):
            return False
        
        self.last_exception = exc_val
        self.attempts += 1
        
        if self.attempts > self.max_retries:
            return False  # Re-raise the exception
        
        delay = self.base_delay * (2 ** (self.attempts - 1))
        time.sleep(delay)
        
        return True  # Suppress exception and retry


# Convenience function for inline retry logic
def retry_call(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    **kwargs
):
    """Call a function with retry logic."""
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except exceptions as e:
            if attempt >= max_retries:
                raise
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)


if __name__ == "__main__":
    # Test the retry decorator
    call_count = 0
    
    @retry_with_backoff(max_retries=3, base_delay=0.1, exceptions=(ValueError,))
    def flaky_function():
        global call_count
        call_count += 1
        if call_count < 3:
            raise ValueError(f"Attempt {call_count} failed")
        return f"Success on attempt {call_count}"
    
    result = flaky_function()
    print(f"Result: {result}")
    assert call_count == 3, f"Expected 3 calls, got {call_count}"
    print("Retry test passed!")
