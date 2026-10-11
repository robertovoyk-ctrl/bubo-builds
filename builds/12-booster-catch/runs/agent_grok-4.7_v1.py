import math

mem = {}

def pilot(tel):
    if tel["tower_health"] == "FAULT":
        return {"engines": 0, "throttle": 0.0, "tilt": 0.0, "fins": 0.0, "abort": True}
    return {"engines": 0, "throttle": 0.0, "tilt": 0.0, "fins": 0.0, "abort": False}
