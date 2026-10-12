from django.core.cache import cache

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5 minutes

def get_client_ip(request):
    """Safely extracts client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')

def get_throttle_key(request, identifier=''):
    ip = get_client_ip(request)
    return f"login_throttle:{ip}:{identifier.strip().lower()}"

def is_rate_limited(request, identifier=''):
    """Returns True if the IP or username has exceeded maximum failed login attempts."""
    key = get_throttle_key(request, identifier)
    attempts = cache.get(key, 0)
    return attempts >= MAX_LOGIN_ATTEMPTS

def record_failed_attempt(request, identifier=''):
    """Increments the failed login attempt counter."""
    key = get_throttle_key(request, identifier)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, timeout=LOCKOUT_DURATION)
    return attempts

def reset_attempts(request, identifier=''):
    """Clears failed login attempt counter upon successful authentication."""
    key = get_throttle_key(request, identifier)
    cache.delete(key)
