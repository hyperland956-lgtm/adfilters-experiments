#!/usr/bin/env python3
"""
adfilters build script
Builds all output filter lists from upstream sources.
Run locally: python3 scripts/build.py
"""

import re
import json
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
            "ddg_tds_url":               "https://staticcdn.duckduckgo.com/trackerblocking/v6/current/extension-tds.json",
            "privacy_badger_seed":       "https://raw.githubusercontent.com/EFForg/privacybadger/master/src/data/seed.json",
            "privacy_badger_config":     "https://raw.githubusercontent.com/EFForg/privacybadger/master/src/data/pbconfig.json",
            "ghostery_trackerdb_url":    "https://github.com/ghostery/trackerdb/releases/latest/download/trackerdb.txt",
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
        "ghostery_complete_categories": ["advertising","site_analytics","pornvertising"],
        "ghostery_extended_extra_categories": ["customer_interaction","social_media","misc"],
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
DDG_OPT_PREV      = float(CONFIG["ddg_optimized_prevalence_threshold"])

GHOSTERY_COMPLETE_CATS  = set(CONFIG.get("ghostery_complete_categories", []))
GHOSTERY_EXTENDED_EXTRA = set(CONFIG.get("ghostery_extended_extra_categories", []))

PB_RISKY          = CONFIG["pb_risky_domain_patterns"]
PB_COMPLETE_EXTRA = CONFIG["pb_complete_extra_excluded_patterns"]

