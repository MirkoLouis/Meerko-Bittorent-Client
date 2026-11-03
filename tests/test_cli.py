# SPDX-License-Identifier: GPL-3.0-or-later
"""CLI tests: main(argv) driven with a scripted fake engine, so no network or libtorrent session is needed."""

import os
import threading

import pytest

from meerko_bittorent import __version__, cli
from meerko_bittorent.errors import InputError
from meerko_bittorent.proxy import ProxyKind, ProxySettings
from tests.fakes import FakeEngine

MAGNET = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"


# Isolated config file path plus a torrent file and save folder for each test
@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.delenv("MEERKO_PROXY_PASSWORD", raising=False)
    torrent = tmp_path / "file.torrent"
    torrent.write_bytes(b"d4:infod4:name1:xee")
    return {"config": tmp_path / "config.ini", "torrent": torrent, "save": tmp_path / "save"}


# Run main with the fake engine and a --config pointing into tmp_path
def run_cli(paths, engine, *arguments, stop_event=None):
    argv = ["--config", str(paths["config"]), *arguments]
    return cli.main(argv, engine_factory=engine, stop_event=stop_event)


# --version shows both versions, proving libtorrent loads (the frozen-build smoke test relies on this)
def test_version_prints_versions_and_exits_0(capsys):
    assert cli.main(["--version"]) == 0
    output = capsys.readouterr().out
    assert __version__ in output
    assert "libtorrent 2.0" in output


# The leaky password flag no longer exists
def test_no_proxy_pass_flag(paths):
    assert run_cli(paths, FakeEngine("finish"), "--proxy-pass", "x", str(paths["torrent"]), str(paths["save"])) == 2


# A single flag overrides only its own config field
def test_flag_overrides_single_config_field(paths):
    paths["config"].write_text("[Proxy]\ntype = socks5\nhost = a\nport = 1080\n", encoding="utf-8")
    engine = FakeEngine("finish")
    assert run_cli(paths, engine, "--proxy-port", "1081", str(paths["torrent"]), str(paths["save"])) == 0
    assert engine.proxy == ProxySettings(ProxyKind.SOCKS5, "a", 1081)


# --no-proxy ignores the configured proxy and any proxy flags
def test_no_proxy_wins(paths):
    paths["config"].write_text("[Proxy]\ntype = socks5\nhost = a\nport = 1080\n", encoding="utf-8")
    engine = FakeEngine("finish")
    assert run_cli(paths, engine, "--no-proxy", "--proxy-port", "9", str(paths["torrent"]), str(paths["save"])) == 0
    assert engine.proxy is None


# A proxy that is disabled in config.ini is not used
def test_disabled_config_proxy_is_ignored(paths):
    paths["config"].write_text("[Proxy]\nenabled = false\ntype = socks5\nhost = a\nport = 1080\n", encoding="utf-8")
    engine = FakeEngine("finish")
    assert run_cli(paths, engine, str(paths["torrent"]), str(paths["save"])) == 0
    assert engine.proxy is None


# Password sources in order: config file, environment variable, interactive prompt
def test_resolve_password_order():
    settings = ProxySettings(ProxyKind.SOCKS5, "h", 1080, "me")
    environ = {"MEERKO_PROXY_PASSWORD": "from-env"}

    # Fail loudly if the prompt is used when it should not be
    def forbidden_prompt(_text):
        raise AssertionError("prompt must not be used")

    resolved = cli.resolve_password(settings, "from-config", environ, True, forbidden_prompt)
    assert resolved.password == "from-config"
    assert cli.resolve_password(settings, None, environ, True, forbidden_prompt).password == "from-env"
    assert cli.resolve_password(settings, None, {}, True, lambda _text: "typed").password == "typed"
    with pytest.raises(InputError):
        cli.resolve_password(settings, None, {}, False, forbidden_prompt)


# No username means no password is needed at all
def test_resolve_password_without_username_is_untouched():
    settings = ProxySettings(ProxyKind.HTTP, "h", 8080)
    assert cli.resolve_password(settings, None, {}, False, lambda _text: "x") == settings


# Exit code 0 once the download is finished
def test_finished_exits_0(paths):
    engine = FakeEngine("finish")
    assert run_cli(paths, engine, str(paths["torrent"]), str(paths["save"])) == 0
    assert engine.download.close_calls == 1
    assert paths["save"].is_dir()


# Exit code 1 for torrent and disk errors
def test_torrent_error_exits_1(paths, capsys):
    assert run_cli(paths, FakeEngine("torrent_error"), str(paths["torrent"]), str(paths["save"])) == 1
    assert "disk full" in capsys.readouterr().err


# Exit code 3 when another Meerko process holds the torrent
def test_already_running_exits_3(paths, capsys):
    assert run_cli(paths, FakeEngine("already_running"), str(paths["torrent"]), str(paths["save"])) == 3
    assert "another Meerko process" in capsys.readouterr().err


# Exit code 2 for an invalid proxy
def test_invalid_proxy_exits_2(paths):
    arguments = ["--proxy-type", "socks5", "--proxy-host", "h", "--proxy-port", "0"]
    assert run_cli(paths, FakeEngine("finish"), *arguments, str(paths["torrent"]), str(paths["save"])) == 2


# A proxy username with no password source and no terminal is an input error
def test_missing_password_without_terminal_exits_2(paths):
    arguments = ["--proxy-type", "socks5", "--proxy-host", "h", "--proxy-port", "1080", "--proxy-user", "me"]
    assert run_cli(paths, FakeEngine("finish"), *arguments, str(paths["torrent"]), str(paths["save"])) == 2


# A save path that is an existing file is refused cleanly (Review Focus 1)
def test_save_path_that_is_a_file_exits_2(paths, capsys):
    not_a_folder = paths["torrent"].parent / "plain-file"
    not_a_folder.write_text("x", encoding="utf-8")
    assert run_cli(paths, FakeEngine("finish"), str(paths["torrent"]), str(not_a_folder)) == 2
    assert "Traceback" not in capsys.readouterr().err


# A .torrent path that does not exist is a usage error
def test_missing_torrent_file_exits_2(paths):
    missing = paths["torrent"].parent / "absent.torrent"
    assert run_cli(paths, FakeEngine("finish"), str(missing), str(paths["save"])) == 2


# A corrupt config file is reported, not a crash
def test_malformed_config_exits_2(paths):
    paths["config"].write_text("[Proxy]\nport = abc\n", encoding="utf-8")
    assert run_cli(paths, FakeEngine("finish"), str(paths["torrent"]), str(paths["save"])) == 2


# Stopping during a metadata wait exits 130 and closes the download once (Review Focus 4)
def test_interrupt_during_metadata_wait_exits_130(paths):
    engine = FakeEngine("block_metadata")
    stop_event = threading.Event()
    timer = threading.Timer(0.2, stop_event.set)
    timer.start()
    try:
        assert run_cli(paths, engine, MAGNET, str(paths["save"]), stop_event=stop_event) == 130
    finally:
        timer.cancel()
    assert engine.download.close_calls == 1


# A readable config file containing a password triggers a chmod hint
@pytest.mark.skipif(os.name == "nt", reason="POSIX file permissions")
def test_insecure_config_warns(paths, capsys):
    paths["config"].write_text(
        "[Proxy]\ntype = socks5\nhost = h\nport = 1080\nusername = me\npassword = p\n", encoding="utf-8"
    )
    paths["config"].chmod(0o644)
    assert run_cli(paths, FakeEngine("finish"), str(paths["torrent"]), str(paths["save"])) == 0
    assert "chmod 600" in capsys.readouterr().err
