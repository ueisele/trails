"""Pack validation and immutable sync, with all bucket operations mocked."""

import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from trails.processing import packs


@pytest.fixture
def deploy():
    path = Path(__file__).resolve().parents[4] / "analysis/scripts/deploy_map.py"
    spec = importlib.util.spec_from_file_location("deploy_map", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def built(tmp_path):
    tile = tmp_path / "tile.png"
    tile.write_bytes(packs.PNG + b"test data")
    root = tmp_path / "packs"
    version = root / "dem/example/1"
    for x in range(2):
        packs.write_pack({(1, x, 0): tile, (2, x * 2, 0): tile}, version / f"1/{x}/0.pmtiles")
    (version / "index.json").write_text(json.dumps({"complete": True}))
    (version / "interrupted.pmtiles.part").write_bytes(b"partial")
    return root


def test_check_opens_every_pack_and_counts_entries(deploy, built, capsys):
    indexes, count = deploy.check_tree(built, "packs")
    assert count == 2 and len(indexes) == 1
    assert "2 packs containing 4 tile entries" in capsys.readouterr().out
    # The second pack must be opened too, and corruption of its directory refused.
    path = built / "dem/example/1/1/1/0.pmtiles"
    data = bytearray(path.read_bytes())
    data[127] = 1
    path.write_bytes(data)
    with pytest.raises(SystemExit, match="Cannot open pack"):
        deploy.check_tree(built, "packs")


def test_incomplete_index_prevents_deploy(deploy, built):
    (built / "dem/example/1/index.json").write_text('{"complete": false}')
    with pytest.raises(SystemExit, match="not complete"):
        deploy.check_tree(built, "packs")


@pytest.mark.parametrize("dry_run", [True, False])
def test_publish_validates_before_sync_and_dry_run_never_uploads_index(deploy, built, monkeypatch, dry_run):
    sync = Mock(return_value=(2, 1234))
    upload = Mock()
    monkeypatch.setattr(deploy, "sync_tree", sync)
    monkeypatch.setattr(deploy, "upload_index", upload)
    config = {"TRAILS_MAP_BUCKET": "test-bucket"}
    deploy.publish_trees(["packs"], built.parent, config, dry_run)
    sync.assert_called_once_with(built, "packs", config, dry_run)
    assert upload.call_count == (0 if dry_run else 1)
    sync.reset_mock()
    (built / "dem/example/1/1/1/0.pmtiles").write_bytes(b"broken")
    with pytest.raises(SystemExit):
        deploy.publish_trees(["packs"], built.parent, config, dry_run)
    sync.assert_not_called()


@pytest.mark.parametrize("dry_run", [True, False])
def test_sync_uses_immutable_header_and_real_aws_dryrun(deploy, built, monkeypatch, dry_run):
    path = built / "dem/example/1/1/0/0.pmtiles"
    process = Mock(stdout=io.StringIO(f"{'(dryrun) ' if dry_run else ''}upload: {path} to s3://test-bucket/packs/test.pmtiles\n"))
    process.wait.return_value = 0
    popen = Mock(return_value=process)
    monkeypatch.setattr(deploy.subprocess, "Popen", popen)
    config = {"TRAILS_MAP_BUCKET": "test-bucket", "TRAILS_MAP_S3_ENDPOINT": "https://example.invalid"}
    assert deploy.sync_tree(built, "packs", config, dry_run) == (1, path.stat().st_size)
    args = popen.call_args.args[0]
    assert args[args.index("--cache-control") + 1] == "public, max-age=31536000, immutable"
    assert ("--dryrun" in args) is dry_run
    assert "*.part" in args and "*/index.json" in args
    assert "s3://test-bucket/packs" in args
