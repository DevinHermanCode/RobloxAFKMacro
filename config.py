# config.py
import os
import sys
import json
import time
import base64
import shutil
import tempfile
import subprocess
import requests
import tkinter as tk
from tkinter import messagebox
from threading import Thread, Event
from io import BytesIO

import importlib.util
import psutil
import pygetwindow as gw
import keyboard
import pyautogui
import pystray
from PIL import Image, ImageTk
import win32gui
import win32process

import os
import sys
import tempfile
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox

# ──────────────────────────────────────────────
# 1) Your current version
# ──────────────────────────────────────────────
CURRENT_VERSION = "1.1"  # update this on each release
CONFIG_VERSION = 2 # update this for major config file handling changes
# ──────────────────────────────────────────────
# GitHub API for repo’s latest release
GITHUB_RELEASES_API = (
    "https://api.github.com/repos/"
    "OnixProgramming/RobloxAFKMacro/releases/latest"
)
ASSET_EXE_NAME  = "Yet_Another_Roblox_AFK_Macro.exe"
# ──────────────────────────────────────────────

def to_tuple(v: str) -> tuple[int, int, int]:
    """
    Normalize a version string into a 3-tuple of ints,
    padding with zeros if needed (so "1.1" → (1,1,0)).
    """
    parts = v.lstrip("v").split(".")
    nums = [int(x) for x in parts]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])

def check_for_updates():
    print("DEBUG✔ Checking for updates…", "CURRENT:", CURRENT_VERSION)

    try:
        r = requests.get(GITHUB_RELEASES_API, timeout=5)
        r.raise_for_status()
        release = r.json()

        latest = release.get("tag_name", "").lstrip("v")
        print("DEBUG✔ Latest release tag:", latest)
        if not latest or to_tuple(latest) <= to_tuple(CURRENT_VERSION):
            print("DEBUG✔ Up to date, no update needed")
            return  # already up to date

        root = tk.Tk(); root.withdraw()
        prompt = (
            f"A new version ({latest}) is available!\n"
            f"You have {CURRENT_VERSION}.\n\n"
            "Download and install now?"
        )
        if not messagebox.askyesno("Update Available", prompt):
            return

        # Find the .exe asset
        download_url = next(
            (a["browser_download_url"]
             for a in release.get("assets", [])
             if a.get("name") == ASSET_EXE_NAME),
            None
        )
        if not download_url:
            messagebox.showerror(
                "Update Error",
                f"Could not find an asset named {ASSET_EXE_NAME}."
            )
            return

        # Download to temp file
        tmp_path = os.path.join(tempfile.gettempdir(), ASSET_EXE_NAME)
        with requests.get(download_url, stream=True) as dl, open(tmp_path, "wb") as out:
            shutil.copyfileobj(dl.raw, out)

        # Spawn a short‐lived helper to overwrite the running EXE
        helper = f"""
        import time, shutil, os, sys
        time.sleep(1)
        src = r'{tmp_path}'
        dst = r'{os.path.abspath(sys.argv[0])}'
        shutil.copy(src, dst)
        """
        subprocess.Popen([sys.executable, "-c", helper], close_fds=True)
        sys.exit()

    except Exception as e:
        # If something goes wrong, we’ll just skip update silently
        print("Update check failed:", e)        
# ————————————————————————————————
# 2) Paths & directories
#————————————————————————————————
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APPDATA_DIR = os.path.join(os.getenv("APPDATA"), "RobloxAFKMacro")
CONFIG_FILE = os.path.join(APPDATA_DIR, "afk_config.json")

# ————————————————————————————————
# 3) Icon loader from base64
#————————————————————————————————
def icon_base64() -> str:
    # Base64 encoded image data
    return("iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAEwmlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSfvu78nIGlkPSdXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQnPz4KPHg6eG1wbWV0YSB4bWxuczp4PSdhZG9iZTpuczptZXRhLyc+CjxyZGY6UkRGIHhtbG5zOnJkZj0naHR0cDovL3d3dy53My5vcmcvMTk5OS8wMi8yMi1yZGYtc3ludGF4LW5zIyc+CgogPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9JycKICB4bWxuczpBdHRyaWI9J2h0dHA6Ly9ucy5hdHRyaWJ1dGlvbi5jb20vYWRzLzEuMC8nPgogIDxBdHRyaWI6QWRzPgogICA8cmRmOlNlcT4KICAgIDxyZGY6bGkgcmRmOnBhcnNlVHlwZT0nUmVzb3VyY2UnPgogICAgIDxBdHRyaWI6Q3JlYXRlZD4yMDI1LTA1LTExPC9BdHRyaWI6Q3JlYXRlZD4KICAgICA8QXR0cmliOkV4dElkPjRhYTBjMzA5LWI4N2YtNGRkNS1hZjhlLTdmZWIzMDYwODJmODwvQXR0cmliOkV4dElkPgogICAgIDxBdHRyaWI6RmJJZD41MjUyNjU5MTQxNzk1ODA8L0F0dHJpYjpGYklkPgogICAgIDxBdHRyaWI6VG91Y2hUeXBlPjI8L0F0dHJpYjpUb3VjaFR5cGU+CiAgICA8L3JkZjpsaT4KICAgPC9yZGY6U2VxPgogIDwvQXR0cmliOkFkcz4KIDwvcmRmOkRlc2NyaXB0aW9uPgoKIDxyZGY6RGVzY3JpcHRpb24gcmRmOmFib3V0PScnCiAgeG1sbnM6ZGM9J2h0dHA6Ly9wdXJsLm9yZy9kYy9lbGVtZW50cy8xLjEvJz4KICA8ZGM6dGl0bGU+CiAgIDxyZGY6QWx0PgogICAgPHJkZjpsaSB4bWw6bGFuZz0neC1kZWZhdWx0Jz5Sb2Jsb3ggQUZLIE1hY3JvIEljb24gLSAxPC9yZGY6bGk+CiAgIDwvcmRmOkFsdD4KICA8L2RjOnRpdGxlPgogPC9yZGY6RGVzY3JpcHRpb24+CgogPHJkZjpEZXNj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")

def load_icon_image_from_base64() -> Image.Image:
    """Decode base64 string and return PIL Image."""
    decoded = base64.b64decode(icon_base64())
    return Image.open(BytesIO(decoded))

# ──────────────────────────────────────────────
# 4) Dependency checker/installer
# ──────────────────────────────────────────────
REQUIRED_MODULES = {
    'keyboard': 'keyboard',
    'pyautogui': 'pyautogui',
    'pystray': 'pystray',
    'pillow': 'PIL',
    'pygetwindow': 'pygetwindow',
    'pywin32': 'win32gui',
}

def check_and_install_dependencies():
    missing = [
        pip for pip, imp in REQUIRED_MODULES.items()
        if importlib.util.find_spec(imp) is None
    ]
    if not missing:
        return

    root = tk.Tk()
    root.withdraw()
    confirm = messagebox.askokcancel(
        "Install Dependencies",
        "The following modules are missing:\n\n"
        + ", ".join(missing)
        + "\n\nInstall now?"
    )
    root.destroy()

    if confirm:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
    else:
        sys.exit("User cancelled dependency installation.")
