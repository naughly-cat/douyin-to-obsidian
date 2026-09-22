# -*- coding: utf-8 -*-
import ssl
import urllib.error
import urllib.request

import pytest

from douyin_to_obsidian.core import net


@pytest.fixture(autouse=True)
def reset_tls_mode():
    net.configure_tls(allow_insecure=False)
    yield
    net.configure_tls(allow_insecure=False)


def _tls_error():
    return urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))


def test_tls_verification_failure_is_closed_by_default(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=10, context=None):
        calls.append(context)
        raise _tls_error()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(urllib.error.URLError):
        net.urlopen_verified(urllib.request.Request("https://example.com"))

    assert calls == [None]


def test_insecure_tls_retry_requires_explicit_opt_in(monkeypatch):
    calls = []
    sentinel = object()

    def fake_context():
        return sentinel

    def fake_urlopen(req, timeout=10, context=None):
        calls.append(context)
        if context is None:
            raise _tls_error()
        return "ok"

    monkeypatch.setattr(net.ssl, "_create_unverified_context", fake_context)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    net.configure_tls(allow_insecure=True)

    assert net.urlopen_verified(urllib.request.Request("https://example.com")) == "ok"
    assert calls == [None, sentinel]


def test_insecure_mode_does_not_retry_non_tls_errors(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=10, context=None):
        calls.append(context)
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    net.configure_tls(allow_insecure=True)

    with pytest.raises(urllib.error.URLError):
        net.urlopen_verified(urllib.request.Request("https://example.com"))

    assert calls == [None]
