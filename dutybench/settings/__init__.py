"""Available settings, by name. A new setting is a new package plus one line here."""

from dutybench.core.setting import Setting


def get_setting(name: str) -> Setting:
    if name == "lending":
        from dutybench.settings.lending import SETTING

        return SETTING
    raise ValueError(f"Unknown setting {name!r}. Available: lending")


SETTING_NAMES = ["lending"]
