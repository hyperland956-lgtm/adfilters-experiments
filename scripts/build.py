#!/usr/bin/env python3
"""
adfilters build script
Builds all output filter lists from upstream sources.
Run locally: python3 scripts/build.py
"""

import re
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

try:
    import yaml
    with open(Path(__file__).parent.parent / "config.yml") as f:
        CONFIG = yaml.safe_load(f)
except ImportError:
    print("[build] WARNING: pyyaml not installed, using hardcoded fallback config")
    CONFIG = {
        "sources": {
            "adg_base_optimized":        "https://filters.adtidy.org/extension/ublock/filters/2_optimized.txt",
            "adg_base_without_easylist": "https://filters.adtidy.org/extension/ublock/filters/2_without_easylist.txt",
            "adg_tracking":              "https://filters.adtidy.org/extension/ublock/filters/3.txt",
            "adg_tracking_optimized":    "https://filters.adtidy.org/extension/ublock/filters/3_optimized.txt",
            "easyprivacy":               "https://filters.adtidy.org/extension/ublock/filters/118.txt",
            "easyprivacy_optimized":     "https://filters.adtidy.org/extension/ublock/filters/118_optimized.txt",
            "adg_mail":                  "https://filters.adtidy.org/extension/ublock/filters/25.txt",
            "adg_mail_optimized":        "https://filters.adtidy.org/extension/ublock/filters/25_optimized.txt",
            "ddg_tracker_radar_repo":    "https://github.com/duckduckgo/tracker-radar.git",
            "ddg_tracker_radar_regions": ["US","AU","CA","CH","DE","FR","GB","NL","NO"],
            "privacy_badger_seed":       "https://raw.githubusercontent.com/EFForg/privacybadger/master/src/data/seed.json",
        },
        "ddg_all_tracking_categories": [
            "Ad Motivated Tracking","Advertising","Analytics","Audience Measurement",
            "Action Pixels","Fingerprinting","Session Replay","Malware","Cryptomining",
            "Tracking","Ad Fraud","Email Tracking",
        ],
        "ddg_complete_excluded_categories": ["Embedded Content","Social"],
        "ddg_safe_categories": [
            "Advertising","Ad Motivated Tracking","Analytics","Audience Measurement",
            "Action Pixels","Fingerprinting","Session Replay","Malware","Cryptomining",
            "Ad Fraud","Email Tracking",
        ],
        "ddg_optimized_prevalence_threshold": 0.01,
        "pb_risky_domain_patterns": [
            ".azurefd.net",".cloudfront.net",".akamaized.net",".fastly.net",
            ".fastlylb.net",".edgekey.net",".edgesuite.net",
            "spotify.com","dropbox.com","twitch.tv","pinterest.com",
            "alicdn.com","aliyuncs.com","amazonaws.com","azure.com",
            "azurewebsites.net","windows.net",
        ],
        "pb_complete_extra_excluded_patterns": ["eventim.com","appconsent.io","api.","accounts."],
        "outputs": {"adblock_dir": "output/adblock", "dns_dir": "output/dns"},
        "metadata": {
            "author": "adfilters",
            "homepage": "https://github.com/cudios-dev/adfilters",
            "license": "MIT",
        },
    }

ROOT      = Path(__file__).parent.parent
ADBLOCK   = ROOT / CONFIG["outputs"]["adblock_dir"]
DNS_DIR   = ROOT / CONFIG["outputs"]["dns_dir"]
SOURCES   = CONFIG["sources"]
META      = CONFIG["metadata"]

DDG_ALL_CATS      = set(CONFIG["ddg_all_tracking_categories"])
DDG_EXCL_COMPLETE = set(CONFIG["ddg_complete_excluded_categories"])
DDG_SAFE_CATS     = set(CONFIG["ddg_safe_categories"])
DDG_REGIONS       = SOURCES["ddg_tracker_radar_regions"]
DDG_OPT_PREV      = float(CONFIG["ddg_optimized_prevalence_threshold"])

PB_RISKY          = CONFIG["pb_risky_domain_patterns"]
PB_COMPLETE_EXTRA = CONFIG["pb_complete_extra_excluded_patterns"]

