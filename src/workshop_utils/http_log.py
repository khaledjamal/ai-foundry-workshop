"""Log every HTTP request and response a script makes, in one format, with secrets redacted.

Call `enable()` once at the start of a script. It wraps the one transport method that every request of an HTTP
library passes through, so calls made by clients built deep inside an SDK are logged too:

- requests (`HTTPAdapter.send`): plain REST calls, the azure-* SDKs (azure-core) and azure-identity
- httpx2 and httpx (`HTTPTransport.handle_request` and its async twin): openai, Semantic Kernel, AutoGen, the MCP
  client

Output (the format of a Spring RestTemplate logging interceptor, with a call number to pair the two blocks):

    --- OUTBOUND REQUEST #1 ---
    > POST https://<resource>.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=...
    > Authorization: Bearer <redacted>
    > Content-Type: application/json
    >
    {
      "messages": [...]
    }

    --- OUTBOUND RESPONSE #1 ---
    < 200 OK
    < Content-Type: application/json
    <
    {
      "choices": [...]
    }

Settings (environment variables, or the arguments of `enable()`, which take precedence):
    HTTP_LOG           full (default) | summary (one line per call) | off
    HTTP_LOG_METRICS   false (default) | true: time, sizes and token usage per call, and totals when the script ends
    HTTP_LOG_MAX_BODY  characters shown of each body (default 8192); the rest is cut with "...more..."
    HTTP_LOG_POLLS     short (default) | full: how status checks are logged

Status checks: a GET to the same URL as an earlier GET (an agent run polled until it ends, for example) is logged as
one line with the reply's "status" field, `HTTP #7 GET <url> -> 200 OK, status: in_progress`. The first GET of a URL
is logged in full, so the reply's shape is shown once.

Secrets are redacted: authorization and key headers, cookies, key and signature query parameters (for example the
Functions `?code=` key), and token, password and credential fields in JSON and form bodies. Long strings inside JSON
(base64 images, for example) are shortened and binary bodies are shown as type and size.

The response block is written once its body has been read, so a streamed reply (server-sent events) is logged when
the stream ends, without slowing the stream down. aiohttp (the azure .aio clients) is not covered.
"""

import atexit
import itertools
import json
import logging
import os
import sys
import threading
import time
import zlib
from urllib.parse import unquote_plus

logger = logging.getLogger("http_log")

LEVELS = ("full", "summary", "off")
POLL_MODES = ("short", "full")
DEFAULT_MAX_BODY = 8 * 1024
REDACTED = "<redacted>"
# Header, query parameter and body field names whose values are secrets (compared in lower case).
SECRET_HEADERS = {
    "authorization",
    "proxy-authorization",
    "api-key",
    "ocp-apim-subscription-key",
    "x-functions-key",
    "cookie",
    "set-cookie",
}
SECRET_PARAMS = {
    "code",
    "sig",
    "key",
    "api-key",
    "api_key",
    "subscription-key",
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "client_assertion",
    "assertion",
    "password",
}
SECRET_FIELDS = {
    "access_token",
    "refresh_token",
    "id_token",
    "client_secret",
    "client_assertion",
    "password",
    "api_key",
    "apikey",
    "primarykey",
    "secondarykey",
    "connectionstring",
    "connection_string",
    "credentials",
}
LONG_STRING = 1000
BINARY_TYPES = ("image/", "audio/", "video/", "application/octet-stream", "application/pdf", "application/zip")
MAX_CAPTURE = 1024 * 1024  # bytes of a body kept for the log; the rest is counted, not stored

_settings = {"level": "full", "metrics": False, "max_body": DEFAULT_MAX_BODY, "polls": "short"}
_originals = {}  # (class, method name) -> original function, to restore in disable()
_call_numbers = itertools.count(1)
_lock = threading.Lock()
_pending = set()
_seen_gets = set()  # URLs already fetched with GET; a repeat is a status check
_totals = {"calls": 0, "seconds": 0.0, "sent": 0, "received": 0, "input_tokens": 0, "output_tokens": 0}


