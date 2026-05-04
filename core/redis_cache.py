import redis
import json
import time
import os

class RedisWallCache:
    def __init__(self, host='localhost', port=6379, db=0):
        self.use_failover = False
        try:
            self.r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            self.r.ping()
        except:
            print("⚠️ Redis OFFLINE. Using Local JSON Failover (Performance Degraded).")
            self.use_failover = True
            self.failover_path = "/home/wek/Escritorio/ccxtv2/logs/redis_failover.json"
            os.makedirs(os.path.dirname(self.failover_path), exist_ok=True)
            if not os.path.exists(self.failover_path):
                with open(self.failover_path, 'w') as f: json.dump({}, f)

    def _get_failover_data(self):
        with open(self.failover_path, 'r') as f: return json.load(f)

    def _set_failover_data(self, data):
        with open(self.failover_path, 'w') as f: json.dump(data, f)

    def set_wall_state(self, symbol, price, size, ticker_price):
        clean_symbol = symbol.replace("/", "").replace(":", "").lower()
        state = {'t': time.time(), 'p': price, 's': size, 'tp': ticker_price}
        
        if self.use_failover:
            data = self._get_failover_data()
            if clean_symbol not in data: data[clean_symbol] = []
            data[clean_symbol].append(state)
            # Keep only last 10
            data[clean_symbol] = data[clean_symbol][-10:]
            self._set_failover_data(data)
            return

        key_latest = f"prod:{clean_symbol}:wall:latest"
        key_history = f"prod:{clean_symbol}:wall:v_vec"
        self.r.hset(key_latest, mapping=state)
        self.r.zadd(key_history, {json.dumps(state): state['t']})
        self.r.expire(key_history, 3600)

    def get_prev_state(self, symbol):
        clean_symbol = symbol.replace("/", "").replace(":", "").lower()
        
        if self.use_failover:
            data = self._get_failover_data()
            history = data.get(clean_symbol, [])
            return history[-2] if len(history) >= 2 else None

        key_history = f"prod:{clean_symbol}:wall:v_vec"
        history = self.r.zrange(key_history, -2, -2)
        if history: return json.loads(history[0])
        return None

# Integration into Action:
# prev = cache.get_prev_state(symbol)
# if prev:
#    dt = curr_t - prev['t']
#    v_price = (ticker_price - prev['tp']) / dt
#    v_wall = (price - prev['p']) / dt
