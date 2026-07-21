"""Shared league normalization used across ETL and modeling."""

from __future__ import annotations

import re

LEAGUE_ALIASES = {
    "SM-liiga": "Liiga",
    "Swe-1": "HockeyAllsvenskan",
    "SweHL": "SHL",
    "Allsvenskan": "HockeyAllsvenskan",
    "Allsv": "HockeyAllsvenskan",
    "H-East": "NCAA",
    "H-EAST": "NCAA",
    "HE": "NCAA",
    "Hockey East": "NCAA",
    "WCHA": "NCAA",
    "Big-10": "NCAA",
    "B1G": "NCAA",
    "Big Ten": "NCAA",
    "BIG10": "NCAA",
    "CCHA": "NCAA",
    "AHA": "NCAA",
    "ECAC": "NCAA",
    "NCHC": "NCAA",
    "USNTDP": "USHL",
    "NTDP": "USHL",
    "NTDP - USHL": "USHL",
    "USDP": "USHL",
    "U.S. NTDP": "USHL",
    "U.S. National Under-18 Team": "USHL",
    "U.S. National U18 Team": "USHL",
    "Rus-MHL": "MHL",
    "Rus-VHL": "VHL",
    "Russia Jrs.": "Russia Jr.",
    "RUSSIA-JR.": "Russia Jr.",
    "Russia Junior": "Russia Jr.",
    "Russian Junior": "Russia Jr.",
    "Russia Jr": "Russia Jr.",
    "Russia U20": "Russia Jr.",
    "Swe-Jr": "Sweden Jrs.",
    "SWEDEN-JR.": "Sweden Jrs.",
    "Swe-Jr.": "Sweden Jrs.",
    "Sweden Jr.": "Sweden Jrs.",
    "Sweden U20": "Sweden Jrs.",
    "J20 Nationell": "Sweden Jrs.",
    "J20": "Sweden Jrs.",
    "J20 SuperElit": "Sweden Jrs.",
    "SuperElit": "Sweden Jrs.",
    "Fin-Jr": "Finland Jrs.",
    "FINLAND-JR.": "Finland Jrs.",
    "Fin-Jr.": "Finland Jrs.",
    "Finland Jr.": "Finland Jrs.",
    "U20 SM-sarja": "Finland Jrs.",
    "U20 SM-liiga": "Finland Jrs.",
    "Jr. A SM-liiga": "Finland Jrs.",
    "Czech Jr.": "Czech Jrs.",
    "Czech U20": "Czech Jrs.",
    "Czechia U20": "Czechia Jrs.",
    "Slovakia Jr.": "Slovakia Jrs.",
    "Slovakia U20": "Slovakia Jrs.",
    "Slovak U20": "Slovakia Jrs.",
    "Swiss Jr.": "Switzerland Jrs.",
    "Swiss U20": "Switzerland Jrs.",
    "U20-Elit": "Switzerland Jrs.",
    "Germany U20": "Germany Jrs.",
    "German Jr.": "Germany Jrs.",
    "Austria Jr.": "Austria Jrs.",
    "Belarus Jr.": "Belarus Jrs.",
    "NL": "National League",
    "NLA": "National League",
    "Swiss": "National League",
    "Swiss-2": "Swiss League",
    "Allsvenskan Norra": "HockeyAllsvenskan",
    "Allsvenskan Sodra": "HockeyAllsvenskan",
    "SWEDEN-2": "HockeyAllsvenskan",
    "Slovak": "Slovakia",
    "Czechia": "Czech",
    "Czechia Extraliga": "Czech Extraliga",
    "Czech Extraliga": "Czech Extraliga",
    "MHL-B": "MHL",
    "VHL-B": "VHL",
    "OHL Cup": "OHL",
    "WHL Cup": "WHL",
    "QMJHL Cup": "QMJHL",
    "USHS-MN": "High School",
    "USHS-Prep": "Prep School",
    "Ont. H.S.": "High School",
    "HIGH-MA": "High School",
    "HIGH-MN": "High School",
    "J18 Regional": "Sweden Jrs.",
    "U20 Region": "Sweden Jrs.",
}

LEAGUE_ALIASES_CASEFOLD = {
    re.sub(r"\s+", " ", alias).strip().casefold(): canonical
    for alias, canonical in LEAGUE_ALIASES.items()
}

PLAYOFF_HINTS = (
    "playoff",
    "playoffs",
    "postseason",
    "slutspel",
)


def normalize_league_name(league: str) -> str:
    value = clean_text(league)
    if not value:
        return "Unknown"
    return LEAGUE_ALIASES.get(value, LEAGUE_ALIASES_CASEFOLD.get(value.casefold(), value))


def infer_regular_season(*values: str) -> bool:
    normalized = " ".join(clean_text(value).lower() for value in values if clean_text(value))
    if not normalized:
        return True
    return not any(hint in normalized for hint in PLAYOFF_HINTS)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
