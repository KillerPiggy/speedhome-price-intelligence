"""
areas.py — area / apartment autocomplete index.
Indeks saran otomatis untuk area & apartemen (dropdown suggestion).

Powers requirement #1: typing "Mont" surfaces Mont Kiara, Mont Kiara Aman,
Mont Kiara Bayu, ... The index is intentionally broad and easy to extend.
"""

from __future__ import annotations

import re

BASE_URL = "https://speedhome.com"


def _slug(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-")


# Top-level areas (broad search targets)
AREAS = [
    "Mont Kiara", "KLCC", "Bangsar", "Bangsar South", "Cyberjaya",
    "Petaling Jaya", "Kuala Lumpur", "Cheras", "Puchong", "Subang Jaya",
    "Ampang", "Bukit Bintang", "Shah Alam", "Bandar Sunway", "Penang",
    "Johor Bahru", "Kota Damansara", "Damansara", "Sentul", "Setapak",
    "Wangsa Maju", "Old Klang Road", "Sri Petaling", "Bukit Jalil",
    "Kepong", "Desa ParkCity", "Ara Damansara", "Kelana Jaya",
]

# Named buildings / apartments (precise targets). Heavy on Mont Kiara so the
# spec's "type Mont -> many suggestions" example works out of the box.
APARTMENTS = [
    # Mont Kiara
    "Mont Kiara Aman", "Mont Kiara Bayu", "Mont Kiara Pelangi",
    "Mont Kiara Astana", "Mont Kiara Damai", "Mont Kiara Meridin",
    "Mont Kiara Sophia", "10 Mont Kiara", "11 Mont Kiara",
    "Seni Mont Kiara", "Verve Suites Mont Kiara", "Arcoris Mont Kiara",
    "Arte Mont Kiara", "Residensi 22 Mont Kiara", "Kiara 163",
    "Pavilion Hilltop", "Sunway Mont Residences", "Kiaramas Ayuria",
    "Kiaramas Sutera", "i-Zen Kiara", "Ceriaan Kiara", "Solaris Mont Kiara",
    "Gateway Kiaramas", "Hijauan Kiara", "Aman Kiara",
    # KLCC
    "Soho Suites KLCC", "Vortex KLCC", "Setia Sky Residences",
    "The Binjai on the Park", "Marc Residence", "K Residence",
    "Pavilion Residences", "Stonor 3", "One KL", "8 Conlay",
    "The Ruma", "Quadro Residences",
    # Bangsar / Bangsar South
    "One Menerung", "The Establishment", "Park Residences",
    "Saville @ The Park", "Pantai Hillpark", "Cornerstone",
    "The Horizon Bangsar South", "Vogue Suites One",
    # Cyberjaya
    "The Place Cyberjaya", "Tamarind Suites", "Third Avenue",
    "Domain NeoCyber", "Mutiara Ville", "Sejati Residences", "Aera Cyberjaya",
    # Petaling Jaya
    "Tropicana Gardens", "Emporis Kota Damansara", "Paisley Tropicana",
    "The Westside Two", "Greenfield Residence", "Empire Damansara",
]


def _entry(label: str, kind: str) -> dict:
    slug = _slug(label)
    return {"label": label, "slug": slug, "kind": kind, "url": f"{BASE_URL}/rent/{slug}"}


# Precomputed index (areas first so they rank above buildings on ties).
INDEX = [_entry(a, "area") for a in AREAS] + [_entry(a, "apartment") for a in APARTMENTS]


def suggest(query: str, limit: int = 8) -> list[dict]:
    """Return up to `limit` autocomplete suggestions for `query`."""
    q = (query or "").strip().lower()
    if not q:
        return INDEX[:limit]

    starts, contains = [], []
    for item in INDEX:
        label = item["label"].lower()
        if label.startswith(q):
            starts.append(item)
        elif q in label:
            contains.append(item)
    # areas rank above apartments within each bucket
    starts.sort(key=lambda x: x["kind"] != "area")
    contains.sort(key=lambda x: x["kind"] != "area")
    return (starts + contains)[:limit]


def all_labels() -> list[str]:
    return [i["label"] for i in INDEX]
