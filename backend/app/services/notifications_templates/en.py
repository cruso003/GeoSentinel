"""English templates (baseline). Keys here must also exist in other
languages, or `render()` will fall back to English."""

TEMPLATES = {
    "fallback": "GeoSentinel {severity} at {site}: {message}",
    "water_quality_critical":
        "GeoSentinel CRITICAL: water quality exceedance at {site}. "
        "Do not drink from or bathe in the stream until cleared.",
    "air_quality_critical":
        "GeoSentinel CRITICAL: air quality at {site} unsafe. "
        "Stay indoors, close windows if possible.",
    "slope_evacuation":
        "GeoSentinel EVACUATION: unstable slope at {site}. "
        "Leave the area immediately and move to the assembly point.",
    "seismic_critical":
        "GeoSentinel CRITICAL: seismic event felt at {site}. "
        "Stay clear of walls and cliff edges.",
    "test":
        "GeoSentinel test alert for {site}. You have successfully subscribed "
        "to community notifications.",
}
