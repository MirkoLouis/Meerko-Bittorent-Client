# meerko-bittorent-cli reference

`meerko-bittorent-cli` downloads one torrent, seeds it until a 1.0 share ratio, then exits.

```bash
meerko-bittorent-cli [options] SOURCE SAVE_PATH
```

How to run it on each platform:

| Platform | Command |
|---|---|
| Nix | `nix shell github:MirkoLouis/Meerko-Bittorent-Client -c meerko-bittorent-cli [options] SOURCE SAVE_PATH` |
| Linux AppImage | `./Meerko-Bittorent-<version>-x86_64.AppImage cli [options] SOURCE SAVE_PATH` |
| Windows | `Meerko-Bittorent-<version>-windows-x86_64-cli.exe [options] SOURCE SAVE_PATH` |
| From source | `python -m meerko_bittorent.cli [options] SOURCE SAVE_PATH` |

## Arguments

| Argument | Meaning |
|---|---|
| `SOURCE` | Path to a `.torrent` file, or a magnet link (quote it: `"magnet:?xt=..."`) |
| `SAVE_PATH` | Folder to save into. Created if it does not exist; must not be an existing file |

## Options

| Option | Meaning |
|---|---|
| `--config PATH` | Use this `config.ini` instead of the per-user one |
| `--proxy-type {socks5,http}` | Proxy protocol |
| `--proxy-host HOST` | Proxy host name or IP address |
| `--proxy-port PORT` | Proxy port (1–65535) |
| `--proxy-user USER` | Proxy username; the password is looked up as described below |
| `--no-proxy` | Connect directly for this run, ignoring any configured proxy and proxy flags |
| `--quiet` | No progress output; errors are still shown |
| `--version` | Show the Meerko and libtorrent versions |
| `-h`, `--help` | Show help |

Each proxy flag overrides only its own field from `config.ini`. For example, `--proxy-port 1081` keeps the
configured host and type and changes only the port. Without a configured proxy, `--proxy-type`, `--proxy-host`
and `--proxy-port` must all be given.

## Proxy password

There is no password option, because anything on the command line ends up in your shell history and is visible
to other users in the process list. When the proxy has a username, the password is taken from the first of:

1. the `password` line in `config.ini` (keep that file private: `chmod 600`; the CLI warns if it is not),
2. the `MEERKO_PROXY_PASSWORD` environment variable,
3. a hidden prompt, when running in a terminal.

If none of these is available the CLI exits with code 2 instead of connecting without the password.

## Settings file

Default location (shared with the desktop app):

*   Linux: `~/.config/meerko-bittorent/config.ini`, or `$XDG_CONFIG_HOME/meerko-bittorent/config.ini`
*   Windows: `%APPDATA%\meerko-bittorent\config.ini`

See [`config.ini.example`](config.ini.example) for the format.

## Output

Progress and messages go to standard error, so standard output stays clean for scripts. In a terminal one status
line updates in place every second; when the output is piped, a plain line is written every 10 seconds.

## Stopping

`Ctrl+C` (or `SIGTERM` on Linux) stops the download gracefully: the torrent is removed from the session, its
lock is released, and the CLI exits with code 130.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Finished: downloaded and seeded to a 1.0 ratio |
| 1 | Torrent or disk error, or an unreadable `.torrent` / magnet link |
| 2 | Usage or settings error: bad options, invalid proxy, broken `config.ini`, missing password with no terminal |
| 3 | Another Meerko process (the app or another CLI) is already downloading this torrent |
| 130 | Stopped with `Ctrl+C` or `SIGTERM` |

## Examples

```bash
# Download from a .torrent file
meerko-bittorent-cli "~/Downloads/ubuntu.torrent" "~/Downloads/ubuntu"

# Download from a magnet link through a SOCKS5 proxy
meerko-bittorent-cli --proxy-type socks5 --proxy-host 127.0.0.1 --proxy-port 1080 "magnet:?xt=urn:btih:..." "downloads"

# Proxy with a login, password from the environment (e.g. in a script)
MEERKO_PROXY_PASSWORD="$(pass show proxy)" meerko-bittorent-cli --proxy-user me "magnet:?..." "downloads"

# Ignore the configured proxy once
meerko-bittorent-cli --no-proxy "my.torrent" "downloads"
```
