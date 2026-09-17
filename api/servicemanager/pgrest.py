from logging import getLogger
from random import randint

import requests

from api.config import BotjagwarConfig
from api.http_client import DEFAULT_HTTP_TIMEOUT

log = getLogger("pgrest")
config = BotjagwarConfig()


class BackendError(Exception):
    pass


class Backend(object):
    postgrest = config.get("postgrest_backend_address")

    def check_postgrest_backend(self):
        if not self.postgrest:
            raise BackendError(
                "No Postgrest defined. "
                'set "postgrest_backend_address" to use this. '
                "Expected service port is 8100"
            )


class StaticBackend(Backend):
    @property
    def backend(self):
        self.check_postgrest_backend()
        return f"http://{self.postgrest}"


class DynamicBackend(Backend):
    backends = [
        "http://" + Backend.postgrest + ":81%s" % (f"{i}".zfill(2)) for i in range(16)
    ]

    @property
    def backend(self):
        self.check_postgrest_backend()
        return self.backends[randint(0, len(self.backends) - 1)]


class PostgrestBackend(object):
    backend = StaticBackend()

    def __init__(self, use_postgrest: [bool, str] = "automatic"):
        """
        Translate templates
        :param use_postgrest: True or False to fetch on template_translations table.
        Set this argument to 'automatic' to use `postgrest_backend_address` only if it's filled
        """
        if use_postgrest == "automatic":
            try:
                self.online = bool(self.backend.backend)
            except BackendError:
                self.online = False
        else:
            assert isinstance(use_postgrest, bool)
            self.online = use_postgrest


class TemplateTranslation(PostgrestBackend):
    """
    Controller to fetch already-defined template name mappings
    from the Postgres database through PostgREST.
    """

    def get_mapped_template_in_database(
        self, title: str, target_language: str = "mg"
    ) -> str | None:
        """Return a template mapping without failing translation on backend errors."""
        if self.online:
            try:
                return self.postgrest_get_mapped_template_in_database(
                    title, target_language
                )
            except (BackendError, requests.RequestException) as exc:
                log.warning(
                    "Unable to look up template mapping for %r; preserving the original template: %s",
                    title,
                    exc,
                )
        return None

    def add_translated_title(
        self, title, translated_title, source_language="en", target_language="mg"
    ):
        if self.online:
            return self.postgrest_add_translated_title(
                title, translated_title, source_language, target_language
            )

    def postgrest_get_mapped_template_in_database(
        self, title: str, target_language: str = "mg"
    ) -> str | None:
        """Fetch a template mapping from PostgREST and validate its response."""
        response = requests.get(
            f"{self.backend.backend}/template_translations",
            params={
                "source_template": f"eq.{title}",
                "target_language": f"eq.{target_language}",
            },
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
        if response.status_code == 404:  # HTTP Not found
            return None
        if response.status_code != 200:  # other HTTP error
            raise BackendError(
                f"Unexpected error: HTTP {response.status_code}; {response.text}"
            )

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise BackendError("PostgREST returned a non-JSON template response") from exc

        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            raise BackendError("PostgREST returned an invalid template response")

        target_template = data.get("target_template")
        return target_template if isinstance(target_template, str) else None

    def postgrest_add_translated_title(
        self, title, translated_title, source_language="en", target_language="mg"
    ):
        response = requests.post(
            f"{self.backend.backend}/template_translations",
            json={
                "source_template": title,
                "target_template": translated_title,
                "source_language": source_language,
                "target_language": target_language,
            },
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
        if response.status_code in {400, 500}:  # HTTP Bad request or HTTP server error:
            raise BackendError(
                f"Unexpected error: HTTP {response.status_code}; {response.text}"
            )

        return None


class JsonDictionary(PostgrestBackend):
    def __init__(
        self,
        use_postgrest: [bool, str] = "automatic",
        use_materialised_view: [bool] = True,
    ):
        super(JsonDictionary, self).__init__(use_postgrest)
        if use_materialised_view:
            self.endpoint_name = "/json_dictionary"
        else:
            self.endpoint_name = "/vw_json_dictionary"

    def look_up_dictionary(self, w_language, w_part_of_speech, w_word):
        params = {
            "language": f"eq.{w_language}",
            "part_of_speech": f"eq.{w_part_of_speech}",
            "word": f"eq.{w_word}",
        }
        resp = requests.get(
            self.backend.backend + self.endpoint_name,
            params=params,
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
        return resp.json()

    def look_up_word(self, language, part_of_speech, word):
        params = {
            "language": f"eq.{language}",
            "part_of_speech": f"eq.{part_of_speech}",
            "word": f"eq.{word}",
        }
        log.debug(params)
        resp = requests.get(
            f"{self.backend.backend}/word",
            params=params,
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
        return resp.json()


class ConvergentTranslations(PostgrestBackend):
    endpoint = "/convergent_translations"

    def get_convergent_translation(
        self,
        target_language,
        en_definition=None,
        fr_definition=None,
        suggested_definition=None,
        part_of_speech=None,
    ):
        params = {
            # 'language': 'eq.' + target_language
        }
        if part_of_speech is not None:
            params["part_of_speech"] = f"eq.{part_of_speech}"
        if en_definition is not None:
            params["en_definition"] = f"eq.{en_definition}"
        if fr_definition is not None:
            params["fr_definition"] = f"eq.{fr_definition}"
        if suggested_definition is not None:
            params["suggested_definition"] = f"eq.{suggested_definition}"
        if len(params) < 2:
            raise BackendError(
                "Expected at least one of 'en_definition', 'fr_definition' or 'suggested_definition'"
            )

        response = requests.get(
            self.backend.backend + self.endpoint,
            params=params,
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
        data = response.json()
        if response.status_code == 200:  # HTTP OK
            return data
        if response.status_code == 404:  # HTTP Not found
            return None

        # other HTTP error:
        raise BackendError(
            f"Unexpected error: HTTP {response.status_code}; {response.text}"
        )

    def get_suggested_translations_fr_mg(
        self,
        target_language,
        definition=None,
        suggested_definition=None,
        part_of_speech=None,
    ):
        params = {
            # 'language': 'eq.' + target_language
        }
        if part_of_speech is not None:
            params["part_of_speech"] = f"eq.{part_of_speech}"
        if definition is not None:
            params["definition"] = f"eq.{definition}"
        if suggested_definition is not None:
            params["suggested_definition"] = f"eq.{suggested_definition}"

        response = requests.get(
            f"{self.backend.backend}/suggested_translations_fr_mg",
            params=params,
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
        data = response.json()
        if response.status_code == 200:  # HTTP OK
            return data

        # other HTTP error:
        raise BackendError(
            f"Unexpected error: HTTP {response.status_code}; {response.text}"
        )
