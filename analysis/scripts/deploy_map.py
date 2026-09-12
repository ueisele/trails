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

**Tile trees go up by ``sync``, not by ``cp``.** The base-map tiles and the height tiles are
directories of a hundred thousand small PNGs (118,967 for Abisko, 696 MB) whose addresses carry a
version segment — ``tiles/lantmateriet/topowebb/1/{z}/{x}/{y}.png`` — so an object never changes
under its name and can be held for a year, and a second run has to upload only what is new. ``aws
s3 sync`` compares size and modification time against the bucket's listing and skips the rest;
nothing is ever deleted, and nothing is purged, because a versioned address has nothing stale to
purge. The tree's ``index.json`` is the one file in it that does change, so it goes up on its own
with a short lifetime.

Usage::

    command make deploy
    command make deploy ARGS="--dry-run"
    command make deploy ARGS="--map oberstdorf-allgaeu"
    command make deploy ARGS="--tree tiles"                 # the tile tree alone, no page
    command make deploy ARGS="--map abisko --tree dem"      # a page and a tree in one run

With ``--tree`` alone only the trees go up; name ``--map`` as well to publish a page in the same
run. A ``--dry-run`` with ``--tree`` does list the bucket, because what it reports is what
``sync`` would find missing there.
"""

import argparse
import json
import os
import subprocess
import sys
import time
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

#: Read from the environment: where the objects go and what may write them. Every run needs these.
SETTINGS = (
    "TRAILS_MAP_BUCKET",
    "TRAILS_MAP_S3_ENDPOINT",
    "TRAILS_MAP_HOSTNAME",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
)

#: What the purge needs on top. Only a page is purged, so a run without one -- or with
#: ``--no-purge`` -- does not ask for them, which is what ``.env.example`` promises.
PURGE_SETTINGS = (
    "TRAILS_MAP_ZONE_ID",
    "CLOUDFLARE_API_TOKEN",
)

#: The directory trees under ``analysis/output`` that are mirrored into the bucket under the same
#: prefix, and what each is. Both hold versioned addresses -- a ``/1/`` segment below the provider
#: -- so every object in them is immutable and an edge may keep it for a year. A new version is a
#: new prefix, never a changed object.
TREES = {
    "tiles": "the base-map tiles, tiles/<provider>/<sheet>/<version>/{z}/{x}/{y}.png",
    "dem": "the height tiles, dem/<provider>/<version>/{z}/{x}/{y}.png",
}

#: How long an edge may hold an object of a tree. A year is the ceiling browsers honour.
TREE_CACHE_CONTROL = "public, max-age=31536000, immutable"

#: The copy's inventory, written beside the tiles. It is the one file in a tree that changes -- a
#: resumed copy rewrites it -- so it goes up on its own with the same short lifetime as the manifest.
TREE_INDEX = "index.json"

#: How often the sync reports progress, in uploaded objects. A tree is a hundred thousand of them
#: and a line per object is a journal nobody reads.
PROGRESS_EVERY = 5_000


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


#: The small objects that ride beside the map, with what each is and how long an
#: edge may hold it. All uncompressed: they are kilobytes, so compressing them
#: saves nothing worth a decompression — and a PNG is already compressed.
BESIDE = {
    # The one object whose whole job is to be noticed when it changes -- an edge
    # holding yesterday's worker would hold yesterday's map with it, for as long
    # as the header said to.
    "sw.js": ("text/javascript; charset=utf-8", "no-cache"),
    # What makes the map installable, and an installed map is what survives
    # WebKit's seven-day sweep of storage a script created. It changes only when
    # the map is renamed, so an edge may hold it as long as it holds the page.
    "manifest.webmanifest": ("application/manifest+json", "max-age=300"),
    # **The mark, as four files rather than as a data: URI inside the page.**
    # iOS reads `apple-touch-icon` off the document and will not fetch a data:
    # URI for it, so an inline mark is a link that resolves to nothing and the
    # home screen shows a screenshot of the map instead. 180 is the one iOS
    # takes; 32 is the tab; 192 and 512 are what the manifest offers a launcher.
    # Held as briefly as the manifest: the name never changes, so a redesign
    # would otherwise sit behind a long TTL with nothing to purge it.
    "icon-32.png": ("image/png", "max-age=300"),
    "icon-180.png": ("image/png", "max-age=300"),
    "icon-192.png": ("image/png", "max-age=300"),
    "icon-512.png": ("image/png", "max-age=300"),
}


def upload_beside(source: Path, config: dict[str, str]) -> None:
    """Copy one of the map's small companions up, uncompressed.

    Args:
        source: The file, written beside the map by the build. Its name decides
            its content type and cache header, from :data:`BESIDE`.
        config: The settings from :func:`settings`.

    Raises:
        SystemExit: If the aws CLI is absent or the copy fails.
    """
    content_type, cache_control = BESIDE[source.name]
    command = [
        "aws", "s3", "cp", str(source), f"s3://{config['TRAILS_MAP_BUCKET']}/{source.name}",
        "--endpoint-url", config["TRAILS_MAP_S3_ENDPOINT"],
        "--region", "auto",
        "--content-type", content_type,
        "--cache-control", cache_control,
        "--no-progress",
    ]  # fmt: skip
    try:
        subprocess.run(command, check=True, env={**os.environ, **CHECKSUM_ENV})
    except FileNotFoundError:
        sys.exit("aws (the AWS CLI) is not installed — it is what talks to R2's S3 API.")
    except subprocess.CalledProcessError as error:
        sys.exit(f"Uploading {source.name} failed (exit {error.returncode}).")


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


def _aws(config: dict[str, str]) -> list[str]:
    """The start of every aws call: the S3 subcommand's endpoint and region."""
    return ["aws", "s3", "--endpoint-url", config["TRAILS_MAP_S3_ENDPOINT"], "--region", "auto"]


