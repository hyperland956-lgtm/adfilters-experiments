#!/usr/bin/env python3
"""
adfilters build script
Builds all output filter lists from upstream sources.
Run locally: python3 scripts/build.py
"""

import os
import re
import sys
import json
import shutil
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
    # Fallback if pyyaml not installed - hardcoded mirrors of config.yml
    CONFIG = {
        "sources": {
            "adg_base_optimized":        "https://filters.adtidy.org/extension/ublock/filters/2_optimized.txt",
            "adg_base_without_easylist": "https://filters.adtidy.org/extension/ublock/filters/2_without_easylist.txt",
            "adg_tracking":              "https://filters.adtidy.org/extension/ublock/filters/3.txt",
            "adg_tracking_optimized":    "https://filters.adtidy.org/extension/ublock/filters/3_optimized.txt",
            "easyprivacy":               "https://filters.adtidy.org/extension/ublock/filters/118.txt",
            "adg_mail":                  "https://filters.adtidy.org/extension/ublock/filters/25.txt",
            "adg_mail_optimized":        "https://filters.adtidy.org/extension/ublock/filters/25_optimized.txt",
            "ddg_tracker_radar_repo":    "https://github.com/duckduckgo/tracker-radar.git",
            "ddg_tracker_radar_region":  "US",
        },
        "ddg_tracking_categories": [
            "Ad Motivated Tracking", "Advertising", "Analytics",
            "Audience Measurement", "Action Pixels", "Fingerprinting",
            "Session Replay", "Malware", "Cryptomining", "Tracking",
            "Ad Fraud", "Email Tracking",
        ],
        "outputs": {
            "adblock_dir": "output/adblock",
            "dns_dir":     "output/dns",
        },
        "metadata": {
            "author":   "adfilters",
            "homepage": "https://github.com/shubham/adfilters",
            "license":  "MIT",
        },
    }

ROOT      = Path(__file__).parent.parent
ADBLOCK   = ROOT / CONFIG["outputs"]["adblock_dir"]
DNS_DIR   = ROOT / CONFIG["outputs"]["dns_dir"]
SOURCES   = CONFIG["sources"]
META      = CONFIG["metadata"]
DDG_CATS  = set(CONFIG["ddg_tracking_categories"])

ADBLOCK.mkdir(parents=True, exist_ok=True)
DNS_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def fetch(url: str) -> set[str]:
    """Fetch a filter list URL and return a set of active rules."""
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
    """
    Drop rules that are clearly malformed or unparseable outside AdGuard context.
    Keeps: network rules, cosmetic rules, exception rules, scriptlets.
    Drops: URL-encoded garbage, empty domain patterns.
    """
    if "%" in rule:
        return False
    if re.match(r"^\|\|[\.\*]?\^$", rule):
        return False
    return True


def extract_domain(rule: str) -> str | None:
    """
    Extract a plain domain from a network rule like ||domain^
    Returns None if the rule cannot be expressed as a bare domain.
    Skips rules with paths, query strings, regex, or options that are too specific.
    """
    # Only handle simple ||domain^ or ||domain^ with no modifiers
    m = re.match(r"^\|\|([a-zA-Z0-9\-\.]+)\^$", rule)
    if not m:
        return None
    domain = m.group(1).lstrip("*").lstrip(".")
    # Must have at least one dot and no wildcards
    if "." not in domain or "*" in domain:
        return None
    return domain.lower()


def deduplicate(rules: set[str]) -> list[str]:
    """Return sorted, deduplicated list of valid rules."""
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


def write_adblock(filename: str, title: str, description: str, rules: set[str]) -> None:
    clean = deduplicate(rules)
    header = adblock_header(title, description, len(clean))
    path = ADBLOCK / filename
    path.write_text(header + "\n".join(clean) + "\n", encoding="utf-8")
    log(f"Written: {path} ({len(clean):,} rules)")


def write_dns(filename: str, title: str, rules: set[str]) -> None:
    domains = sorted({
        d for r in rules
        if (d := extract_domain(r)) is not None
    })
    header = dns_header(title, len(domains))
    lines = "\n".join(f"0.0.0.0 {d}" for d in domains)
    path = DNS_DIR / filename
    path.write_text(header + lines + "\n", encoding="utf-8")
    log(f"Written: {path} ({len(domains):,} domains)")


def write_both(filename_stem: str, title: str, description: str, rules: set[str]) -> None:
    write_adblock(f"{filename_stem}.txt",     title, description, rules)
    write_dns(    f"{filename_stem}.txt",     title, rules)

