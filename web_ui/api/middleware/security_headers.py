"""
Security Headers Middleware for TermiVoxed Web API

Adds essential security headers to all responses to protect against
common web vulnerabilities like XSS, clickjacking, and MIME sniffing.

Reference: OWASP Secure Headers Project
https://owasp.org/www-project-secure-headers/
"""

import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all HTTP responses.

    Headers added:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking attacks
    - X-XSS-Protection: Legacy XSS filter (for older browsers)
    - Referrer-Policy: Controls referrer information sent
    - Permissions-Policy: Restricts browser features
    - Strict-Transport-Security: Forces HTTPS (production only)
    - Content-Security-Policy: XSS and injection protection
    """

    def __init__(self, app, enable_hsts: bool = None):
        """
        Initialize the security headers middleware.

        Args:
            app: The ASGI application
            enable_hsts: Whether to enable HSTS. Defaults to True in production.
        """
        super().__init__(app)

        # Auto-detect production environment
        env = os.getenv("TERMIVOXED_ENV", "development").lower()
        self.is_production = env in ("production", "prod")

        # HSTS should only be enabled in production with HTTPS
        if enable_hsts is None:
            self.enable_hsts = self.is_production
        else:
            self.enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Cross-Origin-Opener-Policy - Allow popups for Firebase Auth
        # Firebase Auth uses popup windows for Google/Microsoft sign-in
        # 'same-origin-allow-popups' allows the popup to communicate back
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"

        # Prevent MIME type sniffing - browsers should respect Content-Type
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking - page cannot be embedded in frames
        response.headers["X-Frame-Options"] = "DENY"

        # Legacy XSS protection for older browsers
        # Modern browsers use CSP, but this helps IE/older Edge
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        # 'strict-origin-when-cross-origin' is the recommended default
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features we don't use
        # This prevents malicious scripts from accessing sensitive APIs
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        # HSTS - Force HTTPS in production
        # max-age=31536000 = 1 year
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Content-Security-Policy
        # Restricts sources of content to prevent XSS and data injection
        # Note: This is a baseline policy - adjust based on your needs
        if self.is_production:
            # Stricter CSP for production
            csp_directives = [
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",  # unsafe-inline for Tailwind
                "img-src 'self' data: https:",
                "font-src 'self' data:",
                "connect-src 'self' https://firebaseauth.googleapis.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com",
                "frame-ancestors 'none'",
                "form-action 'self'",
                "base-uri 'self'",
                "object-src 'none'",
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        else:
            # More permissive CSP for development
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # For hot reload
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: https: blob:",
                "font-src 'self' data:",
                "connect-src 'self' ws: wss: https:",  # WebSocket for HMR
                "frame-ancestors 'self'",
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response