def enable(level=None, metrics=None, max_body=None, polls=None):
    """Start logging HTTP calls. Safe to call more than once; later calls only change the settings."""
    level = level or os.environ.get("HTTP_LOG", "full").strip().lower() or "full"
    if level not in LEVELS:
        raise ValueError(f"HTTP_LOG must be one of {', '.join(LEVELS)}, not {level!r}")
    if metrics is None:
        metrics = os.environ.get("HTTP_LOG_METRICS", "false").strip().lower() in ("1", "true", "yes", "on")
    if max_body is None:
        max_body = int(os.environ.get("HTTP_LOG_MAX_BODY", DEFAULT_MAX_BODY))
    polls = polls or os.environ.get("HTTP_LOG_POLLS", "short").strip().lower() or "short"
    if polls not in POLL_MODES:
        raise ValueError(f"HTTP_LOG_POLLS must be one of {', '.join(POLL_MODES)}, not {polls!r}")
    _settings.update(level=level, metrics=metrics, max_body=max_body, polls=polls)
    if level == "off":
        disable()
        return
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)  # stdout, so the blocks stay in order with the script's prints
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    _patch_requests()
    for name in ("httpx2", "httpx"):
        _patch_httpx(name)


def disable():
    """Stop logging: put the original transport methods back."""
    for (cls, name), original in _originals.items():
        setattr(cls, name, original)
    _originals.clear()
    _seen_gets.clear()


# ---------------------------------------------------------------------------------------------------------------
# One HTTP call: writes the request block when it starts and the response block when its body has been read.


class _Call:
    def __init__(self, method, url, headers, body, content_type):
        self.number = next(_call_numbers)
        self.method = method
        self.url = _redact_url(str(url))
        self.sent = len(body) if isinstance(body, bytes) else 0
        self.start = time.perf_counter()
        self.done = False
        self.status = None
        self.reason = ""
        self.headers = []
        self.encoding = None
        self.chunks = []
        self.captured = 0
        self.received = 0
        with _lock:
            _pending.add(self)
            self.poll = method == "GET" and _settings["polls"] == "short" and self.url in _seen_gets
            if method == "GET":
                _seen_gets.add(self.url)
        if _settings["level"] == "full" and not self.poll:
            lines = [f"--- OUTBOUND REQUEST #{self.number} ---", f"> {method} {self.url}"]
            lines += [f"> {name}: {_redact_header(name, value)}" for name, value in headers]
            text = _format_body(body, content_type)
            if text:
                lines += [">", text]
            _write(lines)

    def response(self, status, reason, headers, encoding=None):
        """Status and headers arrived; `encoding` is the Content-Encoding the body bytes still have, if any."""
        self.status, self.reason, self.headers = status, reason or "", list(headers)
        self.encoding = encoding

    def record(self, chunk):
        self.received += len(chunk)
        if self.captured < MAX_CAPTURE:
            self.chunks.append(chunk)
            self.captured += len(chunk)

    def finish(self, note=None):
        if self.done:
            return
        self.done = True
        seconds = time.perf_counter() - self.start
        with _lock:
            _pending.discard(self)
        body = _decode(b"".join(self.chunks), self.encoding)
        content_type = _header(self.headers, "content-type")
        usage = _usage(body, content_type) if _settings["metrics"] else None
        if _settings["metrics"]:
            with _lock:
                _totals["calls"] += 1
                _totals["seconds"] += seconds
                _totals["sent"] += self.sent
                _totals["received"] += self.received
                if usage:
                    _totals["input_tokens"] += usage[0]
                    _totals["output_tokens"] += usage[1]
        metrics = _metrics_text(seconds, self.sent, self.received, usage) if _settings["metrics"] else ""
        if _settings["level"] == "summary" or self.poll:
            line = f"HTTP #{self.number} {self.method} {self.url} -> {self.status} {self.reason}".rstrip()
            status = _status_field(body, content_type)
            line += f", status: {status}" if status else ""
            _write([line + (f"  ({metrics})" if metrics else "") + (f"  [{note}]" if note else "")])
            return
        lines = [f"--- OUTBOUND RESPONSE #{self.number} ---", f"< {self.status} {self.reason}".rstrip()]
        lines += [f"< {name}: {_redact_header(name, value)}" for name, value in self.headers]
        text = _format_body(body, content_type)
        if self.received > self.captured:
            text += f"\n...more... ({self.received} bytes received, first {self.captured} kept)"
        if text:
            lines += ["<", text]
        if note:
            lines.append(f"< [{note}]")
        if metrics:
            lines.append(f"< [metrics] {metrics}")
        _write(lines)

    def failed(self, error):
        self.done = True
        with _lock:
            _pending.discard(self)
        if _settings["level"] == "summary":
            _write([f"HTTP #{self.number} {self.method} {self.url} -> {type(error).__name__}: {error}"])
        else:
            _write([f"--- OUTBOUND ERROR #{self.number} ---", f"! {type(error).__name__}: {error}"])


def _write(lines):
    logger.info("\n" + "\n".join(lines))


