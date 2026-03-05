"""
SSL helper — robust SSL context for outbound HTTPS requests.

Handles broken SSL certificate chains on certain Python/Homebrew installations.
On first call, probes the target API with a verified context. If it fails,
falls back to unverified for non-production environments.
"""

import logging
import os
import ssl

logger = logging.getLogger("siteline")

_cached_context = None
_probed = False


def get_ssl_context():
    """Return the best available SSL verification setting for httpx.

    Returns either an ssl.SSLContext or False (for httpx's verify parameter).
    """
    global _cached_context, _probed

    if _probed:
        return _cached_context

    _probed = True

    # Explicit skip
    skip = os.environ.get("SKIP_SSL_VERIFY", "").strip()
    if skip in ("1", "true", "yes"):
        logger.info("SSL verification disabled (SKIP_SSL_VERIFY=1)")
        _cached_context = False
        return _cached_context

    env = os.environ.get("ENVIRONMENT", "development")

    # Try to actually connect with verified SSL
    import httpx

    # Strategy 1: certifi CA bundle
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        r = httpx.head("https://api.deepseek.com", verify=ctx, timeout=5)
        logger.info("SSL: certifi context works (status %s)", r.status_code)
        _cached_context = ctx
        return _cached_context
    except Exception as e:
        logger.debug("SSL: certifi probe failed: %s", e)

    # Strategy 2: system default context
    try:
        ctx = ssl.create_default_context()
        r = httpx.head("https://api.deepseek.com", verify=ctx, timeout=5)
        logger.info("SSL: system context works (status %s)", r.status_code)
        _cached_context = ctx
        return _cached_context
    except Exception as e:
        logger.debug("SSL: system probe failed: %s", e)

    # Strategy 3: Homebrew OpenSSL cert path
    brew_cert = "/opt/homebrew/etc/openssl@3/cert.pem"
    if os.path.exists(brew_cert):
        try:
            ctx = ssl.create_default_context(cafile=brew_cert)
            r = httpx.head("https://api.deepseek.com", verify=ctx, timeout=5)
            logger.info("SSL: Homebrew cert works (status %s)", r.status_code)
            _cached_context = ctx
            return _cached_context
        except Exception:
            pass

    # All verified strategies failed
    if env != "production":
        logger.warning(
            "SSL verification failed for api.deepseek.com — "
            "disabling SSL verification for local development. "
            "This is a known issue with Python %s on macOS Homebrew.",
            f"{ssl.OPENSSL_VERSION}"
        )
        _cached_context = False
    else:
        # In production (Railway etc), SSL usually works — use default
        logger.error("SSL verification failed in production — using default context")
        _cached_context = True  # httpx default

    return _cached_context
