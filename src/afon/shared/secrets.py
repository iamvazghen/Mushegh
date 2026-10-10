"""Secrets that are not in the repo: Infisical first, `age` as the offline floor.

Why this exists
---------------
`ARCHITECTURE.md` promises the whole brain is debuggable at 3am with `journalctl`, `sqlite3` and
`curl`. That promise does not survive a secrets manager that has to be up before anything else
is: Infisical self-hosted needs its own server and a second database, and
`ARCHITECTURE.md` explicitly lists "no secrets manager and no second database" as things this
system does not have.

So the ordering is deliberate and the floor is real:

1. **Environment wins.** If the operator already exported the variable, nothing overrides it.
2. **Infisical** pulls the rest — through its CLI or the v3 REST API, so no server is required
   in the loop and nothing is vendored.
3. **`age`**-encrypted file as the offline floor. If the network is down and Infisical is
   unreachable, the brain still boots and still has its keys.

The one rule that is not negotiable: **no function here returns, logs, or formats a secret
value.** Everything reports counts and source names. A `SecretReport` can be printed in a log;
a key cannot. `test_secrets_redaction.py` enforces that with negative controls, because a
redaction that is only asserted positively is not a redaction.

Usage
-----
Called once from `config.py` immediately before `Settings()` is constructed, because
pydantic-settings reads the process environment once at instantiation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Protocol

logger = logging.getLogger(__name__)

# Infisical v3 API. Overridable so a self-hosted or on-prem install is one env var away.
DEFAULT_API = "https://secrets.infisical.com/api/v3"

# How long a network call may take before we give up and fall through to `age`.
# Deliberately short: a boot must not hang on a secrets backend. The 2AM rule beats a complete
# key set.
HTTP_TIMEOUT = float(os.getenv("AFON_INFISICAL_TIMEOUT", "5.0"))
CLI_TIMEOUT = float(os.getenv("AFON_INFISICAL_TIMEOUT", "8.0"))


@dataclass
class SecretReport:
    """What happened, in words that are safe to print.

    Carries names and counts only. There is no field here that can hold a secret value, which
    is the point — `repr()` of this object is loggable by construction.
    """

    source: str = "none"
    loaded: int = 0
    names: list[str] = field(default_factory=list)
    skipped_present: int = 0
    failed: bool = False
    detail: str = ""

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return (
            f"SecretReport(source={self.source!r}, loaded={self.loaded}, "
            f"names={self.names!r}, skipped_present={self.skipped_present}, "
            f"failed={self.failed}, detail={self.detail!r})"
        )


class SecretBackend(Protocol):
    """Anything that can hand back a mapping of name -> value."""

    name: str

    def fetch(self) -> dict[str, str]: ...


# --- redaction -------------------------------------------------------------------------

def redact(value: str, keep: int = 2) -> str:
    """`sk-abcdef123456` -> `sk…56`. Used only in diagnostics, never for a live value."""
    if not value:
        return "<empty>"
    if len(value) <= keep * 2:
        return "…" * 1
    return f"{value[:keep]}…{value[-keep:]}"


def is_secret_name(name: str) -> bool:
    """Only treat a variable as a secret if it looks like one.

    Too eager and we start copying `AFON_USER_TZ` out of a secrets manager, which is wrong and
    surprising. Too timid and real keys stay in the repo. This is the middle.
    """
    n = name.upper()
    return any(
        token in n
        for token in (
            "KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "PWD",
            "APIKEY", "API_KEY", "CREDENTIAL", "AUTH", "PAT_", "BEARER",
        )
    )


# --- backends --------------------------------------------------------------------------

class EnvBackend:
    """Already-exported variables. Always safe, always available."""

    name = "env"

    def fetch(self) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if is_secret_name(k) and v}


class AgeBackend:
    """Offline floor. Reads an `age`-decrypted JSON file of name -> value.

    The path is passed IN rather than read from the environment here, for the same reason the
    Infisical token is: config is the only place allowed to read from the environment, and this
    module deliberately does not shell out to `age`, hold a key, or know how the file was
    encrypted. It only reads the result if one exists.
    """

    name = "age"

    def __init__(self, path: Path | str | None = None) -> None:
        self.path: Path | None = Path(path) if path else None

    def fetch(self) -> dict[str, str]:
        if not self.path or not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("age secrets file unreadable: %s", type(exc).__name__)
            return {}
        if not isinstance(raw, dict):
            logger.warning("age secrets file is not an object; ignoring")
            return {}
        return {str(k): str(v) for k, v in raw.items() if v is not None and str(v) != ""}


class InfisicalConfig:
    """Where to reach Infisical — passed IN, never read from the environment here.

    This is deliberate and it is why `config.py` calls the constructor. Decision 36.F5 requires
    config to be the only place that reads a credential out of the environment, so this module
    cannot do it even for its own bootstrap token — a token that unlocks other secrets is still
    a secret. `config.py` is the single reader and hands the values over.
    """

    __slots__ = ("api", "token", "workspace", "project", "env")

    def __init__(
        self,
        api: str = DEFAULT_API,
        token: str = "",
        workspace: str = "",
        project: str = "",
        env: str = "dev",
    ) -> None:
        self.api = (api or DEFAULT_API).rstrip("/")
        self.token = (token or "").strip()
        self.workspace = (workspace or "").strip()
        self.project = (project or "").strip()
        self.env = (env or "dev").strip()


class InfisicalBackend:
    """Infisical over the v3 REST API, or the CLI when there is no token.

    Both paths are supported because they fail differently: the CLI needs the binary on PATH and
    a login session; the API needs a service token. An operator can have either.
    """

    name = "infisical"

    def __init__(self, cfg: InfisicalConfig | None = None) -> None:
        self.cfg = cfg or InfisicalConfig()

    @property
    def configured(self) -> bool:
        if self.cfg.token and self.cfg.workspace and self.cfg.project:
            return True
        return shutil.which("infisical") is not None

    def fetch(self) -> dict[str, str]:
        if self.cfg.token and self.cfg.workspace and self.cfg.project:
            return self._via_api()
        if shutil.which("infisical"):
            return self._via_cli()
        return {}

    def _via_api(self) -> dict[str, str]:
        url = (
            f"{self.cfg.api}/secrets/raw/{self.cfg.workspace}/{self.cfg.project}/{self.cfg.env}"
            "?secretPath=/"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.cfg.token}",
                "Accept": "application/json",
                "User-Agent": "afon",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            # The status code is safe to log; the body might carry project names, and the token
            # is only ever in the header we already failed to send.
            logger.warning("infisical api unavailable: %s", type(exc).__name__)
            return {}
        secrets = (payload or {}).get("secrets") or {}
        return {str(k): str(v) for k, v in secrets.items() if isinstance(v, (str, int, float))}

    def _via_cli(self) -> dict[str, str]:
        exe = shutil.which("infisical")
        if not exe:
            return {}
        args = [exe, "export", "--format=json", "--env", self.cfg.env, "--silent"]
        try:
            proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
                args,
                capture_output=True,
                text=True,
                timeout=CLI_TIMEOUT,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("infisical cli failed: %s", type(exc).__name__)
            return {}
        if proc.returncode != 0:
            logger.warning("infisical cli exit %s", proc.returncode)
            return {}
        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            logger.warning("infisical cli returned non-JSON")
            return {}
        return {str(k): str(v) for k, v in (payload or {}).items() if v is not None}


# --- the hydration step ----------------------------------------------------------------

def hydrate_environment(
    backends: list[SecretBackend] | None = None,
    env: dict[str, str] | None = None,
    infisical: InfisicalConfig | None = None,
    age_path: Path | str | None = None,
) -> SecretReport:
    """Fill `os.environ` from secret backends. Never overrides what is already set.

    Returns a loggable report. Raises nothing: a secrets backend that is down must not be able
    to stop the brain from booting, because a brain that does not boot cannot be diagnosed.
    """
    env = os.environ if env is None else env
    if backends is None:
        backends = [EnvBackend(), InfisicalBackend(infisical), AgeBackend(age_path)]

    report = SecretReport()
    try:
        for backend in backends:
            source = getattr(backend, "name", type(backend).__name__)
            try:
                values = backend.fetch() or {}
            except Exception as exc:  # noqa: BLE001 - a backend must never abort boot
                logger.warning("secret backend %s raised %s", source, type(exc).__name__)
                report.failed = True
                continue

            added: list[str] = []
            for key, value in values.items():
                if not key or value is None or str(value) == "":
                    continue
                if not is_secret_name(key):
                    continue
                if env.get(key):
                    report.skipped_present += 1
                    continue
                env[str(key)] = str(value)
                added.append(str(key))

            if added:
                report.names.extend(added)
                report.loaded += len(added)
                report.source = source
                report.failed = False
            logger.info(
                "secret backend %s contributed %d name(s)", source, len(added)
            )
    except Exception as exc:  # noqa: BLE001 - last line of defence for boot
        logger.error("secret hydration aborted: %s", type(exc).__name__)
        report.failed = True
        return report

    if report.loaded:
        logger.info(
            "hydrated %d secret(s) from %s: %s",
            report.loaded,
            report.source,
            ",".join(sorted(report.names)),
        )
    elif report.skipped_present:
        # Nothing was ADDED because everything was already there. Saying "none" here would read
        # as "no secrets configured" in a status view, which is the opposite of the truth.
        report.source = "environment (already set)"
        logger.info("all %d secret(s) were already present in the environment",
                    report.skipped_present)
    return report


def secret_status(names: Iterable[str]) -> dict[str, str]:
    """Presence-only view, safe for a status endpoint or a spoken reply.

    Returns `"configured"` / `"missing"` per name — never a length, prefix or fragment.
    """
    return {str(n): ("configured" if os.environ.get(str(n)) else "missing") for n in names}