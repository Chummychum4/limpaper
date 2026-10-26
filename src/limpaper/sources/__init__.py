"""Registry of online wallpaper sources.

None of these sites are affiliated with limpaper. Their content is made and
hosted by third parties; see THIRD_PARTY_WARNING.
"""

from __future__ import annotations

from .base import OnlineWallpaper, Page, Source, SourceError
from .moewalls import MoeWalls
from .motionbgs import MotionBGs
from .wallhaven import Wallhaven

THIRD_PARTY_WARNING = (
    "Wallpapers in Discover come from third-party websites (MotionBGs, MoeWalls "
    "and Wallhaven). They are not made, hosted, checked or endorsed by limpaper, "
    "and may contain malicious software. limpaper only accepts files that look "
    "like real video or image files, but that cannot guarantee they are safe. "
    "Download at your own risk, and respect each site's terms and the artists' rights."
)

SOURCES: dict[str, Source] = {s.id: s for s in (MotionBGs(), MoeWalls(), Wallhaven())}

__all__ = ["OnlineWallpaper", "Page", "Source", "SourceError", "SOURCES", "THIRD_PARTY_WARNING"]
