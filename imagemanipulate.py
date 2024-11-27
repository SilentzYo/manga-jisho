from PIL import Image
im_file = "testimg/puretext.jpg"

im = Image.open(im_file)
im.rotate(90).show()
