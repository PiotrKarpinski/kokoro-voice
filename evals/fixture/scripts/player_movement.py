"""Player movement. Speed, jumping, wall contact."""
SPRINT_SPEED = 20.0      # metres per second
JUMP_HEIGHT = 2.7        # metres
WALL_STICK_MIN_SPEED = 6.0

def charge_from_velocity(speed_along_surface):
    # Spring charge comes from real velocity, never from a state flag.
    return max(0.0, speed_along_surface - 4.0) * 0.5
