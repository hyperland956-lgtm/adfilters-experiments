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
            "adg_mail":                  "https://filters.adtidy.org/extension/ublock/filters/25.txt",
            "adg_mail_optimized":        "https://filters.adtidy.org/extension/ublock/filters/25_optimized.txt",
            "ddg_tracker_radar_repo":    "https://github.com/duckduckgo/tracker-radar.git",
            "ddg_tracker_radar_regions": ["US","AU","CA","CH","DE","FR","GB","NL","NO"],
        },
        "ddg_all_tracking_categories": [
            "Ad Motivated Tracking","Advertising","Analytics","Audience Measurement",
            "Action Pixels","Fingerprinting","Session Replay","Malware","Cryptomining",
            "Tracking","Ad Fraud","Email Tracking",
        ],
        "ddg_safe_categories": [
            "Advertising","Ad Motivated Tracking","Analytics","Audience Measurement",
            "Action Pixels","Fingerprinting","Session Replay","Malware","Cryptomining",
            "Ad Fraud","Email Tracking",
        ],
        "ddg_optimized_prevalence_threshold": 0.01,
        "outputs": {"adblock_dir": "output/adblock", "dns_dir": "output/dns"},
        "metadata": {"author": "adfilters", "homepage": "https://github.com/YOUR_USERNAME/adfilters", "license": "MIT"},
    }

ROOT      = Path(__file__).parent.parent
ADBLOCK   = ROOT / CONFIG["outputs"]["adblock_dir"]
DNS_DIR   = ROOT / CONFIG["outputs"]["dns_dir"]
SOURCES   = CONFIG["sources"]
META      = CONFIG["metadata"]

DDG_ALL_CATS  = set(CONFIG["ddg_all_tracking_categories"])
DDG_SAFE_CATS = set(CONFIG["ddg_safe_categories"])
DDG_REGIONS   = SOURCES["ddg_tracker_radar_regions"]
DDG_OPT_PREV  = float(CONFIG["ddg_optimized_prevalence_threshold"])

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

# ── DDG Tracker Radar ─────────────────────────────────────────────────────────

def _ensure_ddg_clone() -> Path:
    """Sparse-clone or update DDG Tracker Radar, all regions."""
    clone_dir = ROOT / ".cache" / "tracker-radar"

    if clone_dir.exists():
        log("DDG cache exists, pulling latest...")
        subprocess.run(["git", "-C", str(clone_dir), "pull", "--depth=1"], check=True)
    else:
        log(f"Sparse-cloning DDG Tracker Radar (regions: {', '.join(DDG_REGIONS)})...")
        clone_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "git", "clone", "--depth=1",
            "--filter=blob:none", "--sparse",
            SOURCES["ddg_tracker_radar_repo"], str(clone_dir),
        ], check=True)
        # Checkout all regions at once
        sparse_paths = [f"domains/{r}" for r in DDG_REGIONS]
        subprocess.run(
            ["git", "-C", str(clone_dir), "sparse-checkout", "set"] + sparse_paths,
            check=True,
        )

    return clone_dir


def build_ddg_rules(optimized: bool = False) -> set:
    """
    Build DDG tracker rules from all configured regions.

    Full list   (optimized=False):
      - All tracking categories + unknown (no-category) domains
      - No prevalence filter
      - Subdomains included

    Optimized   (optimized=True):
      - Safe categories only (excludes Embedded Content, Social, CDN, etc.)
      - prevalence >= ddg_optimized_prevalence_threshold (default 1%)
      - Subdomains skipped (||domain^ covers them in most adblockers anyway)
    """
    clone_dir   = _ensure_ddg_clone()
    categories  = DDG_SAFE_CATS if optimized else DDG_ALL_CATS
    prev_thresh = DDG_OPT_PREV  if optimized else 0.0
    label       = "optimized" if optimized else "full"

    rules        = set()
    total_files  = 0
    total_kept   = 0

    for region in DDG_REGIONS:
        region_path = clone_dir / "domains" / region
        if not region_path.exists():
            log(f"  WARNING: region path missing: {region_path}")
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

            # Prevalence gate (optimized only)
            if prevalence < prev_thresh:
                continue

            # Category gate
            if optimized:
                # Strict: must have at least one safe category, no unknowns
                if not (cats & categories):
                    continue
            else:
                # Full: any tracking category OR unknown (no category)
                if cats and not (cats & categories):
                    continue  # has categories but none are tracking = skip

            rules.add(f"||{domain}^")
            total_kept += 1

            # Subdomains: full list only
            if not optimized:
                for sub in data.get("subdomains") or []:
                    sub = sub.lstrip("*").lstrip(".")
                    if sub:
                        rules.add(f"||{sub}.{domain}^")

    log(f"DDG [{label}]: scanned {total_files:,} files across {len(DDG_REGIONS)} regions, kept {total_kept:,} domains -> {len(rules):,} rules")
    return rules

# ── Build targets ─────────────────────────────────────────────────────────────

def build_2_without_easylist_optimized() -> None:
    """
    2_without_easylist_optimized = 2_optimized INTERSECT 2_without_easylist
    AdGuard Base rules that survived optimization AND are not from EasyList.
    Pair with EasyList. Do NOT use alongside the default AdGuard Base filter.
    """
    log("=== Building: 2_without_easylist_optimized ===")
    opt   = fetch(SOURCES["adg_base_optimized"])
    wo_el = fetch(SOURCES["adg_base_without_easylist"])

    write_both(
        "2_without_easylist_optimized",
        "AdGuard Base Filter - Without EasyList (Optimized)",
        "Intersection of AdGuard Base (optimized) and AdGuard Base (without EasyList). "
        "Use alongside EasyList. Do not combine with the default AdGuard Base filter.",
        opt & wo_el,
    )


def build_advanced_tracking_protection(optimized: bool = False) -> None:
    """
    Advanced Tracking Protection = union of:
      AdGuard Tracking Protection + EasyPrivacy + AdGuard Mail Tracking + DDG Tracker Radar (all regions)

    Full variant:   all tracking categories, all regions, subdomains included, no prevalence gate
    Optimized:      safe categories only, 1% prevalence threshold, no subdomains
    """
    suffix = "_optimized" if optimized else ""
    label  = " (Optimized)" if optimized else ""
    log(f"=== Building: Advanced Tracking Protection{label} ===")

    tracking_key = "adg_tracking_optimized" if optimized else "adg_tracking"
    mail_key     = "adg_mail_optimized"     if optimized else "adg_mail"

    result = (
        fetch(SOURCES[tracking_key])
        | fetch(SOURCES["easyprivacy"])
        | fetch(SOURCES[mail_key])
        | build_ddg_rules(optimized=optimized)
    )

    write_both(
        f"advanced_tracking_protection{suffix}",
        f"Advanced Tracking Protection{label}",
        "Union of AdGuard Tracking Protection, EasyPrivacy, AdGuard Mail Tracking Protection, "
        "and DDG Tracker Radar (all regions). Deduplicated. "
        + ("Full coverage including all tracking categories and subdomains."
           if not optimized else
           "Safe categories only (1% prevalence threshold). Avoids rules known to break sites."),
        result,
    )

# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    log(f"Build started at {TIMESTAMP}")
    build_2_without_easylist_optimized()
    build_advanced_tracking_protection(optimized=False)
    build_advanced_tracking_protection(optimized=True)
    log("All builds complete.")


if __name__ == "__main__":
    main()
