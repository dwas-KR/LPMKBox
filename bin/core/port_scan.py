import subprocess
import time

from .utils import log


def wait_for_preloader() -> None:
    log("preloader.waiting")
    while True:
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-PnpDevice -Status OK | Where-Object { $_.FriendlyName -like '*PreLoader*' -or $_.FriendlyName -like '*Preloader*' -or $_.FriendlyName -like '*MediaTek USB Port*' } | Select-Object -First 1).FriendlyName",
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )
            name = (result.stdout or "").strip()
            if name:
                log("preloader.detected", name=name)
                return
        except Exception:
            pass
