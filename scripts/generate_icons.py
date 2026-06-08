from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ICON_SPECS = {
    "icon.png": (32, 32),
    "32x32.png": (32, 32),
    "128x128.png": (128, 128),
    "128x128@2x.png": (256, 256),
}
ICO_SIZES = [(32, 32), (128, 128), (256, 256)]
ICON_COLOR = (123, 47, 190, 255)


def generate_icons(root: Path = ROOT) -> None:
    for app_dir in ("companion", "companion-mac"):
        icon_dir = root / app_dir / "src-tauri" / "icons"
        icon_dir.mkdir(parents=True, exist_ok=True)
        for filename, size in ICON_SPECS.items():
            image = Image.new("RGBA", size, ICON_COLOR)
            image.save(icon_dir / filename)
            print(f"[Marouba] wrote {icon_dir / filename}")
        ico_image = Image.new("RGBA", (256, 256), ICON_COLOR)
        ico_image.save(icon_dir / "icon.ico", sizes=ICO_SIZES)
        print(f"[Marouba] wrote {icon_dir / 'icon.ico'}")


if __name__ == "__main__":
    generate_icons()
