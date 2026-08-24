"""Source 基类：统一接口 fetch() -> dict"""
import urllib.request, json, ssl, time, hashlib

UA = {'User-Agent': 'Mozilla/5.0 (compatible; Web3HotspotBot/3.0)'}
CTX = ssl.create_default_context()


class Source:
    name = "base"

    def __init__(self, timeout=8):
        self.timeout = timeout
        self.status = "skipped"
        self.error = ""

    def fetch(self):
        """返回 dict: {"status": "ok"|"failed"|"fallback", "data": ..., "error": ...}"""
        raise NotImplementedError

    # ---- 工具方法 ----
    def http_get(self, url, timeout=None, headers=None):
        h = dict(UA)
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, headers=h)
        resp = urllib.request.urlopen(req, timeout=timeout or self.timeout, context=CTX)
        return resp.read()

    def http_json(self, url, timeout=None, headers=None):
        raw = self.http_get(url, timeout, headers)
        return json.loads(raw)

    def ok(self, data):
        self.status = "ok"
        return {"status": "ok", "data": data}

    def fail(self, err):
        self.status = "failed"
        self.error = str(err)[:200]
        return {"status": "failed", "data": [], "error": self.error}

    @staticmethod
    def dedup_key(text):
        """标题归一化去重键：小写→去标点→去停用词→前20字符md5"""
        import re
        t = text.lower()
        t = re.sub(r"[\W_]+", "", t)
        stop = {"the", "a", "an", "of", "and", "or", "to", "in", "for", "on", "with",
                "是", "的", "了", "和", "与", "在", "为", "及", "及", "等"}
        t = "".join(c for c in t if c not in "".join(stop) or c.isalnum())
        return hashlib.md5(t[:40].encode()).hexdigest()[:16]
