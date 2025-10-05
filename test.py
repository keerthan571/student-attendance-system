from pyzbar.pyzbar import decode
from PIL import Image

img = Image.open("test_qr.png")
print(decode(img))