ADBLOCK.mkdir(parents=True, exist_ok=True)
DNS_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def fetch(url: str) -> set:
    log(f"Fetching {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "adfilters/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    rules = set()
    for line in raw.splitlines():
        line = line.strip()
        if line and not line.startswith("!") and not line.startswith("#") and not line.startswith("["):
            rules.add(line)
    log(f"  -> {len(rules):,} rules")
    return rules


def is_valid_adblock_rule(rule: str) -> bool:
    if "%" in rule:
        return False
    if re.match(r"^\|\|[\.\*]?\^$", rule):
        return False
    return True


def extract_domain(rule: str):
    m = re.match(r"^\|\|([a-zA-Z0-9\-\.]+)\^$", rule)
    if not m:
        return None
    domain = m.group(1).lstrip("*").lstrip(".")
    if "." not in domain or "*" in domain:
        return None
    return domain.lower()


def deduplicate(rules: set) -> list:
    return sorted(r for r in rules if is_valid_adblock_rule(r))


def adblock_header(title: str, description: str, rule_count: int) -> str:
    return (
        f"[Adblock Plus 2.0]\n"
        f"! Title: {title}\n"
        f"! Description: {description}\n"
        f"! Version: {TIMESTAMP}\n"
        f"! Expires: 1 day (update frequency)\n"
        f"! Homepage: {META['homepage']}\n"
        f"! License: {META['license']}\n"
        f"! Rules: {rule_count:,}\n"
        f"!\n"
    )


def dns_header(title: str, rule_count: int) -> str:
    return (
        f"# Title: {title} (DNS/hosts format)\n"
        f"# Version: {TIMESTAMP}\n"
        f"# Homepage: {META['homepage']}\n"
        f"# Domains: {rule_count:,}\n"
        f"#\n"
    )


def write_adblock(filename: str, title: str, description: str, rules: set) -> None:
    clean = deduplicate(rules)
    path  = ADBLOCK / filename
    path.write_text(adblock_header(title, description, len(clean)) + "\n".join(clean) + "\n", encoding="utf-8")
    log(f"Written: {path} ({len(clean):,} rules)")


def write_dns(filename: str, title: str, rules: set) -> None:
    domains = sorted({d for r in rules if (d := extract_domain(r)) is not None})
    path    = DNS_DIR / filename
    path.write_text(dns_header(title, len(domains)) + "\n".join(f"0.0.0.0 {d}" for d in domains) + "\n", encoding="utf-8")
    log(f"Written: {path} ({len(domains):,} domains)")


def write_both(stem: str, title: str, description: str, rules: set) -> None:
    write_adblock(f"{stem}.txt", title, description, rules)
    write_dns(    f"{stem}.txt", title, rules)


# ── Privacy Badger ────────────────────────────────────────────────────────────

def _is_risky_pb_domain(domain: str, extra_patterns: list = None) -> bool:
    """
    Returns True if a domain matches any known risky pattern.
    Used to filter PB block entries that could break site functionality.
    """
    patterns = PB_RISKY + (extra_patterns or [])
    for pat in patterns:
        if domain == pat or domain.endswith(pat):
            return True
    return False


def fetch_privacy_badger_rules(mode: str) -> set:
    """
    Fetch Privacy Badger seed.json and return safe ||domain^ block rules.

    mode='extended' : block-only, light filter (exclude CDN/platform patterns)
    mode='complete' : block-only, heavy filter (light filter + extra risky patterns)

    cookieblock entries are never included - those are borderline functional domains
    (Spotify API, Dropbox, Twitch) that PB only strips cookies from, not fully blocks.
    We cannot replicate cookie-stripping in a filter list, so including them as full
    blocks would break those services.
    """
    log(f"Fetching Privacy Badger seed.json (mode={mode})...")
    req = urllib.request.Request(
        SOURCES["privacy_badger_seed"],
        headers={"User-Agent": "adfilters/1.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        seed = json.loads(resp.read().decode("utf-8"))

    action_map  = seed.get("action_map", {})
    snitch_map  = seed.get("snitch_map", {})

    # Only hard-blocked domains
    blocked = {d for d, v in action_map.items() if v.get("heuristicAction") == "block"}
    log(f"  PB raw block entries: {len(blocked):,}")

    extra = PB_COMPLETE_EXTRA if mode == "complete" else []

    safe_rules = set()
    skipped    = 0
    for domain in blocked:
        domain = domain.lstrip(".").lower()
        if not domain or "." not in domain:
            continue
        if _is_risky_pb_domain(domain, extra):
            skipped += 1
            continue
        # Complete mode: also require the domain to be confirmed cross-site
        # (present in snitch_map means PB saw it tracking on multiple unrelated sites)
        if mode == "complete" and domain not in snitch_map:
            skipped += 1
            continue
        safe_rules.add(f"||{domain}^")

    log(f"  PB [{mode}]: {len(safe_rules):,} rules kept, {skipped} skipped as risky")
    return safe_rules


# ── DDG Tracker Radar ─────────────────────────────────────────────────────────

def _ensure_ddg_clone() -> Path:
    """
    Sparse-clone or update DDG Tracker Radar, all configured regions.

    sparse-checkout set runs unconditionally every time - not just on fresh clone.
    This is required because GitHub Actions cache restores an existing directory,
    causing the clone branch to be skipped and the old sparse-checkout config
    (which may only have US) to persist. Running sparse-checkout set + pull
    every time ensures all regions are present regardless of cache state.
    """
    clone_dir   = ROOT / ".cache" / "tracker-radar"
    sparse_paths = [f"domains/{r}" for r in DDG_REGIONS]

    if not clone_dir.exists():
        log(f"Sparse-cloning DDG Tracker Radar ({len(DDG_REGIONS)} regions)...")
        clone_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "git", "clone", "--depth=1",
            "--filter=blob:none", "--sparse",
            SOURCES["ddg_tracker_radar_repo"], str(clone_dir),
        ], check=True)

    # Always update sparse-checkout config and pull.
    # On a cache restore this fetches any regions not in the cached checkout.
    log(f"Updating DDG sparse-checkout ({len(DDG_REGIONS)} regions)...")
    subprocess.run(
        ["git", "-C", str(clone_dir), "sparse-checkout", "set"] + sparse_paths,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(clone_dir), "pull", "--depth=1"],
        check=True,
    )

    return clone_dir


