"""Bounded chat history with Redis TTL; memory mode supports an offline demo."""

import json
from collections import OrderedDict


class MemoryHistory:
    def __init__(self):
        self._messages = OrderedDict()

    async def get(self, user_id):
        return list(self._messages.get(str(user_id), []))

    async def append(self, user_id, role, content):
        key = str(user_id)
        messages = self._messages.setdefault(key, [])
        messages.append({"role": role, "content": content})
        self._messages[key] = messages[-20:]
        self._messages.move_to_end(key)
        while len(self._messages) > 1000:
            self._messages.popitem(last=False)

    async def close(self):
        self._messages.clear()


class RedisHistory:
    def __init__(self, url):
        from redis.asyncio import Redis

        self.client = Redis.from_url(url, decode_responses=True)

    async def get(self, user_id):
        values = await self.client.lrange(f"chat_history:{user_id}", 0, -1)
        return [json.loads(value) for value in values]

    async def append(self, user_id, role, content):
        key = f"chat_history:{user_id}"
        async with self.client.pipeline(transaction=True) as pipeline:
            pipeline.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
            pipeline.ltrim(key, -20, -1)
            pipeline.expire(key, 86400)
            await pipeline.execute()

    async def close(self):
        await self.client.aclose()
