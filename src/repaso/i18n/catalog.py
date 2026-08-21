from repaso.i18n.en import MESSAGES as EN_MESSAGES
from repaso.i18n.es import MESSAGES as ES_MESSAGES
from repaso.schemas.common import Lang

CATALOGS: dict[Lang, dict[str, str]] = {Lang.EN: EN_MESSAGES, Lang.ES: ES_MESSAGES}


def msg(key: str, lang: Lang, **kwargs: object) -> str:
    catalog = CATALOGS[lang]
    template = catalog.get(key)
    if template is None:
        template = CATALOGS[Lang.EN].get(key)
    if template is None:
        raise KeyError(f"unknown message key: {key}")
    return template.format(**kwargs)


def known_keys() -> set[str]:
    return set(EN_MESSAGES)