def sync_tree(source: Path, prefix: str, config: dict[str, str], dry_run: bool = False) -> tuple[int, int]:
    """Mirror a directory tree into the bucket, uploading only what is not there yet.

    ``aws s3 sync`` lists the prefix and uploads a file whose size differs from the object's or
    whose modification time is newer; a tile copied before the last upload is skipped. Partial
    files the copy left behind are excluded, and so is the inventory, which :func:`upload_index`
    puts up separately. Nothing is deleted: a tree only ever grows. The exclude patterns are
    matched against the path below ``source``, and ``*`` crosses slashes there -- measured: a bare
    ``index.json`` excluded nothing, ``*/index.json`` excludes the one file.

    Args:
        source: The tree on disk.
        prefix: Where it goes, relative to the bucket root -- the tree's own name.
        config: The settings from :func:`settings`.
        dry_run: Ask ``sync`` what it would upload and upload nothing. The listing still happens.

    Returns:
        How many objects were uploaded (or would be) and how many bytes they hold.

    Raises:
        SystemExit: If the aws CLI is absent or the sync fails.
    """
    command = [
        *_aws(config), "sync", str(source), f"s3://{config['TRAILS_MAP_BUCKET']}/{prefix}",
        "--exclude", "*.part",
        "--exclude", f"*/{TREE_INDEX}",
        "--cache-control", TREE_CACHE_CONTROL,
        "--no-progress",
    ]  # fmt: skip
    if dry_run:
        command.append("--dryrun")
    started = time.time()
    uploaded = 0
    size = 0
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, text=True, env={**os.environ, **CHECKSUM_ENV})
    except FileNotFoundError:
        sys.exit("aws (the AWS CLI) is not installed — it is what talks to R2's S3 API.")
    assert process.stdout is not None
    # One line per object -- "upload: <local> to s3://<bucket>/<key>", "(dryrun) " in front when
    # asked -- and nothing else with --no-progress. The local path is what says how big it was.
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        verb, _, rest = line.removeprefix("(dryrun) ").partition(": ")
        if verb != "upload":
            print(f"   {line}")
            continue
        local, _, _target = rest.rpartition(" to s3://")
        uploaded += 1
        try:
            size += Path(local).stat().st_size
        except OSError:
            pass
        if uploaded % PROGRESS_EVERY == 0:
            elapsed = time.time() - started
            print(f"   {uploaded:,} objects, {size / 1e6:,.1f} MB, {elapsed:,.0f} s, {uploaded / elapsed:,.0f}/s", flush=True)
    if process.wait() != 0:
        sys.exit(f"Syncing {source} failed (exit {process.returncode}).")
    return uploaded, size


