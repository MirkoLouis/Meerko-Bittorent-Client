# Meerko Bittorent Client Commands

This document provides a detailed reference for all the command-line arguments available in the Meerko Bittorent Client.

## Main Command

The main command to run the client is:

```bash
python -m meerko_bittorent "<torrent_source>" "<save_path>" [options]
```

### Positional Arguments

*   `<torrent_source>`: **(Required)** The source of the torrent. This can be either:
    *   A path to a `.torrent` file on your local filesystem.
    *   A magnet link, enclosed in quotes.

*   `<save_path>`: **(Required)** The path to the directory where the downloaded files will be saved.

---

## Options

All options are optional.

### Proxy Configuration

You can configure a proxy for anonymity.

*   `--proxy-type <type>`: Specifies the type of proxy.
    *   **Values:** `socks5` or `http`.
    *   **Default:** `socks5` if using `config.ini`, otherwise no default.

*   `--proxy-host <host>`: The hostname or IP address of the proxy server.

*   `--proxy-port <port>`: The port number of the proxy server.

*   `--proxy-user <username>`: The username for proxy authentication (if required).

*   `--proxy-pass <password>`: The password for proxy authentication (if required).

*   `--no-proxy`: Disables the proxy for this run, even if a default proxy is configured in `config.ini`.

---

## Examples

### Downloading from a `.torrent` file

```bash
python -m meerko_bittorent "C:\Users\YourUser\Downloads\ubuntu.torrent" "C:\Users\YourUser\Downloads\ubuntu-distro"
```

### Downloading from a magnet link

```bash
python -m meerko_bittorent "magnet:?xt=urn:btih:..." "C:\Users\YourUser\Downloads\my-file"
```

### Using a SOCKS5 proxy

```bash
python -m meerko_bittorent "magnet:?xt=urn:btih:..." "C:\Downloads" --proxy-type socks5 --proxy-host 127.0.0.1 --proxy-port 9050
```

### Using an authenticated SOCKS5 proxy

```bash
python -m meerko_bittorent "magnet:?xt=urn:btih:..." "C:\Downloads" --proxy-type socks5 --proxy-host 192.168.1.100 --proxy-port 9050 --proxy-user myuser --proxy-pass mypassword
```

### Disabling the default proxy

If you have a proxy configured in `config.ini` but want to run the client without it for a specific download:

```bash
python -m meerko_bittorent "my-local.torrent" "C:\Local" --no-proxy
```

### Stopping a Download Gracefully

You can stop a running download at any time by pressing `Ctrl+C` in your terminal. The client will catch this signal, remove the torrent from the session, and shut down gracefully, preventing data corruption.
