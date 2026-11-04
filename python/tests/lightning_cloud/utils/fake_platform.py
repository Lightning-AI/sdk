import base64
import hashlib
import json
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import requests

CLIENT_ID = "lightning-cli"
_LOOPBACK = re.compile(r"http://127\.0\.0\.1:\d+/callback")
_INTERIM_CALLBACK = re.compile(r"http://localhost:\d+/login-complete\?state=[^&]+")
_DAY = 24 * 3600


class _Server(ThreadingHTTPServer):
    # Eight processes connect at once, and the default backlog of 5 resets some.
    request_queue_size = 64
    daemon_threads = True


class FakePlatform:
    """The control plane's login endpoints, both logins, and one API call.

    The new login is the lightning-cli OAuth client. The interim login is the
    sign-in page handing a ``sess_`` token to a localhost callback. Refresh has
    no reuse grace, so any refresh race shows up as a reuse event.
    """

    def __init__(self, access_ttl=3600):
        self.access_ttl = access_ttl
        self.calls = []
        self.requests = []
        self.authorizations = []
        self.sign_ins = []
        self.reuse_events = []
        self.blocked = False
        self.token_keys = {}
        self._codes = {}
        self._families = {}
        self._refresh = {}
        self._access = {}
        self._sessions = {}
        self._lock = threading.Lock()
        self._server = _Server(("127.0.0.1", 0), _handler(self))
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()

    def approve(self, authorize_query, user="user-1"):
        """Click Approve on the consent page: issue a code for that request."""
        code = "code_" + secrets.token_urlsafe(16)
        with self._lock:
            self._codes[code] = {
                "redirect_uri": authorize_query["redirect_uri"],
                "challenge": authorize_query["code_challenge"],
                "user": user,
            }
        return code

    def mint_session(self, user="user-1"):
        """What the sign-in page hands the interim login: a ``sess_`` for ``user``."""
        token = "sess_" + secrets.token_urlsafe(16)
        with self._lock:
            self._sessions[token] = {"user": user, "active": True}
        return token

    def accepts(self, token):
        return self.user_of(token) is not None

    def user_of(self, token):
        """The user ``GET /v1/auth/user`` answers for ``token``, or None for a 401."""
        with self._lock:
            session = self._sessions.get(token)
            if session is not None:
                return session["user"] if session["active"] else None
            if self._access_ok(token):
                return self._access[token]["family"]["user"]
            return None

    def session_active(self, token):
        with self._lock:
            return self._sessions[token]["active"]

    def family_active(self, token):
        with self._lock:
            family = self._family_of(token)
            return family is not None and family["active"]

    def family_storage(self, token):
        with self._lock:
            return self._family_of(token)["storage"]

    def expire_access_tokens(self):
        with self._lock:
            for access in self._access.values():
                access["expires_at"] = 0

    def calls_to(self, path):
        return [form for call_path, form, _ in self.calls if call_path == path]

    def refreshes(self):
        return [form for form in self.calls_to("/oidc/token") if form.get("grant_type") == "refresh_token"]

    def logouts(self):
        """The bearer tokens ``POST /v1/auth/logout`` received."""
        return [
            headers.get("Authorization", "")[len("Bearer ") :]
            for method, path, headers in self.requests
            if (method, path) == ("POST", "/v1/auth/logout")
        ]

    def authorizations_sent(self, path):
        return [headers.get("Authorization") for _, request_path, headers in self.requests if request_path == path]

    def authorize(self, query):
        problems = []
        if query.get("response_type") != "code":
            problems.append("response_type")
        if query.get("client_id") != CLIENT_ID:
            problems.append("client_id")
        redirect = query.get("redirect_uri", "")
        if not (_LOOPBACK.fullmatch(redirect) or redirect == f"{self.url}/cli-login"):
            problems.append("redirect_uri")
        if "openid" not in query.get("scope", "").split():
            problems.append("scope")
        if not query.get("state"):
            problems.append("state")
        if not 43 <= len(query.get("code_challenge", "")) <= 128:
            problems.append("code_challenge")
        if query.get("code_challenge_method") != "S256":
            problems.append("code_challenge_method")
        if not problems:
            self.authorizations.append(query)
        return problems

    def sign_in(self, query, user):
        """The sign-in page: hand a new ``sess_`` to the ``redirectTo`` callback."""
        redirect = query.get("redirectTo", "")
        if not _INTERIM_CALLBACK.fullmatch(redirect):
            return None
        self.sign_ins.append(query)
        callback = urlsplit(redirect)
        params = parse_qs(callback.query)
        params.update({"token": [self.mint_session(user)], "userID": [user], "key": ["key_legacy"]})
        return urlunsplit(callback._replace(query=urlencode(params, doseq=True)))

    def token(self, form):
        if form.get("client_id") != CLIENT_ID:
            return 401, {"error": "invalid_client"}
        with self._lock:
            if form.get("grant_type") == "authorization_code":
                return self._exchange(form)
            if form.get("grant_type") == "refresh_token":
                return self._rotate(form)
        return 400, {"error": "unsupported_grant_type"}

    def revoke(self, form):
        if form.get("client_id") != CLIENT_ID:
            return 401, {"error": "invalid_client"}
        with self._lock:
            family = self._family_of(form.get("token", ""))
            if family is not None:
                family["active"] = False
        return 200, {}

    def logout(self, bearer):
        token = bearer[len("Bearer ") :] if bearer.startswith("Bearer ") else ""
        with self._lock:
            session = self._sessions.get(token)
            if session is None or not session["active"]:
                return 401, {"code": 16, "message": "unauthenticated"}
            session["active"] = False
        return 200, {}

    def token_login(self, body):
        user = self.token_keys.get(body.get("tokenKey"))
        if user is None:
            return 401, {"code": 16, "message": "unauthenticated"}
        return 200, {"token": self.mint_session(user)}

    def _exchange(self, form):
        storage = form.get("storage")
        if storage not in ("keychain", "file"):
            return 400, {"error": "invalid_request", "error_description": "storage"}
        code = self._codes.get(form.get("code", ""))
        if code is None:
            return 400, {"error": "invalid_grant", "error_description": "unknown authorization code"}
        if code["redirect_uri"] != form.get("redirect_uri"):
            return 400, {"error": "invalid_grant", "error_description": "redirect_uri mismatch"}
        verifier = form.get("code_verifier", "").encode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier).digest()).rstrip(b"=").decode()
        if challenge != code["challenge"]:
            return 400, {"error": "invalid_grant", "error_description": "PKCE verification failed"}
        del self._codes[form["code"]]
        family = {"active": True, "storage": storage, "current": None, "user": code["user"]}
        self._families[id(family)] = family
        return 200, self._issue(family)

    def _rotate(self, form):
        presented = form.get("refresh_token", "")
        family = self._family_of(presented)
        if family is None or not family["active"]:
            return 400, {"error": "invalid_grant", "error_description": "invalid refresh token"}
        if presented != family["current"]:
            family["active"] = False
            self.reuse_events.append(presented)
            return 400, {
                "error": "invalid_grant",
                "error_description": "refresh token was reused; the login is revoked",
            }
        if self.blocked:
            return 400, {"error": "access_denied"}
        return 200, self._issue(family)

    def _issue(self, family):
        access = "lit_ua_" + secrets.token_urlsafe(24)
        refresh = "lit_ur_" + secrets.token_urlsafe(24)
        now = time.time()
        family["current"] = refresh
        self._refresh[refresh] = family
        self._access[access] = {"family": family, "expires_at": now + self.access_ttl}
        idle = 7 * _DAY if family["storage"] == "file" else 14 * _DAY
        refresh_expires_at = datetime.fromtimestamp(now + idle, timezone.utc)
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": self.access_ttl,
            "refresh_token": refresh,
            "refresh_expires_at": refresh_expires_at.strftime("%Y-%m-%dT%H:%M:%S.123456789Z"),
            "lightning_grant": {"orgs": "all", "permissions": ["read", "write"]},
        }

    def _family_of(self, token):
        if token in self._refresh:
            return self._refresh[token]
        if token in self._access:
            return self._access[token]["family"]
        return None

    def _access_ok(self, token):
        access = self._access.get(token)
        return access is not None and access["family"]["active"] and time.time() < access["expires_at"]


