import os
from django.conf import settings
from django.core.cache import cache

MAX_LOGIN_ATTEMPTS = int(os.environ.get('LOGIN_RATELIMIT_MAX_ATTEMPTS', getattr(settings, 'LOGIN_RATELIMIT_MAX_ATTEMPTS', 5)))
LOCKOUT_DURATION = int(os.environ.get('LOGIN_RATELIMIT_TIMEOUT_SECONDS', getattr(settings, 'LOGIN_RATELIMIT_TIMEOUT_SECONDS', 300)))
IP_MAX_ATTEMPTS = MAX_LOGIN_ATTEMPTS * 2


def get_client_ip(request):
    """Safely extracts client IP address from request."""
    if not request:
        return '127.0.0.1'
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def get_throttle_key(request, identifier=''):
    """Legacy compatibility helper."""
    ip = get_client_ip(request)
    clean_id = (identifier or '').strip().lower()
    return f"login_throttle:{ip}:{clean_id}"


def get_user_throttle_key(identifier):
    clean_id = (identifier or '').strip().lower()
    return f"login_throttle_user:{clean_id}"


def get_ip_throttle_key(ip):
    return f"login_throttle_ip:{ip}"


def is_rate_limited(request, identifier=''):
    """
    Returns True if the IP, specific username, or IP+username pair has exceeded
    maximum failed login attempts.
    """
    ip = get_client_ip(request)
    clean_id = (identifier or '').strip().lower()

    # 1. Check IP + username combo
    combo_attempts = cache.get(get_throttle_key(request, clean_id), 0)
    if combo_attempts >= MAX_LOGIN_ATTEMPTS:
        return True

    # 2. Check username globally across IPs (protect targeted citizen accounts)
    if clean_id:
        user_attempts = cache.get(get_user_throttle_key(clean_id), 0)
        if user_attempts >= MAX_LOGIN_ATTEMPTS:
            return True

    # 3. Check IP globally (protect against distributed username spraying)
    ip_attempts = cache.get(get_ip_throttle_key(ip), 0)
    if ip_attempts >= IP_MAX_ATTEMPTS:
        return True

    return False


def record_failed_attempt(request, identifier=''):
    """
    Increments failed login attempt counters for the IP, username, and combo pair.
    """
    ip = get_client_ip(request)
    clean_id = (identifier or '').strip().lower()

    # Increment combo attempts
    combo_key = get_throttle_key(request, clean_id)
    attempts = cache.get(combo_key, 0) + 1
    cache.set(combo_key, attempts, timeout=LOCKOUT_DURATION)

    # Increment username attempts
    if clean_id:
        user_key = get_user_throttle_key(clean_id)
        user_attempts = cache.get(user_key, 0) + 1
        cache.set(user_key, user_attempts, timeout=LOCKOUT_DURATION)

    # Increment IP attempts
    ip_key = get_ip_throttle_key(ip)
    ip_attempts = cache.get(ip_key, 0) + 1
    cache.set(ip_key, ip_attempts, timeout=LOCKOUT_DURATION)

    return attempts


def reset_attempts(request, identifier=''):
    """
    Clears failed login attempt counters upon successful authentication.
    """
    ip = get_client_ip(request)
    clean_id = (identifier or '').strip().lower()
    cache.delete(get_throttle_key(request, clean_id))
    if clean_id:
        cache.delete(get_user_throttle_key(clean_id))
