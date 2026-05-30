#!/usr/bin/env python3
"""Safely download generated image URLs without invoking a shell.

This helper is intentionally small and strict: it accepts only HTTPS URLs that
pass the same generated-image URL validation used by ``image_generation_tool``,
limits the number of bytes read, and writes through a temporary file before an
atomic replace.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, Request, build_opener

from tools.image_generation_tool import _validate_generated_image_url

DEFAULT_MAX_BYTES = 25 * 1024 * 1024
_MAX_REDIRECT_HOPS = 5


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(_NoRedirect())


def _validate_redirect_target(location: str, base_url: str) -> str:
    joined = urljoin(base_url, location)
    return _validate_generated_image_url(joined)


def download_image_url(
    url: str,
    output: str | os.PathLike[str],
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Path:
    """Download ``url`` to ``output`` using validated HTTPS and no shell."""
    current_url = _validate_generated_image_url(url)
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bytes_read = 0
    tmp_name: str | None = None

    try:
        for _hop in range(_MAX_REDIRECT_HOPS + 1):
            request = Request(
                current_url,
                headers={"User-Agent": "Hermes-Roblox safe-image-download"},
            )
            try:
                with _OPENER.open(request, timeout=30) as response:  # noqa: S310 - URL is validated above.
                    content_type = response.headers.get("Content-Type", "").lower()
                    if content_type and not content_type.startswith("image/"):
                        raise ValueError(f"Expected image content, got {content_type!r}")

                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        dir=str(output_path.parent),
                        prefix=f".{output_path.name}.",
                        suffix=".tmp",
                        delete=False,
                    ) as tmp:
                        tmp_name = tmp.name
                        while True:
                            chunk = response.read(1024 * 1024)
                            if not chunk:
                                break
                            bytes_read += len(chunk)
                            if bytes_read > max_bytes:
                                raise ValueError(f"Image exceeds max size of {max_bytes} bytes")
                            tmp.write(chunk)
                    break
            except HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308}:
                    location = exc.headers.get("Location")
                    if not location:
                        raise ValueError("Redirect response missing Location header") from exc
                    current_url = _validate_redirect_target(location, current_url)
                    continue
                raise
        else:
            raise ValueError(f"Too many redirects (>{_MAX_REDIRECT_HOPS})")

        if bytes_read == 0:
            raise ValueError("Downloaded image is empty")
        os.replace(tmp_name, output_path)
        tmp_name = None
        return output_path
    except (OSError, URLError, ValueError) as exc:
        raise RuntimeError(f"Failed to download image: {exc}") from exc
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def _read_url(args: argparse.Namespace) -> str:
    if args.url and args.url_file:
        raise SystemExit("Use either --url or --url-file, not both")
    if args.url_file:
        return Path(args.url_file).read_text(encoding="utf-8").strip()
    if args.url:
        return args.url
    raise SystemExit("One of --url or --url-file is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely download a generated image URL")
    parser.add_argument("--url", help="HTTPS image URL to download")
    parser.add_argument("--url-file", help="File containing the HTTPS image URL")
    parser.add_argument("--output", required=True, help="Absolute or relative output image path")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args(argv)

    path = download_image_url(_read_url(args), args.output, max_bytes=args.max_bytes)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
