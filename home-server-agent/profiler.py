"""
Performance Profiler
Track execution times and identify bottlenecks.
"""
import time
import functools
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class ProfileEntry:
    """Single profiling entry."""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    metadata: Dict = field(default_factory=dict)
    
    def complete(self, end_time: float = None):
        """Mark entry as complete."""
        self.end_time = end_time or time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000


class PerformanceProfiler:
    """
    Simple performance profiler for tracking execution times.
    
    Usage:
        profiler = PerformanceProfiler()
        
        with profiler.track("database_query"):
            result = db.query()
        
        # Or as decorator
        @profiler.profile
        def my_function():
            pass
        
        # Get report
        print(profiler.report())
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._entries: List[ProfileEntry] = []
        self._current_stack: List[ProfileEntry] = []
    
    @contextmanager
    def track(self, name: str, **metadata):
        """Context manager to track execution time."""
        if not self.enabled:
            yield
            return
        
        entry = ProfileEntry(
            name=name,
            start_time=time.time(),
            metadata=metadata
        )
        self._entries.append(entry)
        self._current_stack.append(entry)
        
        try:
            yield
        finally:
            entry.complete()
            self._current_stack.pop()
    
    def profile(self, func: Callable) -> Callable:
        """Decorator to profile a function."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self.track(func.__name__):
                return func(*args, **kwargs)
        return wrapper
    
    def get_stats(self) -> Dict[str, Dict]:
        """Get statistics by name."""
        stats: Dict[str, List[float]] = {}
        
        for entry in self._entries:
            if entry.duration_ms is not None:
                if entry.name not in stats:
                    stats[entry.name] = []
                stats[entry.name].append(entry.duration_ms)
        
        summary = {}
        for name, times in stats.items():
            summary[name] = {
                "count": len(times),
                "total_ms": sum(times),
                "mean_ms": sum(times) / len(times),
                "min_ms": min(times),
                "max_ms": max(times),
            }
        
        return summary
    
    def report(self, top_n: int = 10) -> str:
        """Generate formatted report."""
        if not self.enabled:
            return "Profiling disabled"
        
        stats = self.get_stats()
        
        if not stats:
            return "No profiling data collected"
        
        # Sort by total time
        sorted_stats = sorted(
            stats.items(),
            key=lambda x: x[1]["total_ms"],
            reverse=True
        )[:top_n]
        
        lines = [
            "\n📊 Performance Report",
            "=" * 70,
            f"{'Operation':<30} {'Count':<8} {'Total':<10} {'Mean':<10} {'Max':<10}",
            "-" * 70
        ]
        
        for name, data in sorted_stats:
            lines.append(
                f"{name:<30} {data['count']:<8} "
                f"{data['total_ms']:>8.1f}ms "
                f"{data['mean_ms']:>8.1f}ms "
                f"{data['max_ms']:>8.1f}ms"
            )
        
        lines.append("=" * 70)
        return "\n".join(lines)
    
    def reset(self):
        """Clear all profiling data."""
        self._entries.clear()
        self._current_stack.clear()


# Global profiler instance
_profiler = PerformanceProfiler(enabled=False)


def enable_profiling(enabled: bool = True):
    """Enable or disable global profiling."""
    _profiler.enabled = enabled
    logger.info(f"Profiling {'enabled' if enabled else 'disabled'}")


def track(name: str, **metadata):
    """Track execution time using global profiler."""
    return _profiler.track(name, **metadata)


def profile(func: Callable) -> Callable:
    """Profile function using global profiler."""
    return _profiler.profile(func)


def get_report(top_n: int = 10) -> str:
    """Get global profiler report."""
    return _profiler.report(top_n)


def get_stats() -> Dict:
    """Get global profiler stats."""
    return _profiler.get_stats()


# Example usage
if __name__ == "__main__":
    enable_profiling(True)
    
    @profile
    def slow_function():
        time.sleep(0.1)
    
    @profile
    def fast_function():
        time.sleep(0.01)
    
    for i in range(5):
        with track("loop_iteration", index=i):
            slow_function()
            fast_function()
    
    print(get_report())