def build_ddg_rules(mode: str) -> set:
    """
    Convert DDG Tracker Radar JSON files into adblock rules.

    mode='extended':
      - All tracking categories + unknown (no-category) domains
      - All regions, subdomains included, no prevalence threshold
      - Most comprehensive, catches the most trackers

    mode='complete':
      - Same as extended but excludes 'Embedded Content' and 'Social' categories
      - These two are the most site-breaking DDG categories:
        Embedded Content = YouTube/Vimeo iframes, comment widgets
        Social = social login buttons, share widgets
      - Still includes unknowns and all other tracking categories

    mode='optimized':
      - Safe categories only (no Embedded Content, Social, CDN, Badge, etc.)
      - prevalence >= 1% (high-confidence trackers only)
      - Subdomains skipped (||domain^ covers them in standard adblock parsers)
      - Smallest and safest output
    """
    clone_dir = _ensure_ddg_clone()

    if mode == "extended":
        categories    = DDG_ALL_CATS
        prev_thresh   = 0.0
        include_unknowns  = True
        include_subdomains = True
    elif mode == "complete":
        categories    = DDG_ALL_CATS - DDG_EXCL_COMPLETE
        prev_thresh   = 0.0
        include_unknowns  = True
        include_subdomains = True
    else:  # optimized
        categories    = DDG_SAFE_CATS
        prev_thresh   = DDG_OPT_PREV
        include_unknowns  = False
        include_subdomains = False

    rules       = set()
    total_files = 0
    total_kept  = 0

    for region in DDG_REGIONS:
        region_path = clone_dir / "domains" / region
        if not region_path.exists():
            log(f"  WARNING: missing region path {region_path}")
            continue

        files = list(region_path.glob("*.json"))
        total_files += len(files)

        for fpath in files:
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
            except Exception:
                continue

            domain     = data.get("domain", "").strip()
            cats       = set(data.get("categories") or [])
            prevalence = float(data.get("prevalence") or 0.0)

            if not domain:
                continue
            if prevalence < prev_thresh:
                continue

            if mode == "optimized":
                # Must have at least one safe category. No unknowns.
                if not (cats & categories):
                    continue

            elif mode == "complete":
                # Exclude if domain carries ANY risky category, even alongside tracking ones.
                # e.g. a domain tagged [Embedded Content, Analytics] is excluded.
                if cats & DDG_EXCL_COMPLETE:
                    continue
                # Still require at least one tracking category OR unknown
                if cats and not (cats & categories):
                    continue

            else:  # extended
                # Include if any tracking category matches, OR unknown (no categories)
                if cats and not (cats & categories):
                    continue

            rules.add(f"||{domain}^")
            total_kept += 1

            if include_subdomains:
                for sub in data.get("subdomains") or []:
                    sub = sub.lstrip("*").lstrip(".")
                    if sub:
                        rules.add(f"||{sub}.{domain}^")

    log(f"DDG [{mode}]: {total_files:,} files / {len(DDG_REGIONS)} regions -> {total_kept:,} domains, {len(rules):,} rules")
    return rules


# ── Build targets ─────────────────────────────────────────────────────────────

