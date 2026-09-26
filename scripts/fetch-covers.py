#!/usr/bin/env python3
"""Fetch KOD VIT release covers via Spotify oEmbed and save locally."""

from __future__ import annotations

import base64
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

ARTIST = "KOD VIT"
ARTIST_URL = "https://open.spotify.com/artist/22NpzyR8mc5NOBXAt6Rv3b"
KNOWN = {
    "Gangsters & Gang": "https://open.spotify.com/album/5Ims5PxbJT9E3JoodGwegY",
}

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
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/json,*/*",
        "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
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


def collect_album_ids_from_html(html: str) -> list[str]:
    ids = re.findall(r"/album/([a-zA-Z0-9]{22})", html)
    # also spotify:album:
    ids += re.findall(r"spotify:album:([a-zA-Z0-9]{22})", html)
    seen: list[str] = []
    for i in ids:
        if i not in seen:
            seen.append(i)
    return seen


def search_album_url(title: str) -> str | None:
    queries = [
        f"{title} {ARTIST}",
        f"artist:{ARTIST} {title}",
        title,
    ]
    for q in queries:
        url = f"https://open.spotify.com/search/{quote(q)}/albums"
        try:
            html = SESSION.get(url, timeout=30).text
        except Exception as exc:  # noqa: BLE001
            print("search fail", title, exc)
            continue
        ids = collect_album_ids_from_html(html)
        print("search", title, "ids", ids[:6])
        for aid in ids[:10]:
            album_url = f"https://open.spotify.com/album/{aid}"
            try:
                data = oembed(album_url)
            except Exception:
                continue
            ot = (data.get("title") or "").lower()
            # Prefer titles that look like the release
            tnorm = title.lower()
            if tnorm in ot or ot.startswith(tnorm[: min(8, len(tnorm))]):
                # Prefer artist mention when present
                return album_url
            time.sleep(0.15)
        # fallback: first id if any
        if ids:
            return f"https://open.spotify.com/album/{ids[0]}"
        time.sleep(0.3)
    return None


def discover_catalog() -> dict[str, str]:
    found: dict[str, str] = dict(KNOWN)
    pages = [
        ARTIST_URL,
        f"{ARTIST_URL}/discography/all",
        f"{ARTIST_URL}/discography/album",
        f"{ARTIST_URL}/discography/single",
    ]
    for page in pages:
        try:
            html = SESSION.get(page, timeout=30).text
        except Exception as exc:  # noqa: BLE001
            print("page fail", page, exc)
            continue
        for aid in collect_album_ids_from_html(html):
            url = f"https://open.spotify.com/album/{aid}"
            try:
                data = oembed(url)
            except Exception as exc:  # noqa: BLE001
                print("oembed fail", aid, exc)
                continue
            title = re.sub(
                r"\s+by\s+.*$", "", (data.get("title") or "").strip(), flags=re.I
            )
            found.setdefault(title, url)
            print("discog", title, url)
            time.sleep(0.2)
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
    tokens = set(re.sub(r"[&/]", " ", n).split())
    best = None
    best_score = 0
    for k, url in catalog.items():
        kn = set(re.sub(r"[&/]", " ", normalize(k)).split())
        score = len(tokens & kn)
        if score > best_score and score >= max(1, len(tokens) - 1):
            best_score = score
            best = url
    return best


def save_image(url: str, slug: str) -> dict:
    r = SESSION.get(url, timeout=60)
    r.raise_for_status()
    im = Image.open(BytesIO(r.content)).convert("RGB")
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
        "webp_b64": base64.b64encode(webp.read_bytes()).decode("ascii"),
    }


def main() -> None:
    catalog = discover_catalog()
    manifest = []

    for slug, title, year in RELEASES:
        url = match_url(title, catalog)
        if not url:
            url = search_album_url(title)
        entry = {
            "slug": slug,
            "title": title,
            "year": year,
            "spotify_url": url,
        }
        try:
            if not url or "/album/" not in url:
                raise RuntimeError(f"No album URL for {title}")
            data = oembed(url)
            thumb = data.get("thumbnail_url")
            if not thumb:
                raise RuntimeError("missing thumbnail_url")
            paths = save_image(thumb, slug)
            b64 = paths.pop("webp_b64")
            entry.update(
                {
                    "oembed_title": data.get("title"),
                    "thumbnail_url": thumb,
                    **paths,
                    "ok": True,
                }
            )
            # Emit machine-parseable payload for environments that cannot download artifacts
            print(f"COVER_B64_BEGIN:{slug}")
            print(b64)
            print(f"COVER_B64_END:{slug}")
            print("OK", slug, thumb, url)
        except Exception as exc:  # noqa: BLE001
            entry["ok"] = False
            entry["error"] = str(exc)
            print("FAIL", slug, exc)
        manifest.append(entry)
        time.sleep(0.25)

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
