import os
import sys

import requests

TARGET = "EN-US"
ERRORS = {
    403: "DeepL rejected the API key",
    456: "DeepL quota is used up for this month",
    429: "Too many requests to DeepL, try again in a moment",
}


class TranslationError(Exception):
    pass


def ask_deepl(texts, key, target):
    host = "api-free.deepl.com" if key.endswith(":fx") else "api.deepl.com"
    try:
        response = requests.post(
            f"https://{host}/v2/translate",
            headers={"Authorization": f"DeepL-Auth-Key {key}"},
            json={
                "text": texts,
                "source_lang": "JA",
                "target_lang": target,
                "context": "\n".join(texts),
            },
            timeout=30,
        )
    except requests.RequestException as error:
        raise TranslationError(f"Couldn't reach DeepL: {error}") from error

    if not response.ok:
        raise TranslationError(ERRORS.get(response.status_code, f"DeepL error (HTTP {response.status_code})"))
    return [translation["text"] for translation in response.json()["translations"]]


def translate(texts, key=None, target=TARGET):
    key = key or os.environ.get("DEEPL_API_KEY")
    if not key:
        raise TranslationError("No DeepL API key, set DEEPL_API_KEY")

    wanted = [text for text in texts if text.strip()]
    english = iter(ask_deepl(wanted, key, target) if wanted else [])
    return [next(english) if text.strip() else "" for text in texts]


if __name__ == "__main__":
    texts = sys.argv[1:] or ["お母さんが気をつけてって言ってた", "何作ってんだよ！！"]
    try:
        for japanese, english in zip(texts, translate(texts)):
            print(f"{japanese}\n  -> {english}")
    except TranslationError as error:
        print(error)
