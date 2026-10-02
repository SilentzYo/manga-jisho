import sys

from fugashi import Tagger

tagger = Tagger()


def tokenize(text):
    tokens = []
    position = 0
    for word in tagger(text):
        position += len(word.white_space)
        start, position = position, position + len(word.surface)
        if word.feature.pos1 == "補助記号":
            continue
        tokens.append({
            "text": word.surface,
            "base": word.feature.orthBase or word.surface,
            "pos": word.feature.pos1,
            "start": start,
            "end": position,
        })
    return tokens


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "食べなかった"
    print(text)
    for token in tokenize(text):
        print(f"  [{token['start']}:{token['end']}] {token['text']} -> {token['base']} ({token['pos']})")
