# Meerko Bittorent Client

A secure, fast, and anonymous BitTorrent client built with Python.

## Features

*   **Secure & Anonymous:** Prioritizes user privacy by routing traffic through a proxy, hiding your IP from peers.
*   **High Performance:** Built using the powerful and efficient `libtorrent` library.
*   **Easy to Use:** A simple command-line interface for managing downloads.
*   **Automatic Seeding Stop:** Automatically stops seeding when a share ratio of 1.0 is reached, ensuring you contribute fairly to the swarm.

## Installation

1.  **Create and activate a Python 3.10 virtual environment:**
    ```bash
    # Create the virtual environment
    py -3.10 -m venv .venv
    # Activate the virtual environment (on Windows)
    .venv\Scripts\activate
    ```

2.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

To download a torrent, run the client from the command line, providing a path to a `.torrent` file or a magnet link.

```bash
python -m meerko_bittorent <torrent_source> <save_path>
```

For a detailed reference of all commands and options, please see the [COMMANDS.md](COMMANDS.md) file.

### Examples

**Downloading from a `.torrent` file:**
```bash
python -m meerko_bittorent "path/to/your.torrent" "path/to/save/directory"
```

**Downloading from a magnet link:**
```bash
python -m meerko_bittorent "magnet:?xt=urn:btih:..." "path/to/save/directory"
```

### Using a Proxy

The client can be configured to use a proxy for anonymity. You can do this in two ways:

#### 1. Default Proxy with `config.ini`

For a more permanent setup, you can use the `config.ini` file:

1.  Rename `config.ini.example` to `config.ini`.
2.  Edit `config.ini` with your proxy details.

The client will automatically use these settings every time it runs.

#### 2. Command-Line Arguments

You can specify a proxy for a single run using command-line arguments. These will override the settings in `config.ini`.

```bash
python -m meerko_bittorent "magnet:?xt=urn:btih:..." "path/to/save/directory" --proxy-type socks5 --proxy-host your-proxy-host --proxy-port your-proxy-port
```

To disable the proxy for a single run, use the `--no-proxy` flag.
