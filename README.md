# adfilters

Extra filter lists: optimized AdGuard variants and comprehensive tracking protection from combined upstream sources.

---

## Filter Lists

### AdGuard Base — Without EasyList (Optimized)

A drop-in replacement for AdGuard Base filter, with EasyList rules removed. Use alongside EasyList to get full AdGuard coverage with zero duplication.

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/adblock/2_without_easylist_optimized.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/dns/2_without_easylist_optimized.txt` |

---

### Advanced Tracking Protection

Blocks trackers, analytics, fingerprinting, email pixels, and ads across all regions. Three variants:

#### Complete (recommended)

Broad coverage with low site breakage risk.

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/adblock/advanced_tracking_protection.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/dns/advanced_tracking_protection.txt` |

#### Extended

Maximum coverage. May occasionally break sites with heavy third-party embeds.

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/adblock/advanced_tracking_protection_extended.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/dns/advanced_tracking_protection_extended.txt` |

#### Optimized

For DNS resolvers, routers, and mobile. Smaller file, lower false positive rate.

| Format | URL |
|--------|-----|
| Adblock | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/adblock/advanced_tracking_protection_optimized.txt` |
| DNS/hosts | `https://raw.githubusercontent.com/cudios-dev/adfilters/main/output/dns/advanced_tracking_protection_optimized.txt` |

---

## Sources

All filter lists are derived from the following upstream sources:

- [AdGuard Filters](https://github.com/AdguardTeam/AdguardFilters)
- [EasyPrivacy](https://easylist.to)
- [DDG Tracker Data Set](https://staticcdn.duckduckgo.com/trackerblocking/v6/tds.json)
- [Privacy Badger](https://github.com/EFForg/privacybadger)
- [Ghostery Tracker DB](https://github.com/ghostery/trackerdb)
- Disconnect.me
---

## License

MIT