ADBLOCK.mkdir(parents=True, exist_ok=True)
DNS_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ── Helpers ───────────────────────────────────────────────────────────────────

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def fetch(url: str) -> set:
    log(f"Fetching {url}")
    req = urllib.request.Request(url, headers=HEADERS)
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
    if rule.startswith("@@"):
        return None
    m = re.match(r"^\|\|([a-zA-Z0-9\-\.]+)\^(\$(third-party|3p))?$", rule)
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
    Build adblock rules from EFF's Privacy Badger seed.json and pbconfig.json.

    We use pbconfig.json to gracefully handle the "yellowlist" (cookieblocking)
    and sitefixes since static adblock lists cannot support PB's click-to-play
    widgets or dynamic domain tracking overrides.
    """
    log("Fetching Privacy Badger seed...")
    req = urllib.request.Request(SOURCES["privacy_badger_seed"], headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        seed = json.loads(resp.read().decode("utf-8"))

    log("Fetching Privacy Badger config (pbconfig.json)...")
    req_cfg = urllib.request.Request(SOURCES.get("privacy_badger_config", "https://raw.githubusercontent.com/EFForg/privacybadger/master/src/data/pbconfig.json"), headers=HEADERS)
    with urllib.request.urlopen(req_cfg, timeout=120) as resp_cfg:
        pbconfig = json.loads(resp_cfg.read().decode("utf-8"))

    action_map = seed.get("action_map", {})
    blocked    = {d for d, v in action_map.items() if v.get("heuristicAction") == "block"}

    # Dynamically extract yellowlist (cookieblock) domains
    yellowlist = set(pbconfig.get("yellowlist", []))

    # Extract sitefixes exclusions
    sitefixes_ignore = pbconfig.get("sitefixes", {}).get("ignore", {})
    sitefixes_yellowlist = pbconfig.get("sitefixes", {}).get("yellowlist", {})

    for domains in sitefixes_ignore.values():
        yellowlist.update(domains)
    for domains in sitefixes_yellowlist.values():
        yellowlist.update(domains)

    rules = set()
    extra = PB_COMPLETE_EXTRA if mode == "complete" else []
    n_added = n_skip_risky = n_skip_yellow = 0

    for domain in sorted(blocked):
        domain = domain.lstrip(".").lower()
        if not domain or "." not in domain:
            continue

        if _is_risky_pb_domain(domain, extra):
            n_skip_risky += 1
            continue

        if domain in yellowlist:
            n_skip_yellow += 1
            continue

        # Use $third-party to mimic PB's cross-site-only blocking behavior
        safe_rules = {f"||{domain}^$third-party"}

        if mode == "optimized":
            pass
        elif mode == "complete":
            # Add known subdomains manually just in case
            if "google-analytics.com" in domain:
                safe_rules.add(f"||www.{domain}^$third-party")
                safe_rules.add(f"||ssl.{domain}^$third-party")

        rules.update(safe_rules)
        n_added += len(safe_rules)

    log(f"  PB {mode}: {n_added:,} rules ({n_skip_risky:,} SSO/risky skipped, {n_skip_yellow:,} yellowlist skipped)")
    return rules


# ── DDG Tracker Data Set ─────────────────────────────────────────────────────

def _ddg_regex_to_path(domain: str, pattern: str) -> str | None:
    """
    Convert a DDG TDS regex rule to an adblock path string (without options).

    DDG rules are regex patterns matched against full URLs. We extract the longest
    safe literal prefix before the first regex metacharacter. Patterns that are
    purely dynamic (long hashes, UUIDs, version strings) are discarded since they
    go stale quickly and cause false positives.

    Returns None if the pattern cannot be converted to a useful literal path.
    """
    if not pattern:
        return None

    pattern = pattern.strip().lstrip("^")

    if not pattern or pattern == "/":
        return None

    # Discard patterns whose first path segment looks like a hash or UUID
    if re.match(r"^/?[0-9a-f\-]{8,}", pattern):
        return None

    # Extract literal prefix up to the first regex metachar (except /)
    literal = ""
    for ch in pattern:
        if ch in r"\.+*?[](){}|^$":
            break
        literal += ch

    literal = literal.lstrip("/")
    if not literal:
        return None

    return f"||{domain}/{literal}"


def fetch_ddg_rules(mode: str) -> set:
    """
    Build adblock rules from the DDG Tracker Data Set (TDS).

    Single HTTP fetch of the compiled TDS JSON - the same file DDG browser
    extensions and Vivaldi use. Replaces the old sparse git clone approach.

    TDS default field semantics:
      block  : domain is a dedicated tracker; block as third-party;
               rules with action=ignore become @@ allowlist exceptions
      ignore : dual-use domain (Google, Facebook, CDNs); never block wholesale;
               only specific tracking paths get rules
      (none) : treated as ignore

    mode=extended  : all tracking categories + unknowns; block + path rules
    mode=complete  : same but drops Embedded Content and Social categories
    mode=optimized : safe categories only; default=block domains only; no path rules
    """
    log("Fetching DDG TDS...")
    req = urllib.request.Request(SOURCES["ddg_tds_url"], headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        tds = json.loads(resp.read().decode("utf-8"))

    trackers = tds.get("trackers", {})
    log(f"  TDS loaded: {len(trackers):,} tracker entries")

    rules = set()
    n_block = n_paths = n_exc = n_skip_cat = n_skip_complex = 0

    for domain, tracker in trackers.items():
        default   = tracker.get("default")
        cats      = set(tracker.get("categories") or [])
        tds_rules = tracker.get("rules") or []

        # Category filtering
        if mode == "optimized":
            if not (cats & DDG_SAFE_CATS):
                continue
        elif mode == "complete":
            if cats & DDG_EXCL_COMPLETE:
                n_skip_cat += 1
                continue
            if cats and not (cats & DDG_ALL_CATS):
                n_skip_cat += 1
                continue
        else:  # extended: tracking cat OR unknown (no categories)
            if cats and not (cats & DDG_ALL_CATS):
                n_skip_cat += 1
                continue

        if default == "block":
            rules.add(f"||{domain}^$third-party")
            n_block += 1
            for r in tds_rules:
                if r.get("action") != "ignore":
                    continue
                path = _ddg_regex_to_path(domain, r.get("rule", ""))
                if path:
                    rules.add(f"@@{path}^$third-party")
                    n_exc += 1

        elif mode != "optimized":
            # default=ignore or None: block only specific tracking paths
            for r in tds_rules:
                if r.get("action") == "ignore":
                    continue
                path = _ddg_regex_to_path(domain, r.get("rule", ""))
                if path:
                    rules.add(f"{path}^$third-party")
                    n_paths += 1
                else:
                    n_skip_complex += 1

    log(f"  DDG [{mode}]: {n_block:,} blocked domains | {n_paths:,} path rules | "
        f"{n_exc:,} exceptions | {n_skip_cat:,} skipped (category) | "
        f"{n_skip_complex:,} skipped (complex regex) | {len(rules):,} total")
    return rules


# ── Ghostery Tracker DB ───────────────────────────────────────────────────────

def fetch_ghostery_rules(mode: str) -> set:
    """
    Fetch the Ghostery Tracker DB pre-built adblock filter list from latest release.

    Two rule types per tracker entry:
      trackerdb_filter : precise rules, usually ||domain^$3p or path-specific
      trackerdb_domain : broader ||domain^ rules, but many are specific tracker
                         subdomains (e.g. ||track.funnelytics.io^) so both types
                         are included - Ghostery's categorization is trusted.

    mode=extended : all categories including customer_interaction, social_media, misc
    mode=complete : safe categories only (advertising, site_analytics, pornvertising)
    """
    allowed_cats = GHOSTERY_COMPLETE_CATS | (GHOSTERY_EXTENDED_EXTRA if mode == "extended" else set())

    log(f"Fetching Ghostery Tracker DB (mode={mode})...")
    req = urllib.request.Request(SOURCES["ghostery_trackerdb_url"], headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")

    rules       = set()
    current_cat = None
    skipped     = 0

    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("! trackerdb_"):
            m = re.search(r"trackerdb_category:([a-z_]+)", line)
            current_cat = m.group(1) if m else None
            continue
        if not line or not line.startswith("||"):
            continue
        if current_cat not in allowed_cats:
            skipped += 1
            continue
        rules.add(line)

    log(f"  Ghostery [{mode}]: {len(rules):,} rules kept, {skipped} lines skipped (category)")
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
        | fetch_ddg_rules(mode="extended")
        | fetch_privacy_badger_rules(mode="extended")
        | fetch_ghostery_rules(mode="extended")
    )
    write_both(
        "advanced_tracking_protection_extended",
        "Advanced Tracking Protection (Extended)",
        "AdGuard Tracking Protection, EasyPrivacy, AdGuard Mail Tracking, "
        "DDG TDS (all categories, path-precise rules), "
        "Ghostery Tracker DB (all categories), "
        "Privacy Badger (hard-blocked, light filter).",
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
        | fetch_ddg_rules(mode="complete")
        | fetch_privacy_badger_rules(mode="complete")
        | fetch_ghostery_rules(mode="complete")
    )
    write_both(
        "advanced_tracking_protection",
        "Advanced Tracking Protection",
        "AdGuard Tracking Protection, EasyPrivacy, AdGuard Mail Tracking, "
        "DDG TDS (excludes Embedded Content and Social, path-precise rules), "
        "Ghostery Tracker DB (advertising and analytics categories), "
        "Privacy Badger (hard-blocked, filtered).",
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
        | fetch_ddg_rules(mode="optimized")
    )
    write_both(
        "advanced_tracking_protection_optimized",
        "Advanced Tracking Protection (Optimized)",
        "AdGuard Tracking Protection (optimized), EasyPrivacy (optimized), "
        "AdGuard Mail Tracking (optimized), DDG TDS (safe categories, 1% prevalence). "
        "For DNS resolvers, routers, and mobile.",
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
