#!/usr/bin/env python3
"""Construit la version déployable du site The Cure Tours.

Principe :
- la base historique V3 reste dans site-template/index.html ;
- les données récentes sont lues depuis l'API officielle setlist.fm ;
- elles sont fusionnées uniquement dans le fichier de sortie (dist/index.html) ;
- aucune donnée API n'est écrite dans le dépôt/source.

Aucune dépendance externe : bibliothèque standard Python uniquement.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

API_ROOT = "https://api.setlist.fm/rest/1.0"
THE_CURE_MBID = "69ee3720-a7cb-4402-b48d-a02c366f2bcf"
DATA_RE = re.compile(
    r'(<script\s+id=["\']data-concerts["\']\s+type=["\']application/json["\']>)(.*?)(</script>)',
    re.IGNORECASE | re.DOTALL,
)


def log(message: str) -> None:
    print(f"[build] {message}", flush=True)


def normalize(value: Any) -> str:
    if value is None:
        return ""
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return re.sub(r"\s+", " ", s)


def parse_event_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%d-%m-%Y").date()


def iso_date(value: str) -> str:
    return parse_event_date(value).isoformat()


def weekday_english(value: str) -> str:
    return parse_event_date(value).strftime("%A")


def read_template(path: Path) -> tuple[str, list[dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    match = DATA_RE.search(text)
    if not match:
        raise RuntimeError("Bloc <script id=\"data-concerts\"> introuvable dans le template.")
    try:
        concerts = json.loads(match.group(2))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON concerts invalide dans le template : {exc}") from exc
    if not isinstance(concerts, list):
        raise RuntimeError("Le bloc data-concerts doit contenir une liste JSON.")
    return text, concerts


def inject_concerts(text: str, concerts: list[dict[str, Any]]) -> str:
    payload = json.dumps(concerts, ensure_ascii=False, separators=(",", ":"))
    # Évite qu'un titre improbable contenant </script> ferme la balise HTML.
    payload = payload.replace("</", "<\\/")
    replaced, count = DATA_RE.subn(lambda m: f"{m.group(1)}{payload}{m.group(3)}", text, count=1)
    if count != 1:
        raise RuntimeError("Impossible de remplacer data-concerts dans le template.")
    return replaced


def ensure_attribution(text: str) -> str:
    """Ajoute une attribution globale et une source dans la modale, sans changer les fonctions du site."""
    marker = "<!-- setlist.fm attribution injected by build_site.py -->"
    if marker not in text:
        old = '<div class="footer-note">\n  Outil généré pour exploration personnelle et recoupements — non affilié au groupe The Cure.\n</div>'
        new = '''<div class="footer-note">\n  Outil généré pour exploration personnelle et recoupements — non affilié au groupe The Cure.<br>\n  <span class="api-attribution">Données récentes synchronisées via <a href="https://www.setlist.fm/" target="_blank" rel="noopener">setlist.fm</a>.</span>\n</div>\n<!-- setlist.fm attribution injected by build_site.py -->'''
        if old in text:
            text = text.replace(old, new, 1)
        else:
            # Fallback : insertion avant la modale.
            text = text.replace('<!-- ============ TICKET MODAL ============ -->', new + '\n\n<!-- ============ TICKET MODAL ============ -->', 1)

    old_js = "document.getElementById('ticket-foot').innerHTML = `${esc(c.address)||''}`;"
    new_js = """document.getElementById('ticket-foot').innerHTML = `${esc(c.address)||''}${c.setlistFmUrl ? `${c.address ? '<br>' : ''}<span class=\"api-source\">Source : <a href=\"${esc(c.setlistFmUrl)}\" target=\"_blank\" rel=\"noopener\">setlist.fm</a></span>` : ''}`;"""
    if old_js in text:
        text = text.replace(old_js, new_js, 1)
    return text


