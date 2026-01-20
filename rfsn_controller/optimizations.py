"""Advanced optimizations for the RFSN controller.

This module provides:
1. Lazy loading of heavy dependencies
2. Subprocess connection pooling
3. Response compression for caching
4. Early termination heuristics
5. Retry with exponential backoff
"""

from __future__ import annotations

import gzip
import hashlib
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

# ============================================================================
# LAZY LOADING
# ============================================================================

class LazyModule:
    """Lazy-loading wrapper for heavy modules.
    
    Only imports the module when first accessed, saving startup time.
    """
    
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None
        self._lock = threading.Lock()
    
    def _load(self):
        if self._module is None:
            with self._lock:
                if self._module is None:
                    import importlib
                    self._module = importlib.import_module(self._module_name)
        return self._module
    
    def __getattr__(self, name: str):
        return getattr(self._load(), name)


# Pre-configured lazy modules for heavy dependencies
lazy_numpy = LazyModule("numpy")
lazy_pandas = LazyModule("pandas") 
lazy_torch = LazyModule("torch")
lazy_transformers = LazyModule("transformers")


def lazy_import(module_name: str) -> LazyModule:
    """Create a lazy-loading module wrapper.
    
    Args:
        module_name: Name of the module to lazily import.
        
    Returns:
        LazyModule wrapper.
    """
    return LazyModule(module_name)


# ============================================================================
# SUBPROCESS POOL
# ============================================================================

@dataclass
class SubprocessWorker:
    """A reusable subprocess worker."""
    
    process: subprocess.Popen
    last_used: float = 0.0
    in_use: bool = False


