# adfilters

Custom filter lists built automatically from upstream sources. Updated weekly via GitHub Actions.

---

## Filter Lists

### AdGuard Base - Without EasyList (Optimized)

This is the intersection of AdGuard Base (optimized) and AdGuard Base (without EasyList). It contains only the AdGuard-authored rules that also survived AdGuard's optimization pass.

Use this **instead of** the default AdGuard Base filter. Pair it with EasyList (already included in most adblockers by default). This way you get zero rule duplication between the two.

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/YOUR_USERNAME/adfilters/main/output/adblock/2_without_easylist_optimized.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/YOUR_USERNAME/adfilters/main/output/dns/2_without_easylist_optimized.txt` |

---

### Advanced Tracking Protection

Union of four upstream sources, deduplicated:

- AdGuard Tracking Protection (filter 3)
- EasyPrivacy (filter 118)
- AdGuard Mail Tracking Protection (filter 25)
- DDG Tracker Radar (US, full tracking categories)

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/YOUR_USERNAME/adfilters/main/output/adblock/advanced_tracking_protection.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/YOUR_USERNAME/adfilters/main/output/dns/advanced_tracking_protection.txt` |

#### Optimized variant

Same sources but uses the `_optimized` CDN endpoints from AdGuard where available. Smaller file, fewer rules, faster to parse.

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/YOUR_USERNAME/adfilters/main/output/adblock/advanced_tracking_protection_optimized.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/YOUR_USERNAME/adfilters/main/output/dns/advanced_tracking_protection_optimized.txt` |

---

## How it works

The build script (`scripts/build.py`) does the following on each run:

1. Fetches the AdGuard Base optimized and without-EasyList variants, then intersects them.
2. Fetches AdGuard Tracking Protection, EasyPrivacy, and AdGuard Mail Tracking Protection.
3. Sparse-clones the [DDG Tracker Radar](https://github.com/duckduckgo/tracker-radar) repo (US domain JSONs only) and converts tracking-category domains to adblock rules.
4. Merges and deduplicates everything.
5. Writes adblock format and DNS/hosts format to `output/`.

The DNS format contains only simple `0.0.0.0 domain` entries extracted from `||domain^` style rules. Cosmetic rules, scriptlets, and path-specific rules are adblock-only.

---

## Schedule

Runs every Sunday at 03:00 UTC. You can also trigger a manual build from the Actions tab at any time.

To switch to daily: open `.github/workflows/build.yml` and change:

```yaml
- cron: "0 3 * * 0"
```

to:

```yaml
- cron: "0 3 * * *"
```

---

## Configuration

All sources and settings live in `config.yml`. You can add or remove upstream sources, change DDG tracking categories, or point outputs to different paths without editing any Python.

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
| DDG Tracker Radar | https://github.com/duckduckgo/tracker-radar |

---

## License

MIT