# ── DDG Tracker Radar ─────────────────────────────────────────────────────────

def build_ddg_rules() -> set[str]:
    """
    Sparse-clone the DDG Tracker Radar repo (domains/US only) and
    convert tracking domains to ||domain^ adblock rules.
    """
    repo_url  = SOURCES["ddg_tracker_radar_repo"]
    region    = SOURCES["ddg_tracker_radar_region"]
    clone_dir = ROOT / ".cache" / "tracker-radar"

    if clone_dir.exists():
        log("DDG cache exists, pulling latest...")
        subprocess.run(["git", "-C", str(clone_dir), "pull", "--depth=1"], check=True)
    else:
        log("Sparse-cloning DDG Tracker Radar (domains only)...")
        clone_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "git", "clone", "--depth=1",
            "--filter=blob:none",
            "--sparse",
            repo_url, str(clone_dir),
        ], check=True)
        subprocess.run([
            "git", "-C", str(clone_dir),
            "sparse-checkout", "set", f"domains/{region}",
        ], check=True)

    domains_path = clone_dir / "domains" / region
    if not domains_path.exists():
        log(f"ERROR: DDG domains path not found: {domains_path}")
        return set()

    rules = set()
    files = list(domains_path.glob("*.json"))
    log(f"Processing {len(files):,} DDG domain files...")

    for fpath in files:
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue

        cats   = set(data.get("categories") or [])
        domain = data.get("domain", "").strip()
        if not domain:
            continue

        is_tracker = bool(cats & DDG_CATS) or not cats

        if is_tracker:
            rules.add(f"||{domain}^")
            for sub in data.get("subdomains") or []:
                sub = sub.lstrip("*").lstrip(".")
                if sub:
                    rules.add(f"||{sub}.{domain}^")

    log(f"DDG rules generated: {len(rules):,}")
    return rules

# ── Build targets ─────────────────────────────────────────────────────────────

def build_2_without_easylist_optimized() -> None:
    """
    2_without_easylist_optimized = 2_optimized INTERSECT 2_without_easylist
    This set contains AdGuard Base rules that both survived optimization
    AND are not sourced from EasyList - the cleanest non-redundant base.
    """
    log("=== Building: 2_without_easylist_optimized ===")
    opt   = fetch(SOURCES["adg_base_optimized"])
    wo_el = fetch(SOURCES["adg_base_without_easylist"])
    result = opt & wo_el

    write_both(
        "2_without_easylist_optimized",
        "AdGuard Base Filter - Without EasyList (Optimized)",
        (
            "Intersection of AdGuard Base (optimized) and AdGuard Base (without EasyList). "
            "Use alongside EasyList/uBlock Origin defaults. Do not use with AdGuard Base filter."
        ),
        result,
    )


def build_advanced_tracking_protection(optimized: bool = False) -> None:
    """
    Advanced Tracking Protection = union of:
      - AdGuard Tracking Protection (3 or 3_optimized)
      - EasyPrivacy (118)
      - AdGuard Mail Tracking Protection (25 or 25_optimized)
      - DDG Tracker Radar (fresh, US)
    All deduplicated.
    """
    suffix = "_optimized" if optimized else ""
    label  = " (Optimized)" if optimized else ""
    log(f"=== Building: Advanced Tracking Protection{label} ===")

    tracking_key = "adg_tracking_optimized" if optimized else "adg_tracking"
    mail_key     = "adg_mail_optimized"     if optimized else "adg_mail"

    f_tracking = fetch(SOURCES[tracking_key])
    f_privacy  = fetch(SOURCES["easyprivacy"])
    f_mail     = fetch(SOURCES[mail_key])
    f_ddg      = build_ddg_rules()

    result = f_tracking | f_privacy | f_mail | f_ddg

    stem = f"advanced_tracking_protection{suffix}"
    write_both(
        stem,
        f"Advanced Tracking Protection{label}",
        (
            "Union of AdGuard Tracking Protection, EasyPrivacy, AdGuard Mail Tracking "
            "Protection, and DDG Tracker Radar (US). Deduplicated. "
            "Covers trackers, fingerprinting, email pixels, and analytics."
        ),
        result,
    )

# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    log(f"Build started at {TIMESTAMP}")
    log(f"Output: adblock -> {ADBLOCK}, dns -> {DNS_DIR}")

    build_2_without_easylist_optimized()
    build_advanced_tracking_protection(optimized=False)
    build_advanced_tracking_protection(optimized=True)

    log("All builds complete.")


if __name__ == "__main__":
    main()
