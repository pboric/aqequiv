"""Entry point that PyInstaller packs into aqequiv.exe."""

import sys

from aqequiv.app import main

sys.exit(main())