@dataclass
class SubprocessPool:
    """Pool of reusable subprocess connections for faster command execution.
    
    Instead of spawning a new process for each command, reuse shell processes.
    """
    
    max_workers: int = 4
    max_idle_time: float = 60.0  # seconds
    
    _workers: List[SubprocessWorker] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _initialized: bool = False
    
    def __post_init__(self):
        self._workers = []
        self._lock = threading.Lock()
    
    def _create_worker(self) -> SubprocessWorker:
        """Create a new subprocess worker."""
        # Create a persistent bash process
        process = subprocess.Popen(
            ["/bin/bash", "-i"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,
        )
        return SubprocessWorker(process=process, last_used=time.time())
    
    def acquire(self) -> Optional[SubprocessWorker]:
        """Acquire a subprocess worker from the pool."""
        with self._lock:
            # Find an available worker
            for worker in self._workers:
                if not worker.in_use and worker.process.poll() is None:
                    worker.in_use = True
                    worker.last_used = time.time()
                    return worker
            
            # Create new worker if under limit
            if len(self._workers) < self.max_workers:
                worker = self._create_worker()
                worker.in_use = True
                self._workers.append(worker)
                return worker
            
            return None
    
    def release(self, worker: SubprocessWorker) -> None:
        """Release a worker back to the pool."""
        with self._lock:
            worker.in_use = False
            worker.last_used = time.time()
    
    def cleanup(self) -> None:
        """Remove idle workers that have timed out."""
        now = time.time()
        with self._lock:
            active = []
            for worker in self._workers:
                if not worker.in_use and (now - worker.last_used) > self.max_idle_time:
                    # Kill idle worker
                    try:
                        worker.process.terminate()
                        worker.process.wait(timeout=5)
                    except Exception:
                        try:
                            worker.process.kill()
                        except Exception:
                            pass
                else:
                    active.append(worker)
            self._workers = active
    
    def shutdown(self) -> None:
        """Shutdown all workers."""
        with self._lock:
            for worker in self._workers:
                try:
                    worker.process.terminate()
                    worker.process.wait(timeout=5)
                except Exception:
                    try:
                        worker.process.kill()
                    except Exception:
                        pass
            self._workers = []


# Global subprocess pool
_subprocess_pool: Optional[SubprocessPool] = None


def get_subprocess_pool() -> SubprocessPool:
    """Get the global subprocess pool."""
    global _subprocess_pool
    if _subprocess_pool is None:
        _subprocess_pool = SubprocessPool()
    return _subprocess_pool


# ============================================================================
# RESPONSE COMPRESSION
# ============================================================================

def compress_response(content: str) -> bytes:
    """Compress a response string for storage.
    
    Args:
        content: The string to compress.
        
    Returns:
        Compressed bytes.
    """
    return gzip.compress(content.encode("utf-8"))


def decompress_response(data: bytes) -> str:
    """Decompress a stored response.
    
    Args:
        data: Compressed bytes.
        
    Returns:
        Decompressed string.
    """
    return gzip.decompress(data).decode("utf-8")


def compress_if_large(content: str, threshold: int = 1000) -> Tuple[bool, bytes]:
    """Compress content only if it's large enough to benefit.
    
    Args:
        content: The string to potentially compress.
        threshold: Minimum size in bytes to trigger compression.
        
    Returns:
        (is_compressed, data) tuple.
    """
    content_bytes = content.encode("utf-8")
    if len(content_bytes) >= threshold:
        compressed = gzip.compress(content_bytes)
        # Only use compression if it actually saves space
        if len(compressed) < len(content_bytes) * 0.9:
            return True, compressed
    return False, content_bytes


def decompress_if_needed(is_compressed: bool, data: bytes) -> str:
    """Decompress data if it was compressed.
    
    Args:
        is_compressed: Whether the data is compressed.
        data: The data bytes.
        
    Returns:
        Decoded string.
    """
    if is_compressed:
        return gzip.decompress(data).decode("utf-8")
    return data.decode("utf-8")


# ============================================================================
# EARLY TERMINATION HEURISTICS
# ============================================================================

@dataclass
class TerminationHeuristics:
    """Heuristics for early termination to save compute time."""
    
    # Minimum steps before considering early termination
    min_steps: int = 3
    
    # Maximum consecutive failures before terminating
    max_consecutive_failures: int = 5
    
    # Maximum similar patches (by hash) before terminating
    max_similar_patches: int = 3
    
    # Success rate threshold (if below this after min_steps, terminate)
    min_success_rate: float = 0.05
    
    # Internal state
    _patch_hashes: deque = field(default_factory=lambda: deque(maxlen=20))
    _consecutive_failures: int = 0
    _total_attempts: int = 0
    _successful_attempts: int = 0
    
    def __post_init__(self):
        self._patch_hashes = deque(maxlen=20)
        self._consecutive_failures = 0
        self._total_attempts = 0
        self._successful_attempts = 0
    
    def record_attempt(self, diff: str, success: bool) -> None:
        """Record a patch attempt.
        
        Args:
            diff: The patch diff.
            success: Whether the patch succeeded.
        """
        self._total_attempts += 1
        
        if success:
            self._successful_attempts += 1
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
        
        # Track patch hash
        patch_hash = hashlib.sha256(diff.encode()).hexdigest()[:16]
        self._patch_hashes.append(patch_hash)
    
    def should_terminate(self) -> Tuple[bool, str]:
        """Check if we should terminate early.
        
        Returns:
            (should_terminate, reason) tuple.
        """
        # Check consecutive failures
        if self._consecutive_failures >= self.max_consecutive_failures:
            return True, f"Too many consecutive failures ({self._consecutive_failures})"
        
        # Check similar patches
        if len(self._patch_hashes) >= self.max_similar_patches:
            recent = list(self._patch_hashes)[-self.max_similar_patches:]
            if len(set(recent)) == 1:
                return True, "Repeated identical patches"
        
        # Check success rate after minimum steps
        if self._total_attempts >= self.min_steps:
            rate = self._successful_attempts / self._total_attempts
            if rate < self.min_success_rate:
                return True, f"Success rate too low ({rate:.1%})"
        
        return False, ""
    
    def reset(self) -> None:
        """Reset heuristics state."""
        self._patch_hashes.clear()
        self._consecutive_failures = 0
        self._total_attempts = 0
        self._successful_attempts = 0


# ============================================================================
# RETRY WITH BACKOFF
# ============================================================================

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries.
        max_delay: Maximum delay between retries.
        exponential_base: Base for exponential backoff.
        retryable_exceptions: Tuple of exceptions to retry on.
        
    Returns:
        Decorator function.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay,
                        )
                        time.sleep(delay)
                    else:
                        raise
            
            raise last_exception  # Should never reach here
        
        return wrapper
    return decorator


