from PIL import Image
import pytesseract
print(pytesseract.image_to_string(Image.open('C:\Users\hello\Documents\Manga-Translator\manga-translation-reader\testimg\puretext.jpg')))