# SPDX-License-Identifier: GPL-3.0-or-later
from meerko_bittorent.ui import App


# Entry point for `python -m meerko_bittorent` and the meerko-bittorent gui-script
def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
