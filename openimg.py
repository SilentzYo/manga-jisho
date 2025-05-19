import cv2
import numpy as np
from PIL import Image
from PIL import ImageFilter

im_file = "testimg/testimg.jpg"
im = Image.open(im_file)

# im.rotate(90).show()

def grayscale(image):
    opencv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(opencv_img, cv2.COLOR_BGR2GRAY)
    return Image.fromarray(gray)

gray_image = grayscale(im)
#cv2.imwrite("temp/gray.jpg", gray_image)
gray_image.show()