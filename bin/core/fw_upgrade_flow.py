from pathlib import Path
import time
import xml.etree.ElementTree as ET
import subprocess
import shutil

from .utils import (
    log,
    clear_console,
    kill_adb_server,
    wait_for_device,
    adb_reboot,
)
from .scatter import prepare_platform_scatter
from .flash_spft import prepare_flash_files, launch_spft_gui, run_firmware_upgrade
from .proinfo_country import wait_and_patch_proinfo
from .port_scan import wait_for_preloader
from .global_flow import (
    _cleanup_before_flow,
    _cleanup_after_flow,
    _check_flash_xml_platform,
    _detect_platform,
)

BASE_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = BASE_DIR / "tools"
IMAGE_DIR = BASE_DIR / "image"
PRC_DIR = TOOLS_DIR / "PRC"
ADB_EXE = TOOLS_DIR / "platform-tools" / "adb.exe"
HISTORY_INI = TOOLS_DIR / "history.ini"


def _adb_getprop(name: str) -> str:
    if not ADB_EXE.is_file():
        return ""
    try:
        result = subprocess.run(
            [str(ADB_EXE), "shell", "getprop", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def _delete_history_ini() -> None:
    try:
        if HISTORY_INI.is_file():
            HISTORY_INI.unlink()
    except Exception:
        pass


def _copy_prc_images_to_image() -> None:
    if not IMAGE_DIR.is_dir():
        return
    if not PRC_DIR.is_dir():
        return
    for name in ("lk.img", "dtbo.img"):
        src = PRC_DIR / name
        dst = IMAGE_DIR / name
        if not src.is_file():
            continue
        try:
            if dst.is_file():
                dst.unlink()
        except Exception:
            pass
        try:
            shutil.copy2(src, dst)
        except Exception:
            pass


def _patch_userdata_keep_data(scatter_path: Path) -> None:
    try:
        tree = ET.parse(str(scatter_path))
        root = tree.getroot()
    except Exception:
        return
    changed = False
    for part in root.findall(".//partition_index"):
        name = part.findtext("partition_name", "").strip().lower()
        if name != "userdata":
            continue
        fn = part.find("file_name")
        if fn is None:
            fn = ET.SubElement(part, "file_name")
        if fn.text != "userdata.img":
            fn.text = "userdata.img"
        is_download = part.find("is_download")
        if is_download is None:
            is_download = ET.SubElement(part, "is_download")
        text = (is_download.text or "").strip().lower()
        if text != "false":
            is_download.text = "false"
        is_upgradable = part.find("is_upgradable")
        if is_upgradable is None:
            is_upgradable = ET.SubElement(part, "is_upgradable")
        text = (is_upgradable.text or "").strip().lower()
        if text != "false":
            is_upgradable.text = "false"
        changed = True
    if not changed:
        log("scatter.userdata_not_found")
        return
    try:
        tree.write(str(scatter_path), encoding="utf-8", xml_declaration=True)
        log("scatter.userdata_patched")
    except Exception:
        pass


def run_firmware_upgrade_keep_data_flow() -> None:
    clear_console()
    log("flow.keep_data.start")
    _cleanup_before_flow()
    _delete_history_ini()
    kill_adb_server()
    try:
        ok = wait_for_device()
        if not ok:
            return
        log("flow.device_info_check")
        hw = _adb_getprop("ro.vendor.config.lgsi.hw.version")
        cpu = _adb_getprop("ro.vendor.config.lgsi.cpuinfo")
        log("flow.device_info", hw=hw, cpu=cpu)
        region = _adb_getprop("ro.config.zui.region").upper()
        if region == "PRC":
            log("flow.keep_data.not_global_rom")
            time.sleep(2)
            return
        if region and region != "ROW":
            log("flow.keep_data.unknown_region")
            time.sleep(2)
            return
        platform = _detect_platform()
        if not platform:
            return
        time.sleep(5)
        scatter = prepare_platform_scatter(platform)
        if scatter is None:
            return
        _patch_userdata_keep_data(scatter)
        time.sleep(5)
        if not _check_flash_xml_platform(platform):
            return
        time.sleep(5)
        _copy_prc_images_to_image()
        if not prepare_flash_files():
            return
        time.sleep(5)
        _delete_history_ini()
        launch_spft_gui()
        time.sleep(5)
        wait_and_patch_proinfo(platform)
        time.sleep(5)
        if not wait_for_device():
            return
        log("flow.rebooting")
        adb_reboot()
        wait_for_preloader()
        run_firmware_upgrade()
        _cleanup_after_flow(platform)
        log("flow.keep_data.done")
    finally:
        kill_adb_server()
