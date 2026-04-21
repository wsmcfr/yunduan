"""公开前端地址推断工具。"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from fastapi import Request


def _extract_first_header_value(raw_value: str | None) -> str:
    """从代理头中提取首个值，避免多级代理拼接影响解析。"""

    if raw_value is None:
        return ""

    return raw_value.split(",")[0].strip()


def _normalize_public_origin(candidate: str | None) -> str | None:
    """把可能带路径的 URL 规整为 `scheme://host` 形式。"""

    normalized_candidate = (candidate or "").strip()
    if not normalized_candidate:
        return None

    parsed_url = urlsplit(normalized_candidate)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return None

    return urlunsplit((parsed_url.scheme, parsed_url.netloc, "", "", ""))


def resolve_public_app_url_from_request(request: Request) -> str | None:
    """根据浏览器请求头推断当前前端站点的公开访问地址。

    优先级说明：
    1. `Origin`：浏览器明确声明的站点来源，最适合作为前端公开地址。
    2. `Referer`：同源 GET 请求通常没有 `Origin`，这里退回到引用页来源。
    3. `X-Forwarded-*`：反向代理部署时优先使用代理提供的外部协议和主机。
    4. `Host`：最后才回退到当前请求主机。
    """

    origin_header = _normalize_public_origin(
        _extract_first_header_value(request.headers.get("origin")),
    )
    if origin_header is not None:
        return origin_header

    referer_header = _normalize_public_origin(request.headers.get("referer"))
    if referer_header is not None:
        return referer_header

    forwarded_host = _extract_first_header_value(request.headers.get("x-forwarded-host"))
    if forwarded_host:
        forwarded_proto = _extract_first_header_value(request.headers.get("x-forwarded-proto"))
        forwarded_scheme = forwarded_proto or request.url.scheme
        forwarded_origin = _normalize_public_origin(f"{forwarded_scheme}://{forwarded_host}")
        if forwarded_origin is not None:
            return forwarded_origin

    host_header = _extract_first_header_value(request.headers.get("host"))
    if host_header:
        return _normalize_public_origin(f"{request.url.scheme}://{host_header}")

    return None
