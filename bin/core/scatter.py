from pathlib import Path
import xml.etree.ElementTree as ET

from .constants import IMAGE_DIR
from .utils import log
from .xml_crypto import decrypt_scatter_x


def _find_scatter_x(platform: str) -> Path | None:
    if not IMAGE_DIR.is_dir():
        log("scatter.not_found")
        return None
    platform = platform.strip()
    if platform:
        candidate = IMAGE_DIR / f"{platform}_Android_scatter.x"
        if candidate.is_file():
            return candidate
    for p in IMAGE_DIR.glob("*_Android_scatter.x"):
        if p.is_file():
            return p
    log("scatter.not_found")
    return None


def _convert_x_to_xml(scatter_x: Path) -> Path:
    out_path = IMAGE_DIR / "Android_scatter.xml"
    log("scatter.convert")
    body = decrypt_scatter_x(scatter_x)
    out_path.write_bytes(body)
    log("scatter.convert_done")
    return out_path


def _create_ab_scatter(xml_path: Path) -> Path:
    ab_path = IMAGE_DIR / "Android_scatter_A,B.xml"
    log("scatter.create_ab")
    ab_path.write_bytes(xml_path.read_bytes())
    return ab_path


def _patch_proinfo(ab_path: Path, final_name: str) -> Path:
    tree = ET.parse(str(ab_path))
    root = tree.getroot()
    found = False
    for part in root.findall(".//partition_index"):
        name = part.findtext("partition_name", "").strip().lower()
        if name == "proinfo":
            found = True
            fn = part.find("file_name")
            if fn is None:
                fn = ET.SubElement(part, "file_name")
            fn.text = "proinfo"
            is_download = part.find("is_download")
            if is_download is None:
                is_download = ET.SubElement(part, "is_download")
            is_download.text = "true"
            is_upgradable = part.find("is_upgradable")
            if is_upgradable is None:
                is_upgradable = ET.SubElement(part, "is_upgradable")
            is_upgradable.text = "true"
    final_path = IMAGE_DIR / final_name
    tree.write(str(final_path), encoding="utf-8", xml_declaration=True)
    if not found:
        log("scatter.proinfo_not_found")
    return final_path


def _cleanup_temp() -> None:
    for name in ("Android_scatter.xml", "Android_scatter_A,B.xml"):
        p = IMAGE_DIR / name
        if p.is_file():
            try:
                p.unlink()
            except Exception:
                pass
    log("scatter.temp_cleanup")


def prepare_platform_scatter(platform: str) -> Path | None:
    scatter_x = _find_scatter_x(platform)
    if scatter_x is None:
        return None
    log("scatter.found_x", name=scatter_x.name)
    xml_path = _convert_x_to_xml(scatter_x)
    ab_path = _create_ab_scatter(xml_path)
    final_name = scatter_x.name.replace(".x", ".xml")
    final_path = _patch_proinfo(ab_path, final_name)
    _cleanup_temp()
    log("scatter.final_saved", path=str(final_path))
    return final_path
