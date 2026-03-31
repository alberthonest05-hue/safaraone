import re

with open("data/mock_data.py", "r") as f:
    content = f.read()

# Destinations
content = re.sub(r'("image_url": "https://images.unsplash.com/photo-[^"]+w=\d+.*?)(?=",\n\s+"gallery")', 
                 r'"https://source.unsplash.com/400x300/?tanzania,landscape', content, count=3)

# Replace all gallery images
content = re.sub(r'"https://images.unsplash.com/photo-[^"]+"', r'"https://source.unsplash.com/400x300/?tanzania"', content)

with open("data/mock_data.py", "w") as f:
    f.write(content)
