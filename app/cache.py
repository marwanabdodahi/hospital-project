import redis
import json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

def get_cache(key):
    try:
        data = r.get(key)
        return json.loads(data) if data else None
    except:
        return None  

def set_cache(key, value):
    try:
        r.set(key, json.dumps(value), ex=60) 
    except:
        pass

def delete_cache(key):
    try:
        r.delete(key)
    except:
        pass