def _handler(platform):
    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self):  # noqa: N802
            platform.requests.append(("HEAD", urlsplit(self.path).path, dict(self.headers)))
            self.send_response(200)
            self.end_headers()

        def do_GET(self):  # noqa: N802
            parts = urlsplit(self.path)
            platform.requests.append(("GET", parts.path, dict(self.headers)))
            query = {key: values[0] for key, values in parse_qs(parts.query).items()}
            if parts.path == "/oidc/authorize":
                problems = platform.authorize(query)
                if problems:
                    self._json(400, {"error": "invalid_request", "error_description": ",".join(problems)})
                    return
                self.send_response(302)
                self.send_header("Location", f"/cli-login?{parts.query}")
                self.end_headers()
            elif parts.path == "/sign-in":
                landing = platform.sign_in(query, self.headers.get("X-Signed-In-As", "user-1"))
                if landing is None:
                    self._json(400, {"error": "redirectTo"})
                    return
                self.send_response(302)
                self.send_header("Location", landing)
                self.end_headers()
            elif parts.path == "/v1/auth/user":
                bearer = self.headers.get("Authorization", "")
                token = bearer[len("Bearer ") :] if bearer.startswith("Bearer ") else ""
                user = platform.user_of(token)
                if user is not None:
                    self._json(200, {"id": user})
                else:
                    self._json(401, {"code": 16, "message": "unauthenticated"})
            else:
                self._json(404, {})

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode()
            platform.requests.append(("POST", self.path, dict(self.headers)))
            if self.path == "/v1/auth/logout":
                self._json(*platform.logout(self.headers.get("Authorization", "")))
                return
            if self.path == "/v1/auth/token-login":
                self._json(*platform.token_login(json.loads(raw or "{}")))
                return
            form = {key: values[0] for key, values in parse_qs(raw).items()}
            platform.calls.append((self.path, form, self.headers.get("User-Agent")))
            if self.path == "/oidc/token":
                self._json(*platform.token(form))
            elif self.path == "/oidc/revoke":
                self._json(*platform.revoke(form))
            else:
                self._json(404, {})

        def _json(self, status, body):
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    return Handler


