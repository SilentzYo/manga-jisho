import io
import json
import re
import sqlite3
import zipfile

import requests

from dictionary import DATABASE

RELEASES = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"


def download():
    release = requests.get(RELEASES, timeout=30).json()
    asset = next(a for a in release["assets"] if re.fullmatch(r"jmdict-eng-\d.*\.json\.zip", a["name"]))
    print("Downloading", asset["name"])
    response = requests.get(asset["browser_download_url"], timeout=300)
    response.raise_for_status()
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    return json.loads(archive.read(archive.namelist()[0]))["words"]


def compact(word):
    return {
        "kanji": [form["text"] for form in word["kanji"] if "sK" not in form["tags"]],
        "kana": [form["text"] for form in word["kana"] if "sk" not in form["tags"]],
        "senses": [
            {
                "pos": sense["partOfSpeech"],
                "misc": sense["misc"],
                "glosses": [gloss["text"] for gloss in sense["gloss"]],
            }
            for sense in word["sense"]
        ],
    }


def build(words):
    DATABASE.parent.mkdir(exist_ok=True)
    DATABASE.unlink(missing_ok=True)
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE entries (id INTEGER PRIMARY KEY, kana_usual INTEGER, data TEXT);
        CREATE TABLE forms (text TEXT, entry INTEGER, kanji INTEGER, common INTEGER);
    """)
    for word in words:
        entry_id = int(word["id"])
        kana_usual = not word["kanji"] or "uk" in word["sense"][0]["misc"]
        data = json.dumps(compact(word), ensure_ascii=False)
        db.execute("INSERT INTO entries VALUES (?, ?, ?)", (entry_id, kana_usual, data))
        db.executemany("INSERT INTO forms VALUES (?, ?, ?, ?)", [
            (form["text"], entry_id, kind == "kanji", form["common"])
            for kind in ("kanji", "kana")
            for form in word[kind]
        ])
    db.execute("CREATE INDEX forms_text ON forms (text)")
    db.commit()
    db.close()


if __name__ == "__main__":
    words = download()
    print(f"Building {DATABASE.name} from {len(words)} entries")
    build(words)
    print("Done")
