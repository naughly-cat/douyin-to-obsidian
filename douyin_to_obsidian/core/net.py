# -*- coding: utf-8 -*-
"""
HTTP 请求工具
==============
默认执行完整 TLS 证书校验并在失败时终止。只有调用方显式启用
不安全模式后，证书错误才会降级重试一次，并显著提示。
"""

import ssl
import urllib.error
import urllib.request


_ALLOW_INSECURE_TLS = False


def configure_tls(allow_insecure: bool = False) -> None:
    """配置当前进程的 TLS 策略；默认严格校验。"""
    global _ALLOW_INSECURE_TLS
    _ALLOW_INSECURE_TLS = bool(allow_insecure)


def _is_tls_error(exc: BaseException) -> bool:
    """判断异常是否由 TLS 证书校验失败引起"""
    reason = getattr(exc, "reason", None)
    return isinstance(reason, ssl.SSLError) or isinstance(exc, ssl.SSLError)


def urlopen_verified(req: urllib.request.Request, timeout: int = 10):
    """
    打开 URL：默认严格校验证书并在失败时终止。只有调用方显式启用
    ``configure_tls(allow_insecure=True)`` 后，证书错误才会降级重试一次。
    """
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.URLError as e:
        if not _is_tls_error(e) or not _ALLOW_INSECURE_TLS:
            raise
        print("[!] 已显式启用不安全 TLS：证书校验失败后将进行一次不校验重试。")
        ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