class SetlistFmClient:
    def __init__(self, api_key: str, min_interval: float = 0.60, timeout: float = 25.0):
        self.api_key = api_key
        self.min_interval = max(min_interval, 0.52)  # reste sous 2 req/s
        self.timeout = timeout
        self._last_request = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        url = f"{API_ROOT}{path}?{query}"
        headers = {
            "Accept": "application/json",
            "X-Api-Key": self.api_key,
            "User-Agent": "the-cure-tours-github-pages/1.0",
        }
        last_error: Exception | None = None
        for attempt in range(1, 5):
            self._throttle()
            request = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    self._last_request = time.monotonic()
                    body = response.read().decode("utf-8")
                    return json.loads(body)
            except urllib.error.HTTPError as exc:
                self._last_request = time.monotonic()
                last_error = exc
                if exc.code == 429 or 500 <= exc.code < 600:
                    retry_after = exc.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 20)
                    log(f"API HTTP {exc.code}; nouvelle tentative dans {delay:.0f}s")
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"Erreur API setlist.fm HTTP {exc.code} sur {url}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                self._last_request = time.monotonic()
                last_error = exc
                if attempt < 4:
                    delay = min(2 ** attempt, 15)
                    log(f"Erreur réseau/API; nouvelle tentative dans {delay}s")
                    time.sleep(delay)
                    continue
        raise RuntimeError(f"Échec API après plusieurs tentatives : {last_error}")

    def artist_setlists_for_year(self, year: int) -> list[dict[str, Any]]:
        page = 1
        output: list[dict[str, Any]] = []
        while True:
            data = self.get_json(
                "/search/setlists",
                {"artistMbid": THE_CURE_MBID, "year": year, "p": page},
            )
            items = data.get("setlist") or []
            if not isinstance(items, list):
                raise RuntimeError("Réponse setlist.fm inattendue : 'setlist' n'est pas une liste.")
            output.extend(items)
            total = int(data.get("total") or len(output))
            per_page = int(data.get("itemsPerPage") or max(len(items), 1))
            log(f"setlist.fm {year}: page {page}, {len(items)} résultat(s), total annoncé {total}")
            if not items or page * per_page >= total:
                break
            page += 1
            # Garde-fou très large : on ne devrait jamais l'atteindre pour The Cure sur une seule année.
            if page > 50:
                raise RuntimeError("Pagination anormalement longue (>50 pages), arrêt de sécurité.")
        return output


def api_song_list(item: dict[str, Any]) -> list[dict[str, Any]]:
    sets = ((item.get("sets") or {}).get("set") or [])
    if not isinstance(sets, list):
        return []
    out: list[dict[str, Any]] = []
    main_pos = 0
    encore_positions: dict[int, int] = {}
    for set_obj in sets:
        if not isinstance(set_obj, dict):
            continue
        encore_raw = set_obj.get("encore")
        try:
            encore_no = int(encore_raw) if encore_raw not in (None, "") else None
        except (TypeError, ValueError):
            encore_no = None
        section = f"Encore {encore_no}" if encore_no else "Mainset"
        songs = set_obj.get("song") or []
        if not isinstance(songs, list):
            continue
        for song in songs:
            if not isinstance(song, dict) or song.get("tape") is True:
                continue
            name = str(song.get("name") or "").strip()
            if not name:
                continue
            if encore_no:
                encore_positions[encore_no] = encore_positions.get(encore_no, 0) + 1
                pos = encore_positions[encore_no]
            else:
                main_pos += 1
                pos = main_pos
            out.append({"section": section, "pos": pos, "song": name})
    # Sécurité explicite : Mainset avant Encore 1, Encore 2, etc.
    def sort_key(entry: dict[str, Any]) -> tuple[int, int]:
        section = str(entry.get("section") or "")
        if section == "Mainset":
            order = 0
        else:
            match = re.search(r"(\d+)", section)
            order = 100 + (int(match.group(1)) if match else 99)
        return order, int(entry.get("pos") or 0)
    return sorted(out, key=sort_key)


def api_to_patch(item: dict[str, Any]) -> dict[str, Any]:
    venue = item.get("venue") or {}
    city = venue.get("city") or {}
    country = city.get("country") or {}
    tour = item.get("tour") or {}
    event_date = str(item.get("eventDate") or "").strip()
    if not event_date:
        raise ValueError("Setlist API sans eventDate")
    songs = api_song_list(item)
    return {
        "date": iso_date(event_date),
        "year": parse_event_date(event_date).year,
        "city": city.get("name") or None,
        "venue": venue.get("name") or None,
        "country": country.get("name") or None,
        "tour": tour.get("name") or None,
        "dow": weekday_english(event_date),
        "apiSongs": songs,
        "setlistFmId": item.get("id") or None,
        "setlistFmVersionId": item.get("versionId") or None,
        "setlistFmUrl": item.get("url") or None,
        "setlistFmLastUpdated": item.get("lastUpdated") or None,
    }


