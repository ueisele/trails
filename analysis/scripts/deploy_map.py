"""Publish a built map to the bucket it is served from, and purge what the edge still holds.

The bucket, the hostname and the rules that turn one into the other are **not** created here. They
are an OpenTofu module in a separate, private repository, and this script only puts an object where
that module already expects to find it. Running ``just deploy-env`` there prints every value this
needs, in the order below.

**Nothing about the account is written down in this repository, because it is public.** Bucket,
endpoint, hostname and zone all arrive through the environment — ``.env.example`` names them and
``.env`` is git-ignored. A default for any of them here would publish an account identifier to
anyone who clones this.

A map named ``<name>`` is uploaded as ``<name>.html`` and is then readable at
``https://<host>/<name>``: a rewrite rule adds the suffix back. The object keeps the extension
because every upload tool derives ``Content-Type`` from it, and an object served as
``application/octet-stream`` makes the browser download the map instead of opening it.

Two things this deliberately does rather than assumes:

* **It refuses a file that does not begin like the built map.** An interrupted build leaves a
  truncated file behind, and a truncated 40 MB upload looks exactly like a successful one.
* **It prints the API's own error body on a failed purge.** Cloudflare answers a missing token
  permission with ``403 request is not authorized`` and names neither the permission nor the token,
  which reads like a broken credential rather than one that is short by a single entry.

Usage::

    command make deploy
    command make deploy ARGS="--dry-run"
    command make deploy ARGS="--map oberstdorf-allgaeu"
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

#: What the object is served as. Without it R2 answers with the S3 default and the map downloads.
CONTENT_TYPE = "text/html; charset=utf-8"

#: The suffix the object carries and the URL does not. It has to agree with ``var.map_suffix`` in
#: the OpenTofu module; the module's ``key_suffix`` output is where that value is decided.
KEY_SUFFIX = ".html"

#: How a built map begins. Checked before uploading — see the module docstring.
EXPECTED_PREFIX = b"<!DOCTYPE html>"

#: aws-cli 2.23 and newer send checksum headers R2 rejects. The same reason the OpenTofu backend
#: in the infrastructure repo sets ``skip_s3_checksum = true``.
CHECKSUM_ENV = {"AWS_REQUEST_CHECKSUM_CALCULATION": "when_required"}

#: Read from the environment. The first four say where to put the map, the last three how.
SETTINGS = (
    "TRAILS_MAP_BUCKET",
    "TRAILS_MAP_S3_ENDPOINT",
    "TRAILS_MAP_HOSTNAME",
    "TRAILS_MAP_ZONE_ID",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "CLOUDFLARE_API_TOKEN",
)


def load_env_file(path: Path) -> None:
    """Read ``KEY=value`` lines into the environment, leaving anything already set alone.

    Args:
        path: File to read. Missing is not an error — the values may come from the shell instead.
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        # The shell wins over the file, so a one-off `VAR=... make deploy` works without editing.
        if key and key not in os.environ:
            os.environ[key] = value


def settings(names: tuple[str, ...]) -> dict[str, str]:
    """Collect the named environment variables, naming every one that is missing.

    Args:
        names: Variables to read.

    Returns:
        The variables and their values.

    Raises:
        SystemExit: If any is unset. All of them are reported at once rather than one per run.
    """
    found = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in found.items() if not value]
    if missing:
        sys.exit("Not set: " + ", ".join(missing) + "\nSee .env.example, and `just deploy-env` in the infrastructure repo for the values.")
    return found


def check(source: Path) -> int:
    """Refuse anything that is not a built map.

    Args:
        source: The file about to be uploaded.

    Returns:
        Its size in bytes.

    Raises:
        SystemExit: If it is missing, empty, or does not start like the built page.
    """
    if not source.exists():
        sys.exit(f"{source} does not exist — run `command make map` first.")
    size = source.stat().st_size
    if size == 0:
        sys.exit(f"{source} is empty.")
    with source.open("rb") as handle:
        if not handle.read(len(EXPECTED_PREFIX)).startswith(EXPECTED_PREFIX):
            sys.exit(f"{source} does not begin with {EXPECTED_PREFIX.decode()} — build interrupted?")
    return size


def squeezed(source: Path) -> tuple[Path, int]:
    """Compress the map once, properly, so the reader does not wait for the edge to do it badly.

    **Measured on the published map**, which is 41.8 MB of HTML: Cloudflare
    compresses on the fly and its brotli came out at **7.84 MB**, which is
    *worse* than its own gzip at 7.57 -- a low quality level, chosen for the
    server's time rather than the reader's. The same bytes at brotli 11 are
    **6.58 MB**. On a 1.5 Mbit/s connection that difference is about seven
    seconds, spent before anything at all is on the screen.

    The object is then stored compressed and served with ``Content-Encoding:
    br``, which every browser since 2017 understands over HTTPS. A client that
    does not is handed brotli it cannot read -- that is the standing trade of
    pre-compressed static hosting, and it is the reason this is said out loud
    rather than done quietly.

    Args:
        source: The built map.

    Returns:
        The compressed file, and how many bytes it holds.
    """
    import brotli

    squeezed_file = source.with_suffix(source.suffix + ".br")
    squeezed_file.write_bytes(brotli.compress(source.read_bytes(), quality=11))
    return squeezed_file, squeezed_file.stat().st_size


