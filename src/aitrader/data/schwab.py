"""Charles Schwab Market Data API — OAuth, quotes, option chains.

POLICY (mandatory — do not relax):
- **Quotes and market data only.** This module may call Schwab Market Data endpoints
  (`/marketdata/v1/*`) plus OAuth token exchange.
- **No trading, ever.** Do not add Accounts & Trading API calls, order placement,
  order modification, cancellation, or any endpoint that moves money or changes
  positions. Agents must not place trades on the user's behalf from this codebase.
- **Recommendation-only.** CSP spread advice uses live quotes for pricing; the user
  executes trades manually in their own broker UI.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

DEFAULT_REDIRECT_URI = "https://127.0.0.1:8182"
DEFAULT_TOKEN_PATH = Path.home() / "data" / "aitrader" / "secrets" / "schwab_tokens.json"
AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
MARKET_DATA_BASE = "https://api.schwabapi.com/marketdata/v1"
ALLOWED_API_PREFIXES = (
    MARKET_DATA_BASE,
    TOKEN_URL,
    AUTH_URL,
)
FORBIDDEN_API_HINTS = ("/trader/", "/accounts/", "/orders", "/order", "/transactions")
SCHWAB_QUOTES_ONLY_POLICY = True


def assert_quotes_only_url(url: str) -> None:
    """Reject any non-market-data or trading-related Schwab URL."""
    lower = url.lower()
    for hint in FORBIDDEN_API_HINTS:
        if hint in lower:
            raise RuntimeError(
                f"Schwab trading API blocked by policy (quotes-only): {url}. "
                "This stack must not place orders or access accounts."
            )
    if not any(lower.startswith(prefix.lower()) for prefix in ALLOWED_API_PREFIXES):
        raise RuntimeError(
            f"Schwab URL not on market-data allowlist: {url}. "
            "Only Market Data + OAuth token endpoints are permitted."
        )


# Schwab index option roots
INDEX_SYMBOLS = {"SPX": "$SPX", "RUT": "$RUT", "SPY": "SPY", "IWM": "IWM"}


@dataclass
class SchwabCredentials:
    app_key: str
    app_secret: str
    redirect_uri: str = DEFAULT_REDIRECT_URI

    @classmethod
    def from_env(cls, *, redirect_uri: str | None = None) -> SchwabCredentials:
        key = os.environ.get("SCHWAB_APP_KEY") or os.environ.get("SCHWAB_CLIENT_ID")
        secret = os.environ.get("SCHWAB_APP_SECRET") or os.environ.get("SCHWAB_CLIENT_SECRET")
        if not key or not secret:
            raise RuntimeError(
                "Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET (or SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET)"
            )
        return cls(
            app_key=key,
            app_secret=secret,
            redirect_uri=redirect_uri or os.environ.get("SCHWAB_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        )


def _basic_auth_header(app_key: str, app_secret: str) -> str:
    raw = f"{app_key}:{app_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _load_token(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _save_token(path: Path, token: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    token["saved_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(token, indent=2))


def _token_request(creds: SchwabCredentials, data: dict[str, str]) -> dict[str, Any]:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": _basic_auth_header(creds.app_key, creds.app_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def exchange_code(creds: SchwabCredentials, code: str) -> dict[str, Any]:
    return _token_request(
        creds,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": creds.redirect_uri,
        },
    )


def refresh_access_token(creds: SchwabCredentials, refresh_token: str) -> dict[str, Any]:
    return _token_request(
        creds,
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
    )


def authorization_url(creds: SchwabCredentials) -> str:
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": creds.app_key,
            "redirect_uri": creds.redirect_uri,
        }
    )
    return f"{AUTH_URL}?{params}"


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code: str | None = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        if code:
            _OAuthCallbackHandler.auth_code = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h2>Schwab auth OK - return to terminal.</h2></body></html>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code")

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_login_flow(
    creds: SchwabCredentials,
    token_path: Path,
    *,
    timeout_sec: float = 300.0,
) -> dict[str, Any]:
    """Browser OAuth on localhost; writes tokens to disk."""
    parsed = urllib.parse.urlparse(creds.redirect_uri)
    if parsed.hostname not in ("127.0.0.1", "localhost"):
        raise ValueError("Redirect URI must use 127.0.0.1 or localhost for local OAuth")
    port = parsed.port or 443
    _OAuthCallbackHandler.auth_code = None

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # Schwab requires https callback — self-signed for loopback only.
    certfile = None
    httpd = HTTPServer((parsed.hostname, port), _OAuthCallbackHandler)
    if creds.redirect_uri.startswith("https"):
        import tempfile

        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID
            import datetime as dt

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(dt.datetime.utcnow())
                .not_valid_after(dt.datetime.utcnow() + dt.timedelta(days=1))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
                .sign(key, hashes.SHA256())
            )
            cert_dir = Path(tempfile.mkdtemp(prefix="schwab_oauth_"))
            cert_pem = cert_dir / "cert.pem"
            key_pem = cert_dir / "key.pem"
            cert_pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_pem.write_bytes(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                )
            )
            httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True, certfile=str(cert_pem), keyfile=str(key_pem))
        except ImportError:
            raise RuntimeError(
                "HTTPS callback requires `cryptography` — pip install cryptography, "
                "or use `auth --manual` with copy-paste flow"
            ) from None

    url = authorization_url(creds)
    print(f"Open this URL in your browser:\n{url}\n")
    webbrowser.open(url)
    thread = Thread(target=httpd.handle_request, daemon=True)
    thread.start()
    deadline = time.time() + timeout_sec
    while _OAuthCallbackHandler.auth_code is None and time.time() < deadline:
        time.sleep(0.2)
    httpd.server_close()
    if not _OAuthCallbackHandler.auth_code:
        raise TimeoutError("OAuth callback timed out — try `auth --manual`")
    token = exchange_code(creds, _OAuthCallbackHandler.auth_code)
    _save_token(token_path, token)
    return token


def run_manual_flow(creds: SchwabCredentials, token_path: Path) -> dict[str, Any]:
    """Copy-paste OAuth for headless / notebook environments."""
    url = authorization_url(creds)
    print("1. Open this URL and sign in:\n")
    print(url)
    print("\n2. After approval, copy the FULL redirect URL from the browser address bar.")
    redirect = input("Paste redirect URL here: ").strip()
    parsed = urllib.parse.urlparse(redirect)
    qs = urllib.parse.parse_qs(parsed.query)
    code = qs.get("code", [None])[0]
    if not code:
        raise ValueError("No authorization code found in redirect URL")
    token = exchange_code(creds, code)
    _save_token(token_path, token)
    print(f"Wrote tokens to {token_path}")
    return token


class SchwabClient:
    """Thin Market Data client with automatic token refresh."""

    def __init__(self, creds: SchwabCredentials, token_path: Path) -> None:
        self.creds = creds
        self.token_path = token_path
        self._token = _load_token(token_path)

    def _ensure_access(self) -> str:
        expires_in = int(self._token.get("expires_in", 0))
        saved = self._token.get("saved_at")
        stale = True
        if saved and expires_in:
            saved_dt = datetime.fromisoformat(saved.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - saved_dt).total_seconds()
            stale = age > max(expires_in - 60, 0)
        if stale and self._token.get("refresh_token"):
            self._token = refresh_access_token(self.creds, self._token["refresh_token"])
            _save_token(self.token_path, self._token)
        access = self._token.get("access_token")
        if not access:
            raise RuntimeError("No access_token — run `aitrader data schwab auth`")
        return access

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        access = self._ensure_access()
        query = ""
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            query = "?" + urllib.parse.urlencode(clean)
        url = f"{MARKET_DATA_BASE}{path}{query}"
        assert_quotes_only_url(url)
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {access}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode() if exc.fp else ""
            raise RuntimeError(f"Schwab API {exc.code}: {body}") from exc

    def quote(self, symbol: str) -> dict[str, Any]:
        sym = INDEX_SYMBOLS.get(symbol.upper(), symbol)
        return self._get("/quotes", {"symbols": sym})

    def option_chain(
        self,
        symbol: str,
        *,
        contract_type: str = "PUT",
        from_date: date | None = None,
        to_date: date | None = None,
        strike_count: int | None = 50,
        strategy: str | None = None,
        interval: float | None = None,
        underlying_price: float | None = None,
        volatility: float | None = None,
        days_to_expiration: int | None = None,
        include_quotes: bool = True,
        strike_range: str | None = None,
        strike: float | None = None,
    ) -> dict[str, Any]:
        sym = INDEX_SYMBOLS.get(symbol.upper(), symbol)
        params: dict[str, Any] = {
            "symbol": sym,
            "contractType": contract_type,
            "includeUnderlyingQuote": str(include_quotes).lower(),
        }
        if strike_count is not None:
            params["strikeCount"] = strike_count
        if strike_range:
            params["range"] = strike_range
        if strike is not None:
            params["strike"] = strike
        if strategy:
            params["strategy"] = strategy
        if interval is not None:
            params["interval"] = interval
        if from_date:
            params["fromDate"] = from_date.isoformat()
        if to_date:
            params["toDate"] = to_date.isoformat()
        if underlying_price is not None:
            params["underlyingPrice"] = underlying_price
        if volatility is not None:
            params["volatility"] = volatility
        if days_to_expiration is not None:
            params["daysToExpiration"] = days_to_expiration
        return self._get("/chains", params)

    @classmethod
    def from_token_path(
        cls,
        token_path: Path | str | None = None,
        *,
        redirect_uri: str | None = None,
    ) -> SchwabClient:
        creds = SchwabCredentials.from_env(redirect_uri=redirect_uri)
        path = Path(token_path) if token_path else DEFAULT_TOKEN_PATH
        if not path.exists():
            raise FileNotFoundError(f"No token at {path} — run `aitrader data schwab auth` first")
        return cls(creds, path)


def resolve_schwab_symbol(index: str) -> str:
    return INDEX_SYMBOLS.get(index.upper(), index)


def _cmd_auth(args: argparse.Namespace) -> None:
    creds = SchwabCredentials.from_env(redirect_uri=args.redirect_uri)
    token_path = Path(args.token_path)
    if args.manual:
        run_manual_flow(creds, token_path)
    else:
        run_login_flow(creds, token_path)
        print(f"Wrote tokens to {token_path}")


def _cmd_quote(args: argparse.Namespace) -> None:
    client = SchwabClient.from_token_path(args.token_path, redirect_uri=args.redirect_uri)
    data = client.quote(args.symbol)
    print(json.dumps(data, indent=2))


def _cmd_chain(args: argparse.Namespace) -> None:
    client = SchwabClient.from_token_path(args.token_path, redirect_uri=args.redirect_uri)
    fd = date.fromisoformat(args.from_date) if args.from_date else None
    td = date.fromisoformat(args.to_date) if args.to_date else None
    data = client.option_chain(
        args.symbol,
        contract_type=args.contract_type,
        from_date=fd,
        to_date=td,
        strike_count=args.strike_count,
        strategy=args.strategy,
        underlying_price=args.underlying_price,
        volatility=args.volatility,
        days_to_expiration=args.days_to_expiration,
    )
    print(json.dumps(data, indent=2)[:8000])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Schwab Market Data connector")
    sub = parser.add_subparsers(dest="cmd", required=True)

    auth_p = sub.add_parser("auth", help="OAuth login — writes refresh token")
    auth_p.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI)
    auth_p.add_argument("--token-path", default=str(DEFAULT_TOKEN_PATH))
    auth_p.add_argument("--manual", action="store_true", help="Copy-paste redirect URL flow")
    auth_p.set_defaults(func=_cmd_auth)

    quote_p = sub.add_parser("quote", help="Fetch quote for symbol")
    quote_p.add_argument("--symbol", default="SPY")
    quote_p.add_argument("--redirect-uri", default=None)
    quote_p.add_argument("--token-path", default=str(DEFAULT_TOKEN_PATH))
    quote_p.set_defaults(func=_cmd_quote)

    chain_p = sub.add_parser("chain", help="Fetch option chain")
    chain_p.add_argument("--symbol", default="SPX")
    chain_p.add_argument("--contract-type", default="PUT")
    chain_p.add_argument("--from-date", default=None)
    chain_p.add_argument("--to-date", default=None)
    chain_p.add_argument("--strike-count", type=int, default=30)
    chain_p.add_argument("--strategy", default=None)
    chain_p.add_argument("--underlying-price", type=float, default=None)
    chain_p.add_argument("--volatility", type=float, default=None)
    chain_p.add_argument("--days-to-expiration", type=int, default=None)
    chain_p.add_argument("--redirect-uri", default=None)
    chain_p.add_argument("--token-path", default=str(DEFAULT_TOKEN_PATH))
    chain_p.set_defaults(func=_cmd_chain)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
