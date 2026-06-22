# adfilters

Custom filter lists built automatically from upstream sources. Mainly focused on Adblock/Tracking.

---

## Filter Lists

### AdGuard Base - Without EasyList (Optimized)

The intersection of AdGuard Base (optimized) and AdGuard Base (without EasyList). Contains only the AdGuard-authored rules that also survived AdGuard's optimization pass, with zero EasyList overlap.

Use this **instead of** the default AdGuard Base filter. Pair it with EasyList (already included in most adblockers by default). You get full AdGuard coverage with zero rule duplication.

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/adblock/2_without_easylist_optimized.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/dns/2_without_easylist_optimized.txt` |

---

### Advanced Tracking Protection

Three variants with increasing trade-offs between coverage and caution.

#### Complete (default)

Strong coverage with low breakage risk. The right choice for most users.

Sources:
- AdGuard Tracking Protection (filter 3)
- EasyPrivacy (filter 118)
- AdGuard Mail Tracking Protection (filter 25)
- DDG Tracker Radar (all 9 regions, excludes Embedded Content and Social categories)
- Privacy Badger (hard-blocked domains only, confirmed cross-site trackers, heavy filter)

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/adblock/advanced_tracking_protection.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/dns/advanced_tracking_protection.txt` |

#### Extended

Maximum coverage for users who want to catch as many trackers as possible and are willing to whitelist broken sites manually.

Same sources as complete, plus:
- DDG Tracker Radar with all categories included (including Embedded Content and Social)
- Privacy Badger with a lighter filter applied

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/adblock/advanced_tracking_protection_extended.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/dns/advanced_tracking_protection_extended.txt` |

#### Optimized

Smallest and safest. Built for DNS resolvers, routers, and mobile where file size and false positives matter.

- Uses AdGuard's pre-optimized CDN endpoints where available
- DDG Tracker Radar: safe categories only, 1% prevalence threshold, no subdomain rules
- No Privacy Badger rules

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/adblock/advanced_tracking_protection_optimized.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/dns/advanced_tracking_protection_optimized.txt` |

---

## How it works

The build script (`scripts/build.py`) runs the following on each build:

1. Fetches AdGuard Base (optimized) and (without EasyList), intersects them.
2. Fetches AdGuard Tracking Protection, EasyPrivacy, and AdGuard Mail Tracking Protection.
3. Sparse-clones the [DDG Tracker Radar](https://github.com/duckduckgo/tracker-radar) repo (all 9 regions), converts domain JSON files into `||domain^` adblock rules. Categories and prevalence thresholds vary per variant.
4. Fetches Privacy Badger [seed.json](https://github.com/EFForg/privacybadger) and extracts hard-blocked domains. Filters out CDN endpoints, major platform APIs, and anything borderline functional. Cookieblock entries are never included.
5. Merges all sources, deduplicates, and writes adblock and DNS/hosts format files.

The DNS format contains only `0.0.0.0 domain` entries from simple `||domain^` rules. Cosmetic rules, scriptlets, and path-specific rules are adblock-only.

---

## DDG Tracker Radar category breakdown

| Category | Extended | Complete | Optimized |
|----------|----------|----------|-----------|
| Advertising | yes | yes | yes |
| Analytics | yes | yes | yes |
| Fingerprinting | yes | yes | yes |
| Session Replay | yes | yes | yes |
| Malware / Cryptomining | yes | yes | yes |
| Ad Fraud / Action Pixels | yes | yes | yes |
| Email Tracking | yes | yes | yes |
| Audience Measurement | yes | yes | yes |
| Ad Motivated Tracking | yes | yes | yes |
| **Embedded Content** | yes | **no** | no |
| **Social** | yes | **no** | no |
| Unknown (no category) | yes | yes | no |
| Subdomains included | yes | yes | no |
| Prevalence threshold | none | none | 1% |

---

## Schedule

Runs every Sunday at 03:00 UTC. You can also trigger a manual build anytime from the Actions tab.

To switch to daily builds, open `.github/workflows/build.yml` and change:

```yaml
- cron: "0 3 * * 0"
```

to:

```yaml
- cron: "0 3 * * *"
```

---

## Configuration

All sources, category lists, Privacy Badger filters, and output paths live in `config.yml`. Adding or removing a source, changing DDG categories, or adjusting the Privacy Badger risk filter requires only editing that file.

---

## Sources

| Source | URL |
|--------|-----|
| AdGuard Base (optimized) | https://filters.adtidy.org/extension/ublock/filters/2_optimized.txt |
| AdGuard Base (without EasyList) | https://filters.adtidy.org/extension/ublock/filters/2_without_easylist.txt |
| AdGuard Tracking Protection | https://filters.adtidy.org/extension/ublock/filters/3.txt |
| AdGuard Tracking Protection (optimized) | https://filters.adtidy.org/extension/ublock/filters/3_optimized.txt |
| EasyPrivacy | https://filters.adtidy.org/extension/ublock/filters/118.txt |
| AdGuard Mail Tracking Protection | https://filters.adtidy.org/extension/ublock/filters/25.txt |
| AdGuard Mail Tracking Protection (optimized) | https://filters.adtidy.org/extension/ublock/filters/25_optimized.txt |
| DDG Tracker Radar | https://github.com/duckduckgo/tracker-radar |
| Privacy Badger | https://github.com/EFForg/privacybadger |

---

## License

MIT
