"""Dan (Gio) templates — Nimba County.

Same contract as ``mano.py``. Translations approved by the community-liaison
team. Avoid specialised vocabulary — rural handsets may not render it.
"""

TEMPLATES = {
    "fallback": "GeoSentinel {severity} {site}: {message}",
    "water_quality_critical":
        "GeoSentinel: Yi {site} gba e ya gbo. Yi to mi ya ma eh na pe "
        "kpo.",
    "air_quality_critical":
        "GeoSentinel: Fee {site} gba e ya gbo. Pi yi to ya kpo mi.",
    "slope_evacuation":
        "GeoSentinel: Zee {site} e ka gbo-gbo! Yi kpo mi o to mi mee.",
    "seismic_critical":
        "GeoSentinel: Taa e gba {site}. Yi to mi ya gbanga wi.",
    "test":
        "GeoSentinel: Yee-test {site} mee. I sii kpo ma yi.",
    "community_confirm":
        "GeoSentinel: i nammba-kpo ma {site} e yia {code}. "
        "E ya gbo na 10 minit.",
}
