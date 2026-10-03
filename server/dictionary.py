import json
import sqlite3
import sys
from functools import cache
from pathlib import Path

from words import tokenize

DATABASE = Path(__file__).parent / "data" / "jmdict.sqlite"
GRAMMAR = {"助詞", "助動詞", "接尾辞"}
GRAMMAR_TAGS = {"prt", "aux", "aux-v", "aux-adj", "cop", "suf"}
MAX_TOKENS = 5
MAX_ENTRIES = 6


@cache
def database():
    if not DATABASE.exists():
        raise RuntimeError("No dictionary yet, run server/build_dictionary.py first")
    db = sqlite3.connect(DATABASE, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def hiragana(text):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def is_grammar(entry):
    return any(tag in GRAMMAR_TAGS for sense in entry["senses"] for tag in sense["pos"])


def spans(tokens, hovered):
    for i in range(max(0, hovered - MAX_TOKENS + 1), hovered + 1):
        for j in range(hovered, min(len(tokens), i + MAX_TOKENS)):
            span = tokens[i:j + 1]
            if len(span) > 1 and span[0]["pos"] in GRAMMAR:
                continue
            if all(a["end"] == b["start"] for a, b in zip(span, span[1:])):
                yield i, j, "".join(token["text"] for token in span[:-1]) + span[-1]["base"]


def find(words):
    marks = ",".join("?" * len(words))
    return database().execute(f"""
        SELECT forms.text, forms.common, forms.kanji OR entries.kana_usual AS preferred,
               entries.id, entries.data
        FROM forms JOIN entries ON entries.id = forms.entry
        WHERE forms.text IN ({marks})
    """, list(words)).fetchall()


def lookup(text, at):
    tokens = tokenize(text)
    hovered = next((n for n, token in enumerate(tokens) if token["start"] <= at < token["end"]), None)
    if hovered is None:
        return None

    candidates = {}
    for i, j, word in spans(tokens, hovered):
        for variant in (word, hiragana(word)):
            candidates.setdefault(variant, (i, j, word))

    rows = find(candidates)
    if not rows:
        token = tokens[hovered]
        return {"word": token["text"], "start": token["start"], "end": token["end"], "entries": []}

    def order(row):
        i, j, word = candidates[row["text"]]
        length = tokens[j]["end"] - tokens[i]["start"]
        wants_grammar = i == j and tokens[i]["pos"] in GRAMMAR
        fits = is_grammar(json.loads(row["data"])) == wants_grammar
        return -length, -i, not fits, not row["common"], row["text"] != word, not row["preferred"], row["id"]

    rows = sorted(rows, key=order)
    longest = order(rows[0])[:2]
    entries = {}
    for row in rows:
        if order(row)[:2] == longest or row["preferred"]:
            entries.setdefault(row["id"], row["data"])

    i, j, word = candidates[rows[0]["text"]]
    return {
        "word": word,
        "start": tokens[i]["start"],
        "end": tokens[j]["end"],
        "entries": [json.loads(data) for data in list(entries.values())[:MAX_ENTRIES]],
    }


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "お母さんが気をつけてって言ってた"
    print(text)
    for at, character in enumerate(text):
        result = lookup(text, at)
        if not result:
            print(f"  {character}  (nothing)")
        elif not result["entries"]:
            print(f"  {character}  {result['word']}  (not in dictionary)")
        else:
            entry, *others = result["entries"]
            reading = entry["kana"][0] if entry["kana"] else ""
            meaning = "; ".join(entry["senses"][0]["glosses"][:3])
            also = ", ".join((other["kanji"] or other["kana"])[0] for other in others)
            print(f"  {character}  {result['word']} [{result['start']}:{result['end']}]  {reading}  {meaning}  (also: {also})")