def find_match(concerts: list[dict[str, Any]], patch: dict[str, Any]) -> dict[str, Any] | None:
    api_id = patch.get("setlistFmId")
    if api_id:
        for concert in concerts:
            if concert.get("setlistFmId") == api_id:
                return concert

    same_date = [c for c in concerts if c.get("date") == patch.get("date")]
    if not same_date:
        return None

    pv, pc = normalize(patch.get("venue")), normalize(patch.get("city"))
    exact = [c for c in same_date if normalize(c.get("venue")) == pv and normalize(c.get("city")) == pc]
    if len(exact) == 1:
        return exact[0]

    city_matches = [c for c in same_date if pc and normalize(c.get("city")) == pc]
    if len(city_matches) == 1:
        return city_matches[0]

    venue_matches = [c for c in same_date if pv and normalize(c.get("venue")) == pv]
    if len(venue_matches) == 1:
        return venue_matches[0]

    return same_date[0] if len(same_date) == 1 else None


def merge_api_items(concerts: list[dict[str, Any]], api_items: Iterable[dict[str, Any]]) -> dict[str, int]:
    stats = {"api": 0, "matched": 0, "created": 0, "setlists_updated": 0, "skipped": 0}
    next_id = max((int(c.get("id", -1)) for c in concerts), default=-1) + 1

    for item in api_items:
        stats["api"] += 1
        try:
            patch = api_to_patch(item)
        except (ValueError, TypeError) as exc:
            stats["skipped"] += 1
            log(f"Entrée API ignorée : {exc}")
            continue

        concert = find_match(concerts, patch)
        if concert is None:
            concert = {
                "id": next_id,
                "date": patch["date"],
                "year": patch["year"],
                "city": patch["city"],
                "venue": patch["venue"],
                "country": patch["country"],
                "event": None,
                "songsPlayed": None,
                "setLength": None,
                "setTime": None,
                "dow": patch["dow"],
                "tour": patch["tour"],
                "attendance": None,
                "capacity": None,
                "soldOut": False,
                "address": None,
                "setlist": [],
            }
            concerts.append(concert)
            next_id += 1
            stats["created"] += 1
        else:
            stats["matched"] += 1

        # Champs structurés que l'API sait fournir. On ne détruit pas une valeur locale avec du vide.
        for field in ("date", "year", "city", "venue", "country", "tour", "dow"):
            if patch.get(field) not in (None, ""):
                concert[field] = patch[field]

        # La setlist n'est remplacée que si setlist.fm fournit réellement des morceaux.
        api_songs = patch.pop("apiSongs", [])
        if api_songs:
            if concert.get("setlist") != api_songs:
                stats["setlists_updated"] += 1
            concert["setlist"] = api_songs
            concert["songsPlayed"] = len(api_songs)

        for field in ("setlistFmId", "setlistFmVersionId", "setlistFmUrl", "setlistFmLastUpdated"):
            if patch.get(field):
                concert[field] = patch[field]

    concerts.sort(key=lambda c: (str(c.get("date") or "9999-99-99"), int(c.get("id", 0))))
    return stats


def load_fixture(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("setlist") or [])
    if isinstance(data, list):
        return data
    raise RuntimeError("Fixture JSON invalide")


def build(template: Path, output: Path, api_key: str | None, years: int, fixture: Path | None = None) -> dict[str, int]:
    text, concerts = read_template(template)
    original_count = len(concerts)

    if fixture:
        api_items = load_fixture(fixture)
        log(f"Mode fixture : {len(api_items)} entrée(s) API locale(s)")
    elif api_key:
        client = SetlistFmClient(api_key)
        current_year = dt.datetime.now(dt.timezone.utc).year
        api_items = []
        for year in range(current_year - max(years, 1) + 1, current_year + 1):
            api_items.extend(client.artist_setlists_for_year(year))
    else:
        api_items = []
        log("Aucune clé API : déploiement de la base V3 sans synchronisation setlist.fm.")

    stats = merge_api_items(concerts, api_items)
    text = inject_concerts(text, concerts)
    text = ensure_attribution(text)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    stats["baseline"] = original_count
    stats["final"] = len(concerts)
    log(" | ".join(f"{k}={v}" for k, v in stats.items()))
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GitHub Pages avec synchronisation setlist.fm temporaire")
    parser.add_argument("--template", default="site-template/index.html")
    parser.add_argument("--output", default="dist/index.html")
    parser.add_argument("--years", type=int, default=int(os.getenv("SETLISTFM_REFRESH_YEARS", "2")))
    parser.add_argument("--fixture", help="Fixture JSON locale (tests, aucune requête réseau)")
    parser.add_argument("--no-api", action="store_true", help="Force la construction sans appel API")
    args = parser.parse_args()

    api_key = None if args.no_api else os.getenv("SETLISTFM_API_KEY")
    try:
        build(
            Path(args.template),
            Path(args.output),
            api_key=api_key,
            years=max(1, args.years),
            fixture=Path(args.fixture) if args.fixture else None,
        )
        return 0
    except Exception as exc:
        print(f"[build] ERREUR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
