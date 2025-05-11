from config import *

def save_base64_icon_to_ico(path="icon.ico"):
    b64 = icon_base64().strip()
    img = Image.open(BytesIO(base64.b64decode(b64)))
    img.save(path, format="ICO")
    
save_base64_icon_to_ico()