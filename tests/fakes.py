class MemoryCache:
    """Dict-backed Cache. Records puts as (key, value, ttl_sec); a set error is raised by
    every get and put instead."""

    def __init__(self, entries=None, error=None):
        self.entries = dict(entries or {})
        self.error = error
        self.puts = []

    async def get(self, key):
        if self.error is not None:
            raise self.error
        return self.entries.get(key)

    async def put(self, key, value, ttl_sec):
        if self.error is not None:
            raise self.error
        self.puts.append((key, value, ttl_sec))
        self.entries[key] = value
