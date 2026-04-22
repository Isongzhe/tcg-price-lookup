# Disclaimer and Terms of Use

## Purpose

This project is an **educational and personal-use tool** that demonstrates how
to interact with TCGplayer's publicly accessible frontend JSON endpoints — the
same endpoints a standard web browser uses when a user visits
[tcgplayer.com](https://www.tcgplayer.com). It is intended for:

- Personal price reference when trading physical collectible cards with other
  individuals on a one-to-one basis.
- Learning about HTTP clients, structured API design, and Python software
  architecture.
- Writing and studying API clients in Python.

## Scope of This License

The Apache License 2.0 in `LICENSE` applies **only to the source code of
this repository** (the Python modules, tests, and documentation authored
by the project maintainer). It does not grant any rights to, and does not
make any claim over:

- Data served by TCGplayer's endpoints (prices, product names, images,
  seller information, etc.).
- TCGplayer's trademarks, branding, or UI assets.
- Any third-party intellectual property referenced in card names or set
  names (e.g. card game publishers' trademarks).

All such rights remain with their respective owners. This project stores no
such data in version control — snapshot files are git-ignored by default.

## Not Affiliated With TCGplayer

This project is **not affiliated with, endorsed by, or sponsored by**
TCGplayer, Inc. or its parent company. "TCGplayer" and product-line names
such as "Grand Archive TCG", "Magic: The Gathering", "Pokémon TCG", etc. are
trademarks of their respective owners, used here nominatively solely to
describe what the tool interacts with.

## No Warranty

This software is provided "AS IS" under the Apache License 2.0 (see
`LICENSE`). The authors make no warranties about correctness of price data,
availability of the underlying services, or compatibility with any
third-party terms of service. **Prices and data returned by this tool may be inaccurate,
out-of-date, or unavailable at any time.** Do not rely on this tool for
financial decisions.

## Respect for Target Services

Users of this software are responsible for ensuring their use complies with:

1. **TCGplayer's Terms of Service and `robots.txt`.** Read them before use.
   The default behavior of this tool (sequential requests with a configurable
   ~0.8 second delay per card) is designed for occasional personal lookups
   comparable to manually browsing the website.
2. **Applicable laws in your jurisdiction**, including but not limited to
   the Computer Fraud and Abuse Act (CFAA, United States), the
   Computer-Processed Personal Data Protection Act (Taiwan), the GDPR
   (EU/EEA), or equivalent local legislation governing automated access to
   online services.
3. **Rate-limiting common sense.** This tool is not designed for, and must
   not be configured for, high-frequency or concurrent access.

## Prohibited Uses

The following uses are **explicitly outside** the scope of this project and
are neither endorsed nor supported by the maintainer:

- Commercial resale or redistribution of data obtained via the tool.
- Automated purchasing, sniping, arbitrage, or any interaction with
  TCGplayer user accounts, carts, or checkout systems.
- Building or operating a public-facing service that redistributes
  TCGplayer data.
- Circumventing account authentication, paywalls, geoblocks, or any control
  not bypassed by a normal logged-out browser session.
- Denial-of-service, rate-limit abuse, scraping of the entire catalog, or
  any use likely to degrade service for other users.
- Any use in violation of the target service's current Terms of Service.

**If you wish to use TCGplayer data for commercial or high-volume purposes,
apply for access to the
[official TCGplayer API](https://docs.tcgplayer.com/).**

## Reporting and Good-Faith Takedown

If you are a rights holder (including TCGplayer, Inc.) and believe this
repository should be modified or taken down, please:

1. Open an issue on the GitHub repository, **or**
2. Contact the repository owner directly via the contact information on
   their GitHub profile.

The maintainer will respond in good faith and is willing to make the
repository private, modify its content, or take it down without legal
proceedings being necessary. This project has no commercial value to the
maintainer and exists solely for the purposes stated above.

## User Accountability

**By using, cloning, forking, or redistributing this software, you agree
that:**

- You have read and understood this document.
- You are solely responsible for how you use the software, including
  compliance with the terms of service of any third party it interacts with.
- You will not hold the authors, contributors, or copyright holders liable
  for any direct or indirect consequences arising from your use of the
  software.
- You will not represent this project as officially sanctioned by, or
  affiliated with, TCGplayer, Inc. or any product-line trademark holder.

If you do not agree to these terms, do not use, clone, or fork this
software.

---

*Last updated: 2026-04-22*
