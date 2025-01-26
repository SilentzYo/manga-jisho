import cv2
from PIL import Image
from PIL import ImageFilter

im_file = "testimg/testimg.jpg"
im = Image.open(im_file)

# im.rotate(90).show()

def grayscale(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

gray_image = grayscale(im)
#cv2.imwrite("temp/gray.jpg", gray_image)
gray_image.show()