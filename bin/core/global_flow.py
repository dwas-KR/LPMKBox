from pathlib import Path
import time
import shutil

from .utils import log, clear_console, kill_adb_server, wait_for_device, adb_reboot, safe_unlink
from .scatter import prepare_platform_scatter
from .flash_spft import prepare_flash_files, launch_spft_gui, run_firmware_upgrade
from .proinfo_country import wait_and_patch_proinfo
from .port_scan import wait_for_preloader
from .constants import IMAGE_DIR, PRC_DIR, READBACK_DIR, FLASH_XML_DLAGENT, FLASH_XML_ROOT, TOOLS_DIR
from .adb_utils import adb_shell_getprop


def _cleanup_before_flow() -> None:
    try:
        if IMAGE_DIR.is_dir():
            for entry in IMAGE_DIR.iterdir():
                if not entry.is_file():
                    continue
                name = entry.name.lower()
                if name.endswith("_android_scatter.xml") or name in (
                    "android_scatter.xml",
                    "android_scatter_a,b.xml",
                ) or name == "proinfo":
                    try:
                        entry.unlink()
                    except Exception:
                        pass
    except Exception:
        pass
    try:
        if READBACK_DIR.is_dir():
            for entry in READBACK_DIR.iterdir():
                if entry.is_file() and "proinfo" in entry.name.lower():
                    try:
                        entry.unlink()
                    except Exception:
                        pass
    except Exception:
        pass
    try:
        history = TOOLS_DIR / "history.ini"
        if history.is_file():
            history.unlink()
    except Exception:
        pass


def _cleanup_after_flow(platform: str) -> None:
    try:
        final_scatter = IMAGE_DIR / f"{platform}_Android_scatter.xml"
        if final_scatter.is_file():
            try:
                final_scatter.unlink()
            except Exception:
                pass
    except Exception:
        pass
    _cleanup_before_flow()


def _detect_platform() -> str:
    log("flow.detect_platform")
    platform = adb_shell_getprop("ro.vendor.mediatek.platform")
    if not platform:
        log("flow.not_mtk", platform=platform or "")
        return ""
    platform = platform.strip().upper()
    if not platform.startswith("MT"):
        log("flow.not_mtk", platform=platform)
        return ""
    log("flow.platform", platform=platform)
    return platform


def _check_flash_xml_platform(platform: str) -> bool:
    flash_xml = FLASH_XML_DLAGENT if FLASH_XML_DLAGENT.is_file() else FLASH_XML_ROOT
    if not flash_xml.is_file():
        log("flow.no_flash_xml")
        return False

    try:
        text = flash_xml.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        log("flow.no_flash_xml")
        return False

    expected = platform
    if expected and expected not in text:
        log("flow.flash_xml_mismatch", platform=platform, expected=expected, path=str(flash_xml))
        return False
    return True


def _replace_prc_images() -> None:
    if not IMAGE_DIR.is_dir() or not PRC_DIR.is_dir():
        return
    for fname in ("lk.img", "dtbo.img"):
        dst = IMAGE_DIR / fname
        if dst.is_file():
            try:
                dst.unlink()
            except Exception:
                pass
        src = PRC_DIR / fname
        if src.is_file():
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass


def run_global_firmware_upgrade_flow() -> None:
    log("flow.start")
    _cleanup_before_flow()
    kill_adb_server()
    try:
        wait_for_device()
        log("flow.device_info_check")
        hw = adb_shell_getprop("ro.vendor.config.lgsi.hw.version") or ""
        cpu = adb_shell_getprop("ro.vendor.config.lgsi.cpuinfo") or ""
        log("flow.device_info", hw=hw, cpu=cpu)
        platform = _detect_platform()
        if not platform:
            return
        time.sleep(5)
        scatter = prepare_platform_scatter(platform)
        if scatter is None:
            return
        time.sleep(5)
        if not _check_flash_xml_platform(platform):
            return
        time.sleep(5)
        _replace_prc_images()
        if not prepare_flash_files():
            return
        launch_spft_gui()
        time.sleep(5)
        wait_and_patch_proinfo(platform)
        time.sleep(5)
        wait_for_device()
        log("flow.rebooting")
        adb_reboot()
        wait_for_preloader()
        run_firmware_upgrade()
        _cleanup_after_flow(platform)
        log("flow.done")
    finally:
        kill_adb_server()
