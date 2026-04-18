"""Mano (Mann / Mah) templates — Nimba County.

Translations prepared by the Tokadeh community-liaison team. Keep strings
short; Mano-language rural handsets frequently lack diacritic fonts, so we
use plain ASCII + tone-mark apostrophes only where unambiguous. Update via
PR with the translator's sign-off in the commit trailer.
"""

TEMPLATES = {
    "fallback": "GeoSentinel {severity} {site}: {message}",
    "water_quality_critical":
        "GeoSentinel: Yia e gbo yi e mee {site} gbo. Yia mi eh na yia "
        "wo na kpo.",
    "air_quality_critical":
        "GeoSentinel: Fene e mee {site} e na zono. Sii pie wo e na gbo.",
    "slope_evacuation":
        "GeoSentinel: Zu e mi kpo {site} e yia gbanga! Yi to dee o wi "
        "gbanga mi, wo na pie kpo.",
    "seismic_critical":
        "GeoSentinel: Ta e gboba {site}. Yi kpo mi kaanga pie to lo mi.",
    "test":
        "GeoSentinel: Yei test ma {site}. Eh kpo zono e yia mi e dee.",
    "community_confirm":
        "GeoSentinel: i kpo-nammba ma {site} e yia {code}. "
        "E ka wo na 10 minit e yia.",
}
