# Google Sheets Template

A pre-built Google Sheets template that formats the TSV output of
`scripts.fetch_deck` into a readable, image-rich table with a single
click. Contributed by the project maintainer as a convenience; offered
"as is" and separate from the Apache 2.0 license that covers the core
CLI (see **Disclaimer** below).

---

## What it does

The template ships with an Apps Script that, when run, performs the
following transformations on the active sheet named `Price Reference`:

1. **Adds a card preview column.** Column A is replaced with an
   `=IMAGE()` formula that renders the TCGplayer CDN image from the
   `image_url` column as a thumbnail.
2. **Applies consistent row heights and column widths.** A fixed
   header row, 90 px data rows, a minimum column width of 100 px,
   and a wider minimum for the `card_name` column.
3. **Styles the table.** Dark header bar, optional zebra banding,
   outer border, and `$#,##0.00` number formatting on the
   `market_price` column.
4. **Freezes the header row and the preview column.**
5. **Groups and hides metadata columns** that clutter trading
   discussions (`set_name`, `product_id`, `sku_id`, `image_url`,
   `missing`, `mp_sample`, `released`, `condition`). Hidden columns
   can be re-expanded via the `[+]` toggle that appears above the
   column letters.

The script has a menu entry (`TCG Management → Run Data Formatting`)
plus a helper `Expand All Columns` option.

## What it does not do

- **No network calls.** The script does not use `UrlFetchApp` or any
  other outbound request. It only manipulates cells in the active
  spreadsheet.
- **No data collection.** It does not read the active user's email,
  Google account metadata, or any spreadsheet outside the one you
  open it in.
- **No persistence beyond the spreadsheet itself.** All changes are
  visible cell edits; there is no hidden state, no Drive files, no
  `PropertiesService` use.

You can verify these claims yourself — the full source is in
[`apps-script/`](./apps-script/), or in the copied sheet via
**Extensions → Apps Script**.

---

## How to use

### Option 1: Copy the template (quickest)

Click the following link while signed in to Google Drive:

**[Copy the template to your Drive →](https://docs.google.com/spreadsheets/d/1u7r0ND0wkUTGl7k8jDayK74l2U4KIlu_WLfJCR0dgcg/copy)**

Google will prompt you to confirm the copy. Once created, paste the TSV
from `scripts.fetch_deck` into cell **A1 of the `Price Reference` tab**,
then run **TCG Management → Run Data Formatting** from the sheet's menu
bar.

### Option 2: Build your own sheet from the source

If you prefer not to copy an opaque document:

1. Create a new Google Sheet with a tab named `Price Reference`.
2. Open **Extensions → Apps Script**.
3. Create four script files matching the filenames in
   [`apps-script/`](./apps-script/) (`main.gs`, `Table.gs`, `UI.gs`,
   `View.gs`) and paste their contents.
4. Save. Reload the spreadsheet tab once so the `onOpen` menu takes
   effect.
5. Paste your TSV into A1 of `Price Reference` and trigger
   **TCG Management → Run Data Formatting**.

---

## Authorization prompt

The first time the formatter runs, Google will ask you to authorize
the script. You will see a dialog like:

> This app is not verified.
>
> This app hasn't been verified by Google yet. Only proceed if you
> know and trust the developer.

This warning is expected for any personal Apps Script that has not
gone through Google's formal verification review (which is oriented
toward commercial distribution). It is not an indication of anything
malicious.

To proceed:

1. Click **Advanced** in the warning dialog.
2. Click **Go to [sheet name] (unsafe)**.
3. Review the specific permission requested — the script needs:
   - `See, edit, create, and delete your spreadsheets in Google Drive`

   This scope is requested because the script rewrites cell formatting
   in the spreadsheet you opened. It does not reach into other
   spreadsheets or Drive files.
4. Click **Allow**.

If you are uncomfortable granting this permission, use **Option 2**
above — you can inspect the script source yourself before authorizing.

---

## File layout

```
sheets/
├── README.md                 (this file)
└── apps-script/
    ├── main.gs               Menu definition + pipeline entry point
    ├── UI.gs                 Row heights, column widths, image column
    ├── Table.gs              Styling (header, banding, borders, currency)
    └── View.gs               Hiding and grouping of metadata columns
```

Each `.gs` file carries its own configuration constants at the top, so
customization (colors, hidden columns, currency format) does not
require touching the logic below.

---

## Version compatibility

The template assumes the TSV column layout emitted by
`scripts.fetch_deck`. Specifically it references these headers by name:

- `image_url` — used to build the preview column.
- `card_name` — used for the extra-wide column override.
- `market_price` — targeted for currency formatting.
- `set_name`, `product_id`, `sku_id`, `image_url`, `missing`,
  `mp_sample`, `released`, `condition` — hidden by default.

Because the script looks up columns by header name rather than by
position, adding new columns to the CLI (as long as the existing names
are preserved) will not break the template. Renaming or removing any
of the columns above will.

See the main project [`README.md`](../README.md) for the current TSV
schema.

---

## Disclaimer

This template is provided as a convenience. It is **not** covered by
the repository's Apache 2.0 license — Google Apps Script code
distributed via a shareable Google Drive link falls outside that
grant. Treat the template the same way you would treat any
third-party Sheets add-on:

- Review the script before granting access if you have any concern.
- No warranty of any kind is provided; run at your own discretion.
- The maintainer is not responsible for any data loss or formatting
  issues caused by running the script.

The `.gs` source files bundled in this directory are provided under
the same Apache 2.0 license as the rest of the repository, so you are
free to adapt them for your own sheets.
