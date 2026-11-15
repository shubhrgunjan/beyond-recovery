"""Task state and physically timed forces, independent of the simulation backend."""

from dataclasses import dataclass
import math

import numpy as np


def wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


@dataclass
class Route:
    config: dict
    phase: int = 0
    dwell_elapsed: float = 0.0
    complete: bool = False

    def command(self, xy, yaw, time, dt):
        if self.complete or time < self.config.get("settle", 2.0):
            return np.zeros(3)
        target = np.asarray(self.config["waypoints"][self.phase])
        delta = target - np.asarray(xy)
        distance = np.linalg.norm(delta)
        if distance <= self.config.get("arrival_radius", 0.25):
            self.dwell_elapsed += dt
            if self.dwell_elapsed >= self.config.get("dwell", 2.0):
                self.phase += 1
                self.dwell_elapsed = 0.0
                self.complete = self.phase == len(self.config["waypoints"])
                return np.zeros(3)
            if self.complete or self.config.get("arrival_mode","legacy")=="legacy" or distance<=self.config.get("arrival_radius",.25)*.4:
                return np.zeros(3)
        else:
            self.dwell_elapsed = 0.0
        error = wrap(math.atan2(delta[1], delta[0]) - yaw)
        # Turn in place before advancing; no teleportation between subgoals.
        approach_distance=max(distance,.20) if self.config.get("arrival_mode")=="centered" else distance
        speed = min(self.config["speed"], approach_distance) * max(0.0, math.cos(error))
        if abs(error) > 0.6:
            speed = 0.0
        return np.array([speed, 0.0, np.clip(1.3 * error, -0.5, 0.5)])


def average_force(events, time, dt):
    """Average force over [time,time+dt), preserving pulse impulse at boundaries."""
    force = np.zeros(3)
    for event in events:
        overlap = max(0.0, min(time + dt, event["time"] + event["duration"])
                      - max(time, event["time"]))
        force += np.asarray(event["force"]) * overlap / dt
    return force


def wall_clearance(xy, walls):
    """Signed point-to-wall distance; a geometric proxy, not recoverability."""
    if not walls:
        return None
    distances = []
    for wall in walls:
        delta = np.abs(np.asarray(xy) - wall["center"][:2]) - wall["half_size"][:2]
        distances.append(np.linalg.norm(np.maximum(delta, 0)) + min(max(delta), 0))
    return float(min(distances))
