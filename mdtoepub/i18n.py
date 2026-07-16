import gettext
import locale
import os

_translator = None


def setup_i18n(config=None):
    """Initialize the i18n system. Call once at startup, before any UI code.

    Args:
        config: global config dict. If config["ui_language"] is set,
                use that language instead of auto-detecting.
    """
    global _translator

    locale_dir = os.path.join(os.path.dirname(__file__), "locale")
    domain = "mdtoepub"

    lang = None
    if config and config.get("ui_language", "").strip():
        lang = config["ui_language"].strip()

    if not lang:
        lang = _detect_system_language()

    if not lang:
        lang = "en"

    lang = lang.split(".")[0].split("@")[0]

    try:
        _translator = gettext.translation(domain, locale_dir, languages=[lang], fallback=True)
    except Exception:
        _translator = gettext.translation(domain, locale_dir, languages=["en"], fallback=True)

    _translator.install()


def get_translator():
    """Return the current gettext translator object."""
    return _translator


def get_language():
    """Return the currently active UI language code."""
    if _translator:
        info = _translator.info()
        if info and "language" in info:
            return info["language"]
    return "en"


def _detect_system_language():
    """Detect the system language from environment variables."""
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val and val != "C" and val != "POSIX":
            return val.split(":")[0]
    return None
