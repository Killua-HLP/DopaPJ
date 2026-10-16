import re
from urllib.parse import urlsplit


def anilist_id_from_source_url(source_url: str | None) -> int | None:
    if not source_url:
        return None
    parsed = urlsplit(source_url)
    if parsed.hostname not in {"anilist.co", "www.anilist.co"}:
        return None
    match = re.fullmatch(r"/anime/(\d+)/?", parsed.path)
    return int(match.group(1)) if match else None
