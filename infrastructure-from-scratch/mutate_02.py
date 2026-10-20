"""mutate_02 — CDN: EdgeCache, OriginShield, normalize_cache_key."""
import sys, os, tempfile, shutil, importlib.util, time, threading
HERE = os.path.dirname(os.path.abspath(__file__))
def _load(p):
    s = importlib.util.spec_from_file_location("m", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
def _v(s):
    c = s.EdgeCache()
    assert c.put("/api/p", {"items":[]}, "max-age=60") is True
    assert c.get("/api/p") == {"items":[]}
    assert c.put("/api/user", {"id":1}, "private, max-age=60") is False
    assert c.get("/api/user") is None
    c.put("/api/a", {"a":1}, "max-age=3600", surrogate_keys={"k1"})
    c.put("/api/b", {"b":2}, "max-age=3600", surrogate_keys={"k1"})
    assert c.purge_by_key("k1") == 2
    assert c.get("/api/a") is None
def _m(t,r,l=""): return (t,r,l)
def _c(p):
    try: _v(_load(p)); return False
    except: return True
def main():
    p = os.path.join(HERE,"solutions","cdn_caching.py")
    with open(p) as f: c = f.read()
    ms = [
        _m('self._store: Dict[str, CacheEntry] = {}', 'self._store: Dict[str, CacheEntry] = {}', 'store init ok'),
        _m('def get(self, key: str) -> Optional[Any]:', 'def get(self, key: str) -> Optional[Any]:\n        return None', 'get always null'),
        _m('return entry.body', 'return None  # broken body', 'body null'),
        _m('return (time.time() - entry.stored_at) < entry.max_age', 'return False  # never fresh', 'fresh always false'),
        _m('self._store[key] = entry', 'pass  # broken set', 'set broken'),
        _m('return True', 'return False  # always false', 'put always false'),
        _m('if "no-store" in directives or "private" in directives:', 'if False:  # broken no-store', 'no-store check broken'),
        _m('max_age = float(directives["max-age"])', 'max_age = 0.0  # zeroed', 'max-age zeroed'),
        _m('max_age = float(directives["s-maxage"])', 'max_age = 0.0  # zeroed s-maxage', 's-maxage zeroed'),
        _m('max_age = 60.0', 'max_age = 999999  # huge ttl', 'huge ttl'),
        _m('entry = CacheEntry(body, max_age, surrogate_keys or set(), swr)',
           'entry = CacheEntry(body, 0, set(), 0)  # zero ttl', 'entry zero ttl'),
        _m('def purge_by_key(self, surrogate_key: str) -> int:', 'def purge_by_key(self, surrogate_key: str) -> int:\n        return 0', 'purge always 0'),
        _m('to_delete = [k for k, e in self._store.items()\n                         if surrogate_key in e.surrogate_keys]',
           'to_delete = []  # no deletion', 'purge no-delete'),
        _m('del self._store[k]', 'pass  # broken del', 'del broken'),
        _m('def purge(self, key: str) -> bool:', 'def purge(self, key: str) -> bool:\n        return False', 'purge always false'),
        _m('if key in self._store:', 'if False:  # broken check', 'in check broken'),
        _m('return self._cache.get(key)', 'return None  # always miss', 'cache get broken'),
        _m('if cached is not None:', 'if False:  # broken check', 'cached check broken'),
        _m('result = self._origin(key)', 'result = None  # origin null', 'origin null'),
        _m('self._cache.put(key, result, f"max-age={int(self._ttl)}")', 'pass  # broken cache put', 'cache put broken'),
        _m('self._inflight[key] = event', 'pass  # broken inflight set', 'inflight set broken'),
        _m('self._inflight_result[key] = result', 'pass  # broken result set', 'result set broken'),
    ]
    caught=0; missed=0
    for i,(t,r,l) in enumerate(ms):
        if t not in c: missed+=1; print(f"  M{i+1:03d}: SKIP  {l}"); continue
        td=tempfile.mkdtemp(prefix=f"m02-{i}-")
        try:
            mt=c.replace(t,r,1); tp=os.path.join(td,"cdn_caching.py")
            with open(tp,"w") as f: f.write(mt)
            if _c(tp): caught+=1; print(f"  M{i+1:03d}: CAUGHT  {l}")
            else: missed+=1; print(f"  M{i+1:03d}: MISSED  {l}")
        finally: shutil.rmtree(td,ignore_errors=True)
    print(f"\nMUTATE: CAUGHT {caught} / {caught+missed}  MISSED {missed}")
main()