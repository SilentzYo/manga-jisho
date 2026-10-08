# Manga Jisho

A Chrome extension and local Python server for reading raw Japanese manga in the browser. Hold Shift and hover over a word to look it up, or turn on page translation to have speech bubbles cleaned and typeset in English.

## How it works

- **OCR**: [mokuro](https://github.com/kha-white/mokuro) finds the text blocks on a page and [manga-ocr](https://github.com/kha-white/manga-ocr) reads each line in batches. A faster quantized model is available for slower machines.
- **Dictionary**: text is split into words with [fugashi](https://github.com/polm/fugashi), and the hovered word is matched against a SQLite build of [JMdict](https://github.com/scriptin/jmdict-simplified). Neighbouring tokens are joined into longer words and inflected forms are looked up by their dictionary form.
- **Translation**: Japanese text is erased with OpenCV, each bubble is translated with DeepL, and the English is typeset back into the bubble's shape.

## Setup

Needs Python 3.10+ and Chrome 114+.

```sh
cd server
pip install -r requirements.txt
python build_dictionary.py
python app.py
```

`build_dictionary.py` downloads the latest JMdict release into `server/data/`. The OCR models download on the first run. The server listens on `http://localhost:7331`.

To load the extension, open `chrome://extensions`, turn on Developer mode, click **Load unpacked** and pick the `extension` folder. Clicking the toolbar icon opens the side panel.

It is imperative that the extension can read on all sites, or at least the server (which you would have to manually access I guess) and the manga site.

## Usage

- **Look up a word**: hold Shift and hover over text on a manga page. Any image or canvas at least 300×400 counts as a page. Definitions show in the side panel with a link to search the word on [Jisho](https://jisho.org).
- **Translate pages**: switch on *Translate pages* in the side panel. This needs a DeepL API key, either in the side panel settings or as `DEEPL_API_KEY` in the server's environment. Free keys work.
- **Settings**: pick the accurate or fast OCR model, how many pages to scan ahead, and whether to outline detected text blocks.

The server also automatically starts for each session and is automatically stopped after 15 mins of non-use. You can restart the server in the settings


## License

[GPL-3.0](LICENSE). Comic Neue is under the [SIL Open Font License](server/fonts/OFL.txt).
