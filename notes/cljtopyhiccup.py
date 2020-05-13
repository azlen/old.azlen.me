from pyhiccup.core import convert
import re
import json

test = """:hiccup [:div {:onclick "document.body.classList.toggle('test')" :style {:background-color "red" :width "100px" :height "200px" :display "flex"}} xy [:button XYZ]]"""

def cljtopy(text):
    #data = re.sub(r'(?!=[}\]\"\'])[\s\n]+?([\[:\{\"])', r', \1', text.strip())
    data = re.sub(r':([\w-]+)', r'"\1":', text.strip())
    data = re.sub(r'([\}\]\:][\s]*?)(\w+)([\s]*?[\[\{\]])', r'\1"\2"\3', data)
    data = re.sub(r'([\}\]\"])([\s\n]*?)([\[\{\"])', r'\1,\2\3', data)
    #data = re.sub(r':(\w+)', r'"\1",', data)
    #data = re.sub(r',+', r',', data)
    #data = re.sub(r':,', r':', data)
    #data = re.sub(r'([^"\w])(\w+)([^"\w])', r'\1"\2"\3', data)

    return data[10:]

print(cljtopy(test))