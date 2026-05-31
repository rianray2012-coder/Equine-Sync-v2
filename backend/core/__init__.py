"""EquineSync core package.

Cross-cutting infrastructure shared across the backend: environment
configuration/validation, security helpers, rate limiting, and one-time auth
tokens. These modules are intentionally free of route/HTTP concerns so they can
be imported by routers and services without circular dependencies.

Modules:
- ``core.config``         — env config + fail-fast validation, JWT secret, CORS, limits
- ``core.rate_limit``     — auth-endpoint rate-limit dependency
- ``core.auth_tokens``    — password-reset / email-verification tokens
- ``core.login_attempts`` — account-level brute-force lockout
"""
