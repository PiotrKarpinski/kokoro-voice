"""The mainspring. A timer, not a health bar."""
CAPACITY = 100.0
BASE_DRAIN = 8.3         # points per second while standing
WARNING_AT = 25.0

def tick(level, income, dt):
    return min(CAPACITY, level + (income - BASE_DRAIN) * dt)