def upload(source: Path, key: str, config: dict[str, str]) -> None:
    """Copy the map into the bucket with the content type that makes it open rather than download.

    Args:
        source: The compressed map, from :func:`squeezed`.
        key: Object key to write.
        config: The settings from :func:`settings`.

    Raises:
        SystemExit: If the aws CLI is absent or the copy fails.
    """
    command = [
        "aws", "s3", "cp", str(source), f"s3://{config['TRAILS_MAP_BUCKET']}/{key}",
        "--endpoint-url", config["TRAILS_MAP_S3_ENDPOINT"],
        "--region", "auto",
        "--content-type", CONTENT_TYPE,
        "--content-encoding", "br",
        "--no-progress",
    ]  # fmt: skip
    try:
        subprocess.run(command, check=True, env={**os.environ, **CHECKSUM_ENV})
    except FileNotFoundError:
        sys.exit("aws (the AWS CLI) is not installed — it is what talks to R2's S3 API.")
    except subprocess.CalledProcessError as error:
        sys.exit(f"Upload failed (exit {error.returncode}).")


def purge(urls: list[str], config: dict[str, str]) -> None:
    """Drop the map from Cloudflare's edge cache.

    Args:
        urls: Every address the object is reachable at.
        config: The settings from :func:`settings`.

    Raises:
        SystemExit: If the API refuses. Its own message is printed — a missing token permission
            answers 403 and says nothing about which permission.
    """
    request = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/zones/{config['TRAILS_MAP_ZONE_ID']}/purge_cache",
        data=json.dumps({"files": urls}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['CLOUDFLARE_API_TOKEN']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            answered = json.load(response)
    except urllib.error.HTTPError as error:
        sys.exit(
            f"Purge refused with {error.code}: {error.read().decode('utf-8', 'replace')}\n"
            "A 403 here is usually the token missing Zone -> Cache Purge -> Purge."
        )
    except urllib.error.URLError as error:
        sys.exit(f"Purge could not be sent: {error.reason}")
    if not answered.get("success"):
        sys.exit(f"Purge reported failure: {json.dumps(answered.get('errors'), ensure_ascii=False)}")


def main() -> None:
    """Upload one built map and purge the addresses it is served at."""
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", default="lomsdal-visten", help="Map name, without the suffix")
    parser.add_argument(
        "--output-dir",
        default=str(repo_root / "analysis" / "output"),
        help="Directory the built map is read from",
    )
    parser.add_argument("--no-purge", action="store_true", help="Upload without purging the edge")
    parser.add_argument("--dry-run", action="store_true", help="Say what would happen and change nothing")
    parser.add_argument(
        "--env-file",
        default=str(repo_root / ".env"),
        help="File to read settings from before the environment",
    )
    args = parser.parse_args()

    load_env_file(Path(args.env_file))
    config = settings(SETTINGS)

    key = f"{args.map}{KEY_SUFFIX}"
    source = Path(args.output_dir) / key
    size = check(source)
    host = config["TRAILS_MAP_HOSTNAME"]

    # Every address the same object answers at, because each is its own cache entry: the clean one
    # the rewrite rule serves, the one a trailing slash produces, and the object's own name.
    urls = [f"https://{host}/{args.map}", f"https://{host}/{args.map}/", f"https://{host}/{key}"]

    if args.dry_run:
        print(f"Would compress {source} ({size / 1e6:.1f} MB) at brotli 11")
        print(f"      upload it to s3://{config['TRAILS_MAP_BUCKET']}/{key} as {CONTENT_TYPE}, Content-Encoding: br")
        print("      purge " + ("nothing (--no-purge)" if args.no_purge else ", ".join(urls)))
        return

    body, packed = squeezed(source)
    print(f"🗜️  {source.name}: {size / 1e6:.1f} → {packed / 1e6:.2f} MB at brotli 11 (the edge managed 7.84)")
    print(f"⬆️  → s3://{config['TRAILS_MAP_BUCKET']}/{key}, Content-Encoding: br")
    upload(body, key, config)

    if args.no_purge:
        print("↩️  Edge cache left alone (--no-purge); it holds the old map for up to 5 minutes.")
    else:
        purge(urls, config)
        print("🧹 Edge cache purged")

    print(f"✅ https://{host}/{args.map}")


if __name__ == "__main__":
    main()
