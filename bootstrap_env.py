"""
Load before `utils` and Google SDK imports: `.env` + CA bundle defaults.
Imported from app.py (first) and utils/ai_resume_analyzer.py (when tests/tools skip app).
"""
from __future__ import annotations

import os
from pathlib import Path

_done = False


def _bootstrap() -> None:
    global _done
    if _done:
        return
    _done = True

    root = Path(__file__).resolve().parent
    utils_dir = root / "utils"
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env")
        load_dotenv(utils_dir / ".env", override=True)
        load_dotenv()
    except Exception:
        pass

    if os.environ.get("HIRERESUME_SKIP_CA_BUNDLE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return

    # Prefer OS trust store (Windows CryptoAPI, etc.) so corporate / AV TLS roots work.
    # Certifi alone often fails with HTTPSConnectionPool ... unable to get local issuer.
    certifi_only = os.environ.get("HIRERESUME_USE_CERTIFI_ONLY", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not certifi_only:
        try:
            import truststore

            truststore.inject_into_ssl()
            try:
                import certifi

                ca = certifi.where()
                if not str(os.environ.get("GRPC_DEFAULT_SSL_ROOTS_FILE_PATH") or "").strip():
                    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = ca
            except ImportError:
                pass
            return
        except ImportError:
            pass
        except Exception:
            pass

    try:
        import certifi
    except ImportError:
        return
    ca = certifi.where()
    for key in (
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "GRPC_DEFAULT_SSL_ROOTS_FILE_PATH",
    ):
        cur = os.environ.get(key)
        if cur is None or not str(cur).strip():
            os.environ[key] = ca

    # Resolve a single PEM path: .env may point at a missing file.
    cafile = str(os.environ.get("SSL_CERT_FILE", "")).strip()
    if not cafile or not os.path.isfile(cafile):
        cafile = ca
        os.environ["SSL_CERT_FILE"] = cafile
        os.environ["REQUESTS_CA_BUNDLE"] = cafile

    # urllib3 / http.client: force certifi when truststore is unavailable.
    try:
        import ssl
    except ImportError:
        return

    def _default_https_context():
        return ssl.create_default_context(cafile=cafile)

    ssl._create_default_https_context = _default_https_context  # type: ignore[assignment]


_bootstrap()