def upload_index(source: Path, prefix: str, config: dict[str, str]) -> None:
    """Put a tree's inventory up beside its tiles, held only briefly.

    Args:
        source: The ``index.json`` the copy wrote.
        prefix: The tree's prefix in the bucket.
        config: The settings from :func:`settings`.

    Raises:
        SystemExit: If the copy fails.
    """
    command = [
        *_aws(config), "cp", str(source), f"s3://{config['TRAILS_MAP_BUCKET']}/{prefix}/{source.name}",
        "--content-type", "application/json",
        "--cache-control", "max-age=300",
        "--no-progress",
    ]  # fmt: skip
    try:
        subprocess.run(command, check=True, env={**os.environ, **CHECKSUM_ENV})
    except subprocess.CalledProcessError as error:
        sys.exit(f"Uploading {prefix}/{source.name} failed (exit {error.returncode}).")


def check_tree(root: Path, name: str) -> tuple[list[Path], int]:
    """Refuse a tree that is not there or holds nothing to upload.

    Args:
        root: The directory to mirror.
        name: Its key in :data:`TREES`, for the message.

    Returns:
        The inventories found below it -- one per copied version -- and how many files it holds
        apart from them.

    Raises:
        SystemExit: If it is missing or empty.
    """
    if not root.is_dir():
        sys.exit(f"{root} is not a directory — {TREES[name]} — nothing has built it yet.")
    files = 0
    indexes: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name == TREE_INDEX:
            indexes.append(path)
        elif path.suffix != ".part":
            files += 1
    if files == 0:
        sys.exit(f"{root} is empty.")
    return sorted(indexes), files