class FakeBrowser:
    """Stands in for webbrowser.open, for either login.

    It signs in or approves as ``user`` and follows the redirect to the
    localhost callback. Like a real browser it runs on its own, so the CLI can
    serve the callback.
    """

    def __init__(self, platform, state=None, deny=False, stray_paths=(), user="user-1"):
        self.platform = platform
        self.state = state
        self.deny = deny
        self.stray_paths = stray_paths
        self.user = user
        self.visited = []
        self.stray_statuses = []
        self.landed = None
        self._thread = None

    def open(self, url, *args, **kwargs):
        self._thread = threading.Thread(target=self._visit, args=(url,), daemon=True)
        self._thread.start()
        return True

    def finish(self):
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _visit(self, url):
        self.visited.append(url)
        landing = self._sign_in(url) if urlsplit(url).path == "/sign-in" else self._approve(url)
        self.visited.append(landing)
        response = requests.get(landing, allow_redirects=False, timeout=10)
        self.landed = response.headers.get("Location")

    def _sign_in(self, url):
        page = requests.get(url, headers={"X-Signed-In-As": self.user}, allow_redirects=False, timeout=10)
        assert page.status_code == 302, page.text
        landing = urlsplit(page.headers["Location"])
        self._visit_strays(f"{landing.scheme}://{landing.netloc}")
        if self.state is None:
            return landing.geturl()
        params = parse_qs(landing.query)
        params["state"] = [self.state]
        return urlunsplit(landing._replace(query=urlencode(params, doseq=True)))

    def _approve(self, url):
        consent = requests.get(url, allow_redirects=False, timeout=10)
        assert consent.status_code == 302, consent.text
        query = {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}
        callback = query["redirect_uri"]
        self._visit_strays(callback[: -len("/callback")])
        if self.deny:
            params = {"error": "access_denied", "state": query["state"]}
        else:
            params = {"code": self.platform.approve(query, self.user), "state": self.state or query["state"]}
        return f"{callback}?{urlencode(params)}"

    def _visit_strays(self, origin):
        for path in self.stray_paths:
            self.stray_statuses.append(requests.get(origin + path, timeout=10).status_code)


class SilentBrowser:
    """A browser that opens but never comes back, while the clock runs past the login's wait."""

    def __init__(self, clock, seconds):
        self.clock = clock
        self.seconds = seconds
        self.opened = []

    def open(self, url, *args, **kwargs):
        self.opened.append(url)
        self.clock.advance(self.seconds)
        return True


def raised_within(seconds, call):
    """What ``call`` raised, failing rather than hanging when it is still running after ``seconds``."""
    outcome = []

    def run():
        try:
            call()
        except BaseException as err:
            outcome.append(err)
        else:
            outcome.append(None)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(seconds)
    assert outcome, f"still waiting after {seconds} seconds"
    return outcome[0]


class OtherDevice:
    """Someone approving a paste-back login on another device, then typing codes."""

    def __init__(self, platform, read_terminal, typed):
        self.platform = platform
        self.read_terminal = read_terminal
        self.typed = list(typed)
        self.prompts = 0
        self.code = None

    def getpass(self, prompt=""):
        self.prompts += 1
        if self.code is None:
            url = re.search(r"https?://\S+/oidc/authorize\?\S+", self.read_terminal()).group(0)
            requests.get(url, allow_redirects=False, timeout=10).raise_for_status()
            query = {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}
            self.code = self.platform.approve(query)
        typed = self.typed.pop(0)
        return self.code if typed == "CODE" else typed
