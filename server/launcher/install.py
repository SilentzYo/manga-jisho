import json
import re
import sys
import winreg
from pathlib import Path

NAME = "com.manga_jisho.server"
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / f"{NAME}.json"
REGISTRY = rf"Software\Google\Chrome\NativeMessagingHosts\{NAME}"


def install(extension_id):
    MANIFEST.write_text(json.dumps({
        "name": NAME,
        "description": "Starts the Manga Jisho server",
        "path": str(HERE / "host.bat"),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }, indent=2))
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(MANIFEST))
    print(f"Done. Chrome can now start the server for extension {extension_id}.")


def uninstall():
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REGISTRY)
    MANIFEST.unlink(missing_ok=True)
    print("Removed.")


if __name__ == "__main__":
    argument = sys.argv[1] if len(sys.argv) == 2 else ""
    if argument == "--uninstall":
        uninstall()
    elif re.fullmatch(r"[a-p]{32}", argument):
        install(argument)
    else:
        print("Usage: install.py <extension ID from chrome://extensions>")
        print("       install.py --uninstall")