@atexit.register
def _at_exit():
    with _lock:
        pending = list(_pending)
    for call in sorted(pending, key=lambda call: call.number):
        call.finish(note="body not read by the script" if call.status is not None else "no response")
    if _settings["metrics"] and _totals["calls"] and _originals:
        t = _totals
        tokens = f", tokens {t['input_tokens']} in / {t['output_tokens']} out" if t["input_tokens"] else ""
        sizes = f"sent {_size(t['sent'])}, received {_size(t['received'])}"
        _write([f"HTTP totals: {t['calls']} calls, {t['seconds']:.2f} s in calls, {sizes}{tokens}"])


# ---------------------------------------------------------------------------------------------------------------
# requests: wrap HTTPAdapter.send, and tee the raw urllib3 response so the body is logged as it is read.


def _patch_requests():
    try:
        from requests.adapters import HTTPAdapter
    except ImportError:
        return
    if (HTTPAdapter, "send") in _originals:
        return
    original = HTTPAdapter.send

    def send(self, request, **kwargs):
        body = request.body
        if isinstance(body, str):
            body = body.encode()
        elif body is not None and not isinstance(body, bytes):
            body = "<streamed body, not logged>"
        call = _Call(request.method, request.url, request.headers.items(), body, request.headers.get("Content-Type"))
        try:
            response = original(self, request, **kwargs)
        except Exception as error:
            call.failed(error)
            raise
        call.response(response.status_code, response.reason, response.headers.items())
        response.raw = _RawTee(response.raw, call)
        return response

    _originals[(HTTPAdapter, "send")] = original
    HTTPAdapter.send = send


class _RawTee:
    """Stands in for urllib3's HTTPResponse: passes every read through and keeps a copy for the log."""

    def __init__(self, raw, call):
        object.__setattr__(self, "_raw", raw)
        object.__setattr__(self, "_call", call)

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def __setattr__(self, name, value):
        setattr(self._raw, name, value)

    def _keep(self, chunk, decode_content):
        decoded = decode_content if decode_content is not None else getattr(self._raw, "decode_content", True)
        if not decoded:
            self._call.encoding = _header(self._call.headers, "content-encoding")
        self._call.record(chunk)

    def stream(self, amt=2**16, decode_content=None):
        for chunk in self._raw.stream(amt, decode_content=decode_content):
            self._keep(chunk, decode_content)
            yield chunk
        self._call.finish()

    def read(self, amt=None, decode_content=None, **kwargs):
        data = self._raw.read(amt, decode_content=decode_content, **kwargs)
        self._keep(data, decode_content)
        if amt is None or not data:
            self._call.finish()
        return data

    def close(self):
        self._call.finish(note="closed before the body was read" if not self._call.received else None)
        self._raw.close()


# ---------------------------------------------------------------------------------------------------------------
# httpx2 / httpx: wrap the transports, and tee the response stream so the body is logged as it is read.


def _patch_httpx(module_name):
    try:
        module = __import__(module_name)
    except ImportError:
        return
    sync_cls, async_cls = module.HTTPTransport, module.AsyncHTTPTransport
    if (sync_cls, "handle_request") in _originals:
        return
    original_sync, original_async = sync_cls.handle_request, async_cls.handle_async_request

    class SyncTee(module.SyncByteStream):
        def __init__(self, stream, call):
            self.stream, self.call = stream, call

        def __iter__(self):
            for chunk in self.stream:
                self.call.record(chunk)
                yield chunk
            self.call.finish()

        def close(self):
            self.call.finish()
            self.stream.close()

    class AsyncTee(module.AsyncByteStream):
        def __init__(self, stream, call):
            self.stream, self.call = stream, call

        async def __aiter__(self):
            async for chunk in self.stream:
                self.call.record(chunk)
                yield chunk
            self.call.finish()

        async def aclose(self):
            self.call.finish()
            await self.stream.aclose()

    def items(headers):  # names as sent on the wire; multi_items() would lower-case them
        return [(name.decode("latin-1"), value.decode("latin-1")) for name, value in headers.raw]

    def start(request, body):
        return _Call(request.method, request.url, items(request.headers), body, request.headers.get("content-type"))

    def answered(call, response):
        encoding = response.headers.get("content-encoding")
        call.response(response.status_code, response.reason_phrase, items(response.headers), encoding)

    def handle_request(self, request):
        call = start(request, request.read())
        try:
            response = original_sync(self, request)
        except Exception as error:
            call.failed(error)
            raise
        answered(call, response)
        response.stream = SyncTee(response.stream, call)
        return response

    async def handle_async_request(self, request):
        call = start(request, await request.aread())
        try:
            response = await original_async(self, request)
        except Exception as error:
            call.failed(error)
            raise
        answered(call, response)
        response.stream = AsyncTee(response.stream, call)
        return response

    _originals[(sync_cls, "handle_request")] = original_sync
    _originals[(async_cls, "handle_async_request")] = original_async
    sync_cls.handle_request = handle_request
    async_cls.handle_async_request = handle_async_request


