import time
from services.planner import client
try:
    t0=time.time()
    client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])
except Exception as e:
    print("Failed in", time.time()-t0, "seconds:", e)
