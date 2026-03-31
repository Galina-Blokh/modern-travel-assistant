import functools
import time
from typing import Callable

BOOKING_KEYWORDS = ["hotel", "flight", "airline", "resort", "airbnb", "hostel", "book", "reservation", "price"]
DISCLAIMER = "\n\n> ⚠️ Please verify bookings independently — specific availability and prices may vary."


def with_retry(max_retries: int = 2, delay: float = 1.0):
    """Decorator to retry a tool function on exception."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        time.sleep(delay)
            return f"Service temporarily unavailable. Please try again. ({last_error})"
        return wrapper
    return decorator


def add_hallucination_disclaimer(response: str) -> str:
    """Append a disclaimer if the response references bookable services."""
    if any(word in response.lower() for word in BOOKING_KEYWORDS):
        if DISCLAIMER.strip() not in response:
            return response + DISCLAIMER
    return response
