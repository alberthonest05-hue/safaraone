import re

with open("data/mock_data.py", "r") as f:
    text = f.read()

# I will use re.sub with a function to dynamically replace the image based on preceding destination id and category
def repl_dest(m):
    return '"https://source.unsplash.com/400x300/?tanzania,' + m.group(1) + '"'

text = re.sub(r'"id": "([^"]+)",\n\s+"name": "[^"]+",\n(?:.*?)"image_url": "([^"]+)"', lambda m: m.group(0).replace(m.group(2), f"https://source.unsplash.com/400x300/?{m.group(1)},landscape"), text, flags=re.DOTALL)

# Let me just write a quick script that uses `ast` or `exec` to modify the variables if I lost them? No, I overwrote it with `https://source.unsplash.com/400x300/?tanzania` earlier.