# ============================================================================
# MEMOIZATION WITH TTL
# ============================================================================

def memoize_with_ttl(ttl_seconds: float = 300.0, maxsize: int = 128):
    """Decorator for memoization with time-to-live.
    
    Args:
        ttl_seconds: Time-to-live for cached values.
        maxsize: Maximum cache size.
        
    Returns:
        Decorator function.
    """
    def decorator(func):
        cache: Dict[str, Tuple[float, Any]] = {}
        lock = threading.Lock()
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from arguments
            key = str((args, tuple(sorted(kwargs.items()))))
            
            now = time.time()
            
            with lock:
                # Check cache
                if key in cache:
                    timestamp, value = cache[key]
                    if now - timestamp < ttl_seconds:
                        return value
                    else:
                        del cache[key]
                
                # Compute value
                value = func(*args, **kwargs)
                
                # Store in cache
                if len(cache) >= maxsize:
                    # Remove oldest entry
                    oldest_key = min(cache, key=lambda k: cache[k][0])
                    del cache[oldest_key]
                
                cache[key] = (now, value)
                return value
        
        def clear_cache():
            with lock:
                cache.clear()
        
        wrapper.clear_cache = clear_cache
        return wrapper
    
    return decorator


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def batch_process(
    items: List[Any],
    processor: Callable[[Any], Any],
    batch_size: int = 10,
    max_workers: int = 4,
) -> List[Any]:
    """Process items in batches with parallel execution.
    
    Args:
        items: Items to process.
        processor: Function to apply to each item.
        batch_size: Number of items per batch.
        max_workers: Maximum parallel workers.
        
    Returns:
        List of processed results in same order.
    """
    from concurrent.futures import ThreadPoolExecutor
    
    results = [None] * len(items)
    
    def process_item(idx_item):
        idx, item = idx_item
        return idx, processor(item)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for idx, result in executor.map(process_item, enumerate(items)):
            results[idx] = result
    
    return results


# ============================================================================
# RESOURCE LIMITS
# ============================================================================

@dataclass
class ResourceLimits:
    """Resource limits for operations."""
    
    max_memory_mb: int = 4096
    max_cpu_seconds: float = 300.0
    max_file_size_mb: int = 100
    max_output_size_mb: int = 10
    
    def check_memory(self) -> bool:
        """Check if memory usage is within limits."""
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            memory_mb = usage.ru_maxrss / 1024  # Convert to MB
            return memory_mb < self.max_memory_mb
        except Exception:
            return True
    
    def limit_output(self, output: str) -> str:
        """Limit output size to prevent memory issues."""
        max_chars = self.max_output_size_mb * 1024 * 1024
        if len(output) > max_chars:
            return output[:max_chars] + f"\n... [truncated {len(output) - max_chars} chars]"
        return output


# ============================================================================
# INITIALIZATION
# ============================================================================

def init_optimizations() -> None:
    """Initialize all optimization systems."""
    # Start subprocess pool cleanup thread
    def cleanup_loop():
        while True:
            time.sleep(30)
            try:
                pool = get_subprocess_pool()
                pool.cleanup()
            except Exception:
                pass
    
    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()


def shutdown_optimizations() -> None:
    """Shutdown all optimization systems."""
    global _subprocess_pool
    if _subprocess_pool:
        _subprocess_pool.shutdown()
        _subprocess_pool = None