def publish_trees(names: list[str], output_dir: Path, config: dict[str, str], dry_run: bool) -> None:
    """Sync every named tree, then its inventories.

    Args:
        names: Keys of :data:`TREES`.
        output_dir: Where the trees are, one directory each.
        config: The settings from :func:`settings`.
        dry_run: Report what ``sync`` would do and change nothing.
    """
    bucket = config["TRAILS_MAP_BUCKET"]
    for name in names:
        root = output_dir / name
        indexes, files = check_tree(root, name)
        verb = "Would sync" if dry_run else "Syncing"
        print(f"🔁 {verb} {root} ({files:,} files) → s3://{bucket}/{name}/, {TREE_CACHE_CONTROL}", flush=True)
        started = time.time()
        uploaded, size = sync_tree(root, name, config, dry_run)
        elapsed = time.time() - started
        done = "would upload" if dry_run else "uploaded"
        print(f"   {done} {uploaded:,} of {files:,} objects, {size / 1e6:,.1f} MB, in {elapsed:,.0f} s")
        for index in indexes:
            prefix = f"{name}/{index.parent.relative_to(root).as_posix()}"
            if dry_run:
                print(f"   would upload {prefix}/{index.name}, max-age=300")
            else:
                print(f"⬆️  {prefix}/{index.name} → s3://{bucket}/{prefix}/{index.name}, max-age=300")
                upload_index(index, prefix, config)


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
    """Upload the trees named, then the page and its companions, then purge the page's addresses."""
    repo_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--map",
        default=None,
        help="Map name, without the suffix. Default lomsdal-visten; with --tree, no page unless named",
    )
    parser.add_argument(
        "--tree",
        action="append",
        default=[],
        choices=sorted(TREES),
        help="Mirror this tree from the output directory into the bucket; may be repeated",
    )
    parser.add_argument(
        "--output-dir",
        default=str(repo_root / "analysis" / "output"),
        help="Directory the built map and the trees are read from",
    )
    parser.add_argument("--no-purge", action="store_true", help="Upload without purging the edge")
    parser.add_argument("--dry-run", action="store_true", help="Say what would happen and change nothing")
    parser.add_argument(
        "--env-file",
        default=str(repo_root / ".env"),
        help="File to read settings from before the environment",
    )
    args = parser.parse_args()

    trees = list(dict.fromkeys(args.tree))
    name = args.map if args.map is not None else (None if trees else "lomsdal-visten")
    purging = name is not None and not args.no_purge

    load_env_file(Path(args.env_file))
    config = settings(SETTINGS + PURGE_SETTINGS if purging else SETTINGS)
    output_dir = Path(args.output_dir)
    host = config["TRAILS_MAP_HOSTNAME"]

    # The trees go up first: a page that names tiles which are not there yet would draw white ground
    # for as long as its worker held the misses.
    if trees:
        publish_trees(trees, output_dir, config, args.dry_run)
    if name is None:
        print("✅ " + ", ".join(f"https://{host}/{tree}/" for tree in trees))
        return

    key = f"{name}{KEY_SUFFIX}"
    source = output_dir / key
    size = check(source)

    # Every address the same object answers at, because each is its own cache entry: the clean one
    # the rewrite rule serves, the one a trailing slash produces, and the object's own name.
    urls = [f"https://{host}/{name}", f"https://{host}/{name}/", f"https://{host}/{key}"]
    urls += [f"https://{host}/{beside}" for beside in BESIDE]

    if args.dry_run:
        print(f"Would compress {source} ({size / 1e6:.1f} MB) at brotli 11")
        for beside, (kind, held) in BESIDE.items():
            print(f"      upload {beside} uncompressed, {kind}, {held}")
        print(f"      upload it to s3://{config['TRAILS_MAP_BUCKET']}/{key} as {CONTENT_TYPE}, Content-Encoding: br")
        print("      purge " + ("nothing (--no-purge)" if args.no_purge else ", ".join(urls)))
        return

    body, packed = squeezed(source)
    print(f"🗜️  {source.name}: {size / 1e6:.1f} → {packed / 1e6:.2f} MB at brotli 11 (the edge managed 7.84)")
    print(f"⬆️  → s3://{config['TRAILS_MAP_BUCKET']}/{key}, Content-Encoding: br")
    upload(body, key, config)

    # **The worker goes up after the map and never before it.** It is what makes
    # a reader's next visit serve the copy they already have, so a worker that
    # arrived first would hand out the old map while announcing the new one.
    for companion_name, (_kind, held) in BESIDE.items():
        companion = source.with_name(companion_name)
        if companion.exists():
            weight = companion.stat().st_size / 1e3
            print(f"⬆️  {companion_name} ({weight:.1f} kB) → s3://{config['TRAILS_MAP_BUCKET']}/{companion_name}, {held}")
            upload_beside(companion, config)
        elif companion_name == "sw.js":
            print("⚠️  No sw.js beside the map — readers get no offline copy. Was this built by `make map`?")
        elif companion_name.startswith("icon-"):
            print(f"⚠️  No {companion_name} beside the map — the page links to it, so a home screen gets a screenshot instead.")
        else:
            print(f"⚠️  No {companion_name} beside the map — it cannot be installed, so iOS will sweep what it keeps.")

    if args.no_purge:
        print("↩️  Edge cache left alone (--no-purge); it holds the old map for up to 5 minutes.")
    else:
        purge(urls, config)
        print("🧹 Edge cache purged")

    print(f"✅ https://{host}/{name}")


if __name__ == "__main__":
    main()
