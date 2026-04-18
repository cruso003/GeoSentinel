"""Local-language SMS templates for the community channel (Spec §9.3).

Template keys mirror the Alert ``alert_type`` + ``severity``. Rendering is
naive ``str.format(**fields)`` — templates are trusted static strings under
version control, not user input. Languages available for the Tokadeh pilot:

- ``en`` — English (baseline)
- ``mano`` — Mano (Mann / Mah), spoken across Nimba County
- ``gio`` — Dan (Gio), the other dominant language in the region

Add new language files as plain Python mappings; ``render()`` falls back to
English if a key is missing so a new alert type never silences the channel.
"""

from __future__ import annotations

from . import en, gio, mano  # noqa: F401  (imported for side-effect registration)

_REGISTRY = {"en": en.TEMPLATES, "mano": mano.TEMPLATES, "gio": gio.TEMPLATES}


def render(*, language: str, key: str, **fields: str) -> str:
    """Render ``key`` in ``language``, falling back to English, then to a
    generic one-liner that always includes the severity + site."""
    pack = _REGISTRY.get(language, en.TEMPLATES)
    template = pack.get(key) or en.TEMPLATES.get(key)
    if template is None:
        template = en.TEMPLATES["fallback"]
    try:
        return template.format(**fields)
    except KeyError:
        # Missing interpolation field — don't crash the alert pipeline.
        return en.TEMPLATES["fallback"].format(**fields)


AVAILABLE_LANGUAGES = tuple(_REGISTRY.keys())