# ---------------------------------------------------------------------------------------------------------------
# Formatting and redaction.


def _header(headers, name):
    return next((value for key, value in headers if key.lower() == name), None)


def _redact_header(name, value):
    if name.lower() not in SECRET_HEADERS:
        return value
    scheme, _, rest = value.partition(" ")
    return f"{scheme} {REDACTED}" if rest and name.lower().endswith("authorization") else REDACTED


def _redact_params(query):
    parts = []
    for part in query.split("&"):
        name, sep, _ = part.partition("=")
        parts.append(f"{name}={REDACTED}" if sep and unquote_plus(name).lower() in SECRET_PARAMS else part)
    return "&".join(parts)


def _redact_url(url):
    base, sep, query = url.partition("?")
    return base + sep + _redact_params(query) if sep else url


def _redact_json(value):
    if isinstance(value, dict):
        return {key: REDACTED if key.lower() in SECRET_FIELDS else _redact_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, str) and len(value) > LONG_STRING:
        return f"{value[:80]}...({len(value)} characters)"
    return value


def _decode(data, encoding):
    """Undo gzip/deflate on body bytes that are still compressed (a raw transport stream)."""
    if not data or not encoding:
        return data
    encoding = encoding.lower()
    # decompressobj also handles a body cut at MAX_CAPTURE; deflate is zlib-wrapped or raw, depending on the server.
    window_bits = {"gzip": [16 + zlib.MAX_WBITS], "deflate": [zlib.MAX_WBITS, -zlib.MAX_WBITS]}.get(encoding, [])
    for bits in window_bits:
        try:
            return zlib.decompressobj(bits).decompress(data)
        except zlib.error:
            continue
    return f"<{encoding}-compressed body, {_size(len(data))}>"


def _format_body(body, content_type):
    if not body:
        return ""
    if isinstance(body, str):  # a note such as "<streamed body, not logged>"
        return body
    content_type = (content_type or "").lower()
    if content_type.startswith(BINARY_TYPES):
        return f"<binary body, {_size(len(body))}, {content_type}>"
    if content_type.startswith("multipart/"):
        return f"<multipart body, {_size(len(body))}>"
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return f"<binary body, {_size(len(body))}, {content_type or 'no content type'}>"
    if "json" in content_type or (not content_type and text.lstrip()[:1] in "{["):
        try:
            text = json.dumps(_redact_json(json.loads(text)), indent=2, ensure_ascii=False)
        except ValueError:
            pass
    elif content_type.startswith("application/x-www-form-urlencoded"):
        text = _redact_params(text)
    limit = _settings["max_body"]
    return text if len(text) <= limit else text[:limit] + "...more..."


def _status_field(body, content_type):
    """The top-level "status" of a JSON reply (an agent run's in_progress / completed, for example), or None."""
    if not isinstance(body, bytes) or "json" not in (content_type or "").lower():
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    status = data.get("status") if isinstance(data, dict) else None
    return status if isinstance(status, str) else None


def _usage(body, content_type):
    """(input tokens, output tokens) from a model response's usage block, or None."""
    if not isinstance(body, bytes) or not body:
        return None
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "event-stream" in (content_type or ""):
        candidates = [line[5:].strip() for line in reversed(text.splitlines()) if line.startswith("data:")]
    else:
        candidates = [text]
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        usage = data.get("usage") if isinstance(data, dict) else None
        if not usage and isinstance(data, dict) and isinstance(data.get("response"), dict):
            usage = data["response"].get("usage")  # Responses API stream: the final event carries the response
        if isinstance(usage, dict):
            tokens_in = usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
            tokens_out = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
            return tokens_in, tokens_out
    return None


def _size(count):
    return f"{count} B" if count < 1024 else f"{count / 1024:.1f} KB"


def _metrics_text(seconds, sent, received, usage):
    text = f"{seconds:.2f} s, sent {_size(sent)}, received {_size(received)}"
    return text + (f", tokens {usage[0]} in / {usage[1]} out" if usage else "")