def build_2_without_easylist_optimized() -> None:
    """
    Intersection of AdGuard Base (optimized) and AdGuard Base (without EasyList).
    Contains only the AdGuard-authored rules that also survived AdGuard's optimization pass.
    Use alongside EasyList. Do NOT combine with the default AdGuard Base filter.
    """
    log("=== Building: 2_without_easylist_optimized ===")
    result = fetch(SOURCES["adg_base_optimized"]) & fetch(SOURCES["adg_base_without_easylist"])
    write_both(
        "2_without_easylist_optimized",
        "AdGuard Base Filter - Without EasyList (Optimized)",
        "Intersection of AdGuard Base (optimized) and AdGuard Base (without EasyList). "
        "Use alongside EasyList. Do not combine with the default AdGuard Base filter.",
        result,
    )


def build_advanced_tracking_protection_extended() -> None:
    """
    Extended variant - most comprehensive, for users who want maximum coverage
    and accept slightly more risk of occasional site breakage.

    Sources:
      - AdGuard Tracking Protection (full)
      - EasyPrivacy (full)
      - AdGuard Mail Tracking Protection (full)
      - DDG Tracker Radar: all categories + unknowns, all regions, with subdomains
      - Privacy Badger: hard-blocked domains only, light filter applied
    """
    log("=== Building: Advanced Tracking Protection (Extended) ===")
    result = (
        fetch(SOURCES["adg_tracking"])
        | fetch(SOURCES["easyprivacy"])
        | fetch(SOURCES["adg_mail"])
        | build_ddg_rules(mode="extended")
        | fetch_privacy_badger_rules(mode="extended")
    )
    write_both(
        "advanced_tracking_protection_extended",
        "Advanced Tracking Protection (Extended)",
        "Maximum coverage variant. AdGuard Tracking Protection, EasyPrivacy, AdGuard Mail "
        "Tracking, DDG Tracker Radar (all regions, all categories, with subdomains), and "
        "Privacy Badger hard-blocked domains (light filter). "
        "May occasionally break sites with heavy third-party embeds.",
        result,
    )


def build_advanced_tracking_protection_complete() -> None:
    """
    Complete variant (default) - strong coverage with reduced breakage risk.

    Sources:
      - AdGuard Tracking Protection (full)
      - EasyPrivacy (full)
      - AdGuard Mail Tracking Protection (full)
      - DDG Tracker Radar: excludes Embedded Content + Social categories, all regions, with subdomains
      - Privacy Badger: hard-blocked domains only, heavy filter applied
    """
    log("=== Building: Advanced Tracking Protection (Complete) ===")
    result = (
        fetch(SOURCES["adg_tracking"])
        | fetch(SOURCES["easyprivacy"])
        | fetch(SOURCES["adg_mail"])
        | build_ddg_rules(mode="complete")
        | fetch_privacy_badger_rules(mode="complete")
    )
    write_both(
        "advanced_tracking_protection",
        "Advanced Tracking Protection",
        "Default variant. AdGuard Tracking Protection, EasyPrivacy, AdGuard Mail Tracking, "
        "DDG Tracker Radar (all regions, excludes Embedded Content and Social categories), "
        "and Privacy Badger hard-blocked domains (heavy filter, confirmed cross-site trackers only). "
        "Balanced coverage with low breakage risk.",
        result,
    )


def build_advanced_tracking_protection_optimized() -> None:
    """
    Optimized variant - smallest and safest, for performance-constrained environments
    (DNS resolvers, mobile, router-level blocking).

    Sources:
      - AdGuard Tracking Protection (optimized CDN endpoint)
      - EasyPrivacy (full, no optimized variant exists)
      - AdGuard Mail Tracking Protection (optimized CDN endpoint)
      - DDG Tracker Radar: safe categories only, 1% prevalence, no subdomains
      - Privacy Badger: NOT included (optimized list stays minimal)
    """
    log("=== Building: Advanced Tracking Protection (Optimized) ===")
    result = (
        fetch(SOURCES["adg_tracking_optimized"])
        | fetch(SOURCES["easyprivacy_optimized"])
        | fetch(SOURCES["adg_mail_optimized"])
        | build_ddg_rules(mode="optimized")
    )
    write_both(
        "advanced_tracking_protection_optimized",
        "Advanced Tracking Protection (Optimized)",
        "Lean variant for DNS/router/mobile use. AdGuard Tracking Protection (optimized), "
        "EasyPrivacy, AdGuard Mail Tracking (optimized), DDG Tracker Radar (safe categories "
        "only, 1% prevalence threshold, no subdomains). No Privacy Badger rules.",
        result,
    )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    log(f"Build started at {TIMESTAMP}")
    build_2_without_easylist_optimized()
    build_advanced_tracking_protection_extended()
    build_advanced_tracking_protection_complete()
    build_advanced_tracking_protection_optimized()
    log("All builds complete.")


if __name__ == "__main__":
    main()
