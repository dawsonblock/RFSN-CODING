"""Async LLM client with streaming and caching support.

This module provides:
1. Async API calls for parallel LLM invocations
2. Streaming responses for early validation
3. Semantic caching for cost reduction
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

# Try to import httpx for async HTTP
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore


# ============================================================================
# CONFIGURATION
# ============================================================================

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

DEFAULT_TIMEOUT = 120.0  # 2 minutes


# ============================================================================
# ASYNC DEEPSEEK CLIENT
# ============================================================================

@dataclass
class AsyncLLMResponse:
    """Response from an async LLM call."""
    
    content: str
    model: str
    temperature: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Parse content as JSON dict."""
        try:
            return json.loads(self.content)
        except json.JSONDecodeError:
            return {"mode": "error", "error": "Invalid JSON", "raw": self.content}


async def call_deepseek_async(
    prompt: str,
    *,
    temperature: float = 0.0,
    model: str = "deepseek-chat",
    system_prompt: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> AsyncLLMResponse:
    """Call DeepSeek API asynchronously.
    
    Args:
        prompt: User prompt.
        temperature: Sampling temperature.
        model: Model name.
        system_prompt: Optional system prompt.
        timeout: Request timeout in seconds.
        
    Returns:
        AsyncLLMResponse with parsed content.
    """
    if not HTTPX_AVAILABLE:
        raise RuntimeError("httpx not installed. Run: pip install httpx")
    
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        # Return mock response
        return AsyncLLMResponse(
            content='{"mode": "tool_request", "requests": [], "why": "Mocked - no API key"}',
            model=model,
            temperature=temperature,
            cached=False,
        )
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        data = response.json()
    
    latency_ms = (time.time() - start_time) * 1000
    
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    
    return AsyncLLMResponse(
        content=content,
        model=model,
        temperature=temperature,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        latency_ms=latency_ms,
        cached=False,
    )


async def call_deepseek_streaming(
    prompt: str,
    *,
    temperature: float = 0.0,
    model: str = "deepseek-chat",
    system_prompt: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> AsyncIterator[str]:
    """Call DeepSeek API with streaming response.
    
    Yields:
        Chunks of the response as they arrive.
    """
    if not HTTPX_AVAILABLE:
        raise RuntimeError("httpx not installed. Run: pip install httpx")
    
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        yield '{"mode": "tool_request", "requests": [], "why": "Mocked - no API key"}'
        return
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=body,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


# ============================================================================
# PARALLEL LLM CALLS
# ============================================================================

async def call_parallel(
    prompts: List[Tuple[str, float]],  # List of (prompt, temperature)
    *,
    model: str = "deepseek-chat",
    system_prompt: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> List[AsyncLLMResponse]:
    """Call LLM with multiple prompts/temperatures in parallel.
    
    Args:
        prompts: List of (prompt, temperature) tuples.
        model: Model to use.
        system_prompt: Optional system prompt.
        timeout: Request timeout.
        
    Returns:
        List of responses in same order as input.
    """
    tasks = [
        call_deepseek_async(
            prompt,
            temperature=temp,
            model=model,
            system_prompt=system_prompt,
            timeout=timeout,
        )
        for prompt, temp in prompts
    ]
    
    return await asyncio.gather(*tasks, return_exceptions=True)


async def generate_patches_parallel(
    prompt: str,
    *,
    temperatures: Optional[List[float]] = None,
    model: str = "deepseek-chat",
    system_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate patches at multiple temperatures in parallel.
    
    Args:
        prompt: The patch generation prompt.
        temperatures: List of temperatures to try.
        model: Model to use.
        system_prompt: Optional system prompt.
        
    Returns:
        List of parsed patch responses.
    """
    if temperatures is None:
        temperatures = [0.0, 0.2, 0.4]
    
    prompts = [(prompt, temp) for temp in temperatures]
    responses = await call_parallel(
        prompts,
        model=model,
        system_prompt=system_prompt,
    )
    
    patches = []
    for resp in responses:
        if isinstance(resp, Exception):
            patches.append({"mode": "error", "error": str(resp)})
        else:
            patches.append(resp.to_dict())
    
    return patches


# ============================================================================
# SEMANTIC CACHE
# ============================================================================

@dataclass
class LLMCache:
    """SQLite-based cache for LLM responses.
    
    Uses prompt hashing for exact match caching.
    Future: Add embedding-based semantic similarity.
    """
    
    db_path: str
    max_age_hours: int = 24
    max_entries: int = 10000
    
    _conn: Optional[sqlite3.Connection] = field(default=None, repr=False)
    
    def __post_init__(self):
        self._ensure_db()
    
    def _ensure_db(self) -> None:
        """Create database and tables if needed."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                prompt_hash TEXT PRIMARY KEY,
                prompt TEXT,
                model TEXT,
                temperature REAL,
                response TEXT,
                created_at REAL,
                hit_count INTEGER DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created 
            ON cache(created_at)
        """)
        self._conn.commit()
    
    def _hash_prompt(self, prompt: str, model: str, temperature: float) -> str:
        """Create hash key for cache lookup."""
        key = f"{model}:{temperature:.2f}:{prompt}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]
    
    def get(
        self,
        prompt: str,
        model: str,
        temperature: float,
    ) -> Optional[AsyncLLMResponse]:
        """Look up cached response.
        
        Args:
            prompt: The prompt string.
            model: Model name.
            temperature: Temperature used.
            
        Returns:
            Cached response or None.
        """
        if not self._conn:
            return None
        
        prompt_hash = self._hash_prompt(prompt, model, temperature)
        
        cursor = self._conn.execute(
            """
            SELECT response, created_at FROM cache
            WHERE prompt_hash = ?
            """,
            (prompt_hash,),
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        response_json, created_at = row
        
        # Check age
        age_hours = (time.time() - created_at) / 3600
        if age_hours > self.max_age_hours:
            self._conn.execute(
                "DELETE FROM cache WHERE prompt_hash = ?",
                (prompt_hash,),
            )
            self._conn.commit()
            return None
        
        # Update hit count
        self._conn.execute(
            "UPDATE cache SET hit_count = hit_count + 1 WHERE prompt_hash = ?",
            (prompt_hash,),
        )
        self._conn.commit()
        
        return AsyncLLMResponse(
            content=response_json,
            model=model,
            temperature=temperature,
            cached=True,
        )
    
    def set(
        self,
        prompt: str,
        model: str,
        temperature: float,
        response: str,
    ) -> None:
        """Cache a response.
        
        Args:
            prompt: The prompt string.
            model: Model name.
            temperature: Temperature used.
            response: The response content to cache.
        """
        if not self._conn:
            return
        
        prompt_hash = self._hash_prompt(prompt, model, temperature)
        
        self._conn.execute(
            """
            INSERT OR REPLACE INTO cache 
            (prompt_hash, prompt, model, temperature, response, created_at, hit_count)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (prompt_hash, prompt[:1000], model, temperature, response, time.time()),
        )
        self._conn.commit()
        
        # Housekeeping
        self._cleanup()
    
    def _cleanup(self) -> None:
        """Remove old entries if over limit."""
        if not self._conn:
            return
        
        # Delete old entries
        cutoff = time.time() - (self.max_age_hours * 3600)
        self._conn.execute(
            "DELETE FROM cache WHERE created_at < ?",
            (cutoff,),
        )
        
        # Delete excess entries (keep most recent)
        cursor = self._conn.execute("SELECT COUNT(*) FROM cache")
        count = cursor.fetchone()[0]
        
        if count > self.max_entries:
            excess = count - self.max_entries
            self._conn.execute(
                """
                DELETE FROM cache WHERE prompt_hash IN (
                    SELECT prompt_hash FROM cache
                    ORDER BY created_at ASC
                    LIMIT ?
                )
                """,
                (excess,),
            )
        
        self._conn.commit()
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._conn:
            return {"error": "not connected"}
        
        cursor = self._conn.execute(
            """
            SELECT 
                COUNT(*) as entries,
                SUM(hit_count) as total_hits,
                AVG(hit_count) as avg_hits
            FROM cache
            """
        )
        row = cursor.fetchone()
        
        return {
            "entries": row[0],
            "total_hits": row[1] or 0,
            "avg_hits": row[2] or 0.0,
        }


# ============================================================================
# CACHED ASYNC CLIENT
# ============================================================================

_default_cache: Optional[LLMCache] = None


def get_cache(db_path: Optional[str] = None) -> LLMCache:
    """Get or create the default LLM cache.
    
    Args:
        db_path: Path to cache database. Uses default if None.
        
    Returns:
        LLMCache instance.
    """
    global _default_cache
    
    if _default_cache is None:
        cache_path = db_path or os.path.expanduser("~/.rfsn/llm_cache.db")
        _default_cache = LLMCache(db_path=cache_path)
    
    return _default_cache


async def call_deepseek_cached(
    prompt: str,
    *,
    temperature: float = 0.0,
    model: str = "deepseek-chat",
    system_prompt: Optional[str] = None,
    use_cache: bool = True,
    cache: Optional[LLMCache] = None,
) -> AsyncLLMResponse:
    """Call DeepSeek with caching support.
    
    Args:
        prompt: User prompt.
        temperature: Sampling temperature.
        model: Model name.
        system_prompt: Optional system prompt.
        use_cache: Whether to use caching.
        cache: Cache instance (uses default if None).
        
    Returns:
        AsyncLLMResponse (may be from cache).
    """
    if use_cache:
        cache = cache or get_cache()
        
        # Check cache
        cached = cache.get(prompt, model, temperature)
        if cached is not None:
            return cached
    
    # Make actual API call
    response = await call_deepseek_async(
        prompt,
        temperature=temperature,
        model=model,
        system_prompt=system_prompt,
    )
    
    # Cache the response
    if use_cache and cache and not response.cached:
        cache.set(prompt, model, temperature, response.content)
    
    return response


# ============================================================================
# SYNC WRAPPER FOR BACKWARD COMPATIBILITY
# ============================================================================

def call_model_async_sync(
    prompt: str,
    temperature: float = 0.0,
    model: str = "deepseek-chat",
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Sync wrapper for async LLM call.
    
    Use this as a drop-in replacement for the existing call_model function.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # Already in async context, create new loop in thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                call_deepseek_cached(
                    prompt,
                    temperature=temperature,
                    model=model,
                    use_cache=use_cache,
                ),
            )
            response = future.result()
    else:
        response = loop.run_until_complete(
            call_deepseek_cached(
                prompt,
                temperature=temperature,
                model=model,
                use_cache=use_cache,
            )
        )
    
    return response.to_dict()
