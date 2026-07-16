import gettext
import locale
import os

_translator = None


def setup_i18n(config=None):
    """Initialize the i18n system. Call once at startup, before any UI code."""
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
    return _translator


def get_language():
    if _translator:
        info = _translator.info()
        if info and "language" in info:
            return info["language"]
    return "en"


def _detect_system_language():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val and val != "C" and val != "POSIX":
            return val.split(":")[0]
    return None


def _(text):
    """Translate text using the current UI language.

    Uses the installed translator from setup_i18n().
    Falls back to English if setup hasn't been called yet.
    """
    import builtins
    if hasattr(builtins, '_'):
        return builtins._(text)
    return text
