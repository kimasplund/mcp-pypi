"""
HTTP client for the MCP-PyPI client.
"""

import json
import logging
import asyncio
import random
from typing import Dict, Any, Optional

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from mcp_pypi.core.models import PyPIClientConfig, ErrorCode, format_error
from mcp_pypi.core.cache import AsyncCacheManager

logger = logging.getLogger("mcp-pypi.http")

class AsyncHTTPClient:
    """Async HTTP client for making requests to PyPI."""
    
    def __init__(
        self, 
        config: PyPIClientConfig, 
        cache_manager: AsyncCacheManager
    ):
        self.config = config
        self.cache_manager = cache_manager
        self.rate_limit_delay = 0.1  # Initial delay between requests
        self.last_request_time = 0.0
        self._session: Optional[ClientSession] = None
    
    async def _get_session(self) -> ClientSession:
        """Get or create an aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=self.config.timeout)
            self._session = ClientSession(timeout=timeout)
        return self._session
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def _apply_rate_limit(self) -> None:
        """Apply rate limiting to avoid overwhelming the server."""
        import time
        
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.rate_limit_delay:
            delay = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping for {delay:.2f}s")
            await asyncio.sleep(delay)
        
        self.last_request_time = time.time()
    
    async def fetch(self, url: str, method: str = "GET") -> Dict[str, Any]:
        """Fetch data from URL with caching, rate limiting, and retries.
        
        Args:
            url: The URL to fetch
            method: The HTTP method to use (default: GET)
        
        Returns:
            The parsed response as a dictionary
        """
        # Check cache first
        cached_data = await self.cache_manager.get(url)
        if cached_data:
            logger.debug(f"Cache hit for {url}")
            return cached_data
        
        # Get ETag if available for conditional requests
        etag = await self.cache_manager.get_etag(url)
        
        # Prepare headers
        headers = {"User-Agent": self.config.user_agent}
        if etag:
            headers["If-None-Match"] = etag
        
        session = await self._get_session()
        retries_left = self.config.max_retries
        retry_delay = self.config.retry_delay
        last_error = None
        
        while retries_left > 0:
            try:
                # Apply rate limiting
                await self._apply_rate_limit()
                
                async with session.request(method, url, headers=headers) as response:
                    # Handle HTTP status codes
                    if response.status == 304 and cached_data:  # Not Modified
                        logger.debug(f"Not modified (304) for {url}, using cache")
                        return cached_data
                    
                    if response.status == 429:  # Too Many Requests
                        retry_after = response.headers.get('Retry-After')
                        if retry_after and retry_after.isdigit():
                            self.rate_limit_delay = float(retry_after)
                        else:
                            # Exponential backoff with jitter
                            self.rate_limit_delay = min(60, self.rate_limit_delay * 2) + random.uniform(0, 1)
                        
                        logger.warning(f"Rate limited, retrying after {self.rate_limit_delay:.2f}s")
                        await asyncio.sleep(self.rate_limit_delay)
                        continue
                    
                    if response.status == 404:
                        return format_error(ErrorCode.NOT_FOUND, f"Resource not found: {url}")
                    
                    if response.status >= 400:
                        error_message = f"HTTP error {response.status}: {response.reason}"
                        
                        # Try to extract more details from response body
                        try:
                            error_body = await response.text()
                            if error_body:
                                error_message += f" - {error_body[:200]}"
                        except Exception:
                            pass
                        
                        # Decide if we should retry based on status code
                        if response.status >= 500:  # Server errors are retriable
                            retries_left -= 1
                            retry_delay = self._get_next_retry_delay(retry_delay)
                            logger.warning(f"Server error {response.status}, retrying in {retry_delay:.2f}s ({retries_left} retries left)")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:  # Client errors are not retriable
                            return format_error(ErrorCode.NETWORK_ERROR, error_message)
                    
                    # Extract content type and response data
                    content_type = response.headers.get('Content-Type', '')
                    new_etag = response.headers.get('ETag')
                    
                    if 'application/json' in content_type:
                        result = await response.json()
                    else:
                        # Return raw data for non-JSON responses
                        result = await response.read()
                        
                        # For XML responses, keep it as bytes for the XML parser
                        if not ('application/xml' in content_type or 'text/xml' in content_type):
                            # Convert bytes to UTF-8 string for text responses
                            try:
                                result = result.decode('utf-8')
                            except UnicodeDecodeError:
                                # If it can't be decoded as UTF-8, leave as bytes
                                pass
                    
                    # Cache successful JSON responses
                    if isinstance(result, dict):
                        await self.cache_manager.set(url, result, new_etag)
                    
                    return result
            
            except aiohttp.ClientConnectorError as e:
                last_error = str(e)
                logger.warning(f"Connection error for {url}: {e}")
            except aiohttp.ClientError as e:
                last_error = str(e)
                logger.warning(f"Client error for {url}: {e}")
            except asyncio.TimeoutError:
                last_error = "Request timed out"
                logger.warning(f"Timeout for {url}")
            except json.JSONDecodeError as e:
                return format_error(ErrorCode.PARSE_ERROR, f"Invalid JSON response from {url}: {e}")
            except Exception as e:
                last_error = str(e)
                logger.exception(f"Unexpected error for {url}: {e}")
            
            # Apply backoff before retrying
            retries_left -= 1
            if retries_left > 0:
                retry_delay = self._get_next_retry_delay(retry_delay)
                logger.warning(f"Retrying in {retry_delay:.2f}s ({retries_left} retries left)")
                await asyncio.sleep(retry_delay)
        
        # All retries failed
        return format_error(
            ErrorCode.NETWORK_ERROR, 
            f"Failed to fetch {url} after {self.config.max_retries} retries: {last_error}"
        )
    
    def _get_next_retry_delay(self, current_delay: float) -> float:
        """Calculate the next retry delay using exponential backoff with jitter."""
        # Apply full jitter: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
        return min(60, current_delay * 2) * random.uniform(0.5, 1.0)
