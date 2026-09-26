#!/usr/bin/env python3
"""Fetch KOD VIT release covers via Spotify oEmbed and save locally."""

from __future__ import annotations

import json
import re
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image

OUT = Path("assets/covers")
OUT.mkdir(parents=True, exist_ok=True)

ARTIST_URL = "https://open.spotify.com/artist/22NpzyR8mc5NOBXAt6Rv3b"
KNOWN = {
    "Gangsters & Gang": "https://open.spotify.com/album/5Ims5PxbJT9E3JoodGwegY",
}

# slug, display title, year label for site
RELEASES = [
    ("gangsters-and-gang", "Gangsters & Gang", "2026"),
    ("gangster-pa-wifi", "Gangster på Wifi", "2026"),
    ("fel-sjalvbild", "Fel självbild", "2026"),
    ("fel-kassa", "Fel kassa", "2026"),
    ("hall-den-kvar", "Håll den kvar", "2026"),
    ("nar-den-kanns-fardig", "När den känns färdig", "2026"),
    ("ensam", "Ensam", "2026"),
    ("lampan-lyste", "Lampan lyste", "2026"),
    ("where-the-road-meets-the-sun", "Where the road meets the sun", "2026"),
    ("dar-ni-ar", "Där ni är", "2026"),
    ("vitlinje", "Vitlinje", "2026"),
]

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (compatible; KodVitCoverBot/1.0)",
        "Accept": "application/json,text/html,*/*",
    }
)


def oembed(spotify_url: str) -> dict:
    r = SESSION.get(
        "https://open.spotify.com/oembed",
        params={"url": spotify_url},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def discover_album_urls() -> dict[str, str]:
    """Map normalized title -> album url using artist page + search HTML."""
    found: dict[str, str] = dict(KNOWN)
    pages = [
        ARTIST_URL,
        f"{ARTIST_URL}/discography/album",
        f"{ARTIST_URL}/discography/single",
        f"{ARTIST_URL}/discography/all",
    ]
    album_ids: list[str] = []
    for page in pages:
        try:
            html = SESSION.get(page, timeout=30).text
        except Exception as exc:  # noqa: BLE001
            print("page fail", page, exc)
            continue
        album_ids.extend(re.findall(r"/album/([a-zA-Z0-9]{22})", html))
        time.sleep(0.4)

    # unique
    seen: list[str] = []
    for aid in album_ids:
        if aid not in seen:
            seen.append(aid)

    print("discovered album ids", len(seen))
    for aid in seen:
        url = f"https://open.spotify.com/album/{aid}"
        try:
            data = oembed(url)
        except Exception as exc:  # noqa: BLE001
            print("oembed fail", aid, exc)
            continue
        title = (data.get("title") or "").strip()
        # strip " by Artist" style suffixes sometimes present
        title_clean = re.sub(r"\s+by\s+.*$", "", title, flags=re.I).strip()
        found.setdefault(title_clean, url)
        print("album", title_clean, url)
        time.sleep(0.25)

    return found


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def match_url(title: str, catalog: dict[str, str]) -> str | None:
    if title in KNOWN:
        return KNOWN[title]
    n = normalize(title)
    for k, url in catalog.items():
        kn = normalize(k)
        if n == kn or n in kn or kn in n:
            return url
    # token overlap
    tokens = set(n.replace("&", " ").split())
    best = None
    best_score = 0
    for k, url in catalog.items():
        kn = set(normalize(k).replace("&", " ").split())
        score = len(tokens & kn)
        if score > best_score and score >= max(1, len(tokens) - 1):
            best_score = score
            best = url
    return best


def save_image(url: str, slug: str) -> dict:
    r = SESSION.get(url, timeout=60)
    r.raise_for_status()
    im = Image.open(BytesIO(r.content)).convert("RGB")
    # Optimize ~640 max
    im.thumbnail((640, 640), Image.Resampling.LANCZOS)
    webp = OUT / f"{slug}.webp"
    jpg = OUT / f"{slug}.jpg"
    im.save(webp, "WEBP", quality=82, method=6)
    im.save(jpg, "JPEG", quality=85, optimize=True)
    return {
        "webp": str(webp).replace("\\", "/"),
        "jpg": str(jpg).replace("\\", "/"),
        "width": im.width,
        "height": im.height,
    }


def main() -> None:
    catalog = discover_album_urls()
    manifest = []
    artist_fallback = ARTIST_URL

    for slug, title, year in RELEASES:
        url = match_url(title, catalog) or artist_fallback
        entry = {
            "slug": slug,
            "title": title,
            "year": year,
            "spotify_url": url,
        }
        try:
            # Prefer album oEmbed; artist page oEmbed won't give album art
            if "/album/" not in url:
                raise RuntimeError(f"No album URL for {title}")
            data = oembed(url)
            thumb = data.get("thumbnail_url")
            if not thumb:
                raise RuntimeError("missing thumbnail_url")
            paths = save_image(thumb, slug)
            entry.update(
                {
                    "oembed_title": data.get("title"),
                    "thumbnail_url": thumb,
                    **paths,
                    "ok": True,
                }
            )
            print("OK", slug, thumb)
        except Exception as exc:  # noqa: BLE001
            entry["ok"] = False
            entry["error"] = str(exc)
            print("FAIL", slug, exc)
        manifest.append(entry)
        time.sleep(0.3)

    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ok = sum(1 for m in manifest if m.get("ok"))
    print(f"done {ok}/{len(manifest)}")
    if ok == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
