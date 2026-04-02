import json

filepath = 'data/mock_data.py'
import importlib.util
import sys

# Load module safely to inspect
spec = importlib.util.spec_from_file_location("mock_data", filepath)
mock = importlib.util.module_from_spec(spec)
sys.modules["mock_data"] = mock
spec.loader.exec_module(mock)

def update_image(obj, target_type):
    # Determine new url based on target_type and specifics
    # Dest
    if target_type == 'dest':
        if obj['id'] == 'zanzibar':
            return 'https://images.unsplash.com/photo-1590523277543-a94d2e4eb00b?w=800&q=80'
        elif obj['id'] == 'serengeti':
            return 'https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800&q=80'
        elif obj['id'] == 'kilimanjaro':
            return 'https://images.unsplash.com/photo-1589308078059-be1415eab4c3?w=800&q=80'
    elif target_type == 'accom':
        d_id = obj['destination_id']
        t = obj['type']
        tier = obj.get('tier', '')
        if d_id == 'zanzibar':
            if tier == 'luxury' and 'resort' in t:
                return 'https://images.unsplash.com/photo-1596436574961-e5c9f639e6c4?w=800&q=80'
            elif 'boutique' in t:
                return 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=800&q=80'
            elif 'guesthouse' in t or 'budget' in tier:
                return 'https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=80'
            else:
                return 'https://images.unsplash.com/photo-1596436574961-e5c9f639e6c4?w=800&q=80'
        elif d_id == 'serengeti':
            if 'tented' in t:
                return 'https://images.unsplash.com/photo-1523805009345-7448845a9e53?w=800&q=80'
            else:
                return 'https://images.unsplash.com/photo-1493246507139-91e8fad9978e?w=800&q=80'
        elif d_id == 'kilimanjaro':
            return 'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=800&q=80'
    elif target_type == 'exp':
        c = obj['category'].lower()
        title = obj['title'].lower()
        if 'wildlife' in c or 'safari' in title:
            return 'https://images.unsplash.com/photo-1516426122078-c23e76319801?w=800&q=80'
        elif 'dolphin' in title or 'dhow' in title or 'boat' in title:
            return 'https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=800&q=80'
        elif 'snorkeling' in title or 'beach' in title or 'snork' in title:
            return 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?w=800&q=80'
        elif 'trekking' in c or 'hike' in title or 'trek' in title:
            return 'https://images.unsplash.com/photo-1551632811-561732d1e306?w=800&q=80'
        elif 'climb' in title or 'summit' in title:
            return 'https://images.unsplash.com/photo-1621414050945-1a9f2f966e56?w=800&q=80'
        elif 'spice' in title:
            return 'https://images.unsplash.com/photo-1596040033229-a9821ebd058d?w=800&q=80'
        elif 'coffee' in title:
            return 'https://images.unsplash.com/photo-1447933601403-0c6688de566e?w=800&q=80'
        elif 'food' in c or 'culture' in c or 'cultural' in c:
            return 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=800&q=80'
        else:
            return 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=800&q=80'
    elif target_type == 'guide':
        # Provide avatars sequentially
        avatars = [
            'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=400&q=80',
            'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&q=80',
            'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=400&q=80',
            'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=400&q=80'
        ]
        return avatars[hash(obj['id']) % len(avatars)]
    return None

def main():
    import pprint
    with open(filepath, 'r') as f:
        content = f.read()
    
    # We will replace URLs by doing string replacement on the old URLs with the new URLs
    replacements = {}
    
    for d in mock.DESTINATIONS:
        new_url = update_image(d, 'dest')
        replacements[d['image_url']] = new_url
        
    for a in mock.ACCOMMODATIONS:
        new_url = update_image(a, 'accom')
        replacements[a['image_url']] = new_url
        
    for e in mock.EXPERIENCES:
        new_url = update_image(e, 'exp')
        replacements[e['image_url']] = new_url
        
    for g in mock.GUIDES:
        new_url = update_image(g, 'guide')
        replacements[g['avatar_url']] = new_url
        
    for old, new in replacements.items():
        if old and new:
            content = content.replace(f"'{old}'", f"'{new}'")
            content = content.replace(f'"{old}"', f'"{new}"')
            
    with open(filepath, 'w') as f:
        f.write(content)
        
    print("Images correctly updated in mock_data.py")

if __name__ == '__main__':
    main()
