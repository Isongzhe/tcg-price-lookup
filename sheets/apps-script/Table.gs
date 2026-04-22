/**
 * Table styling configuration.
 * Adjust colors, fonts, and numeric formats here.
 */
const TABLE_CONFIG = {
  // Header row
  HEADER_BG_COLOR: "#444444",
  HEADER_FONT_COLOR: "#ffffff",
  HEADER_FONT_SIZE: 11,

  // Borders and gridlines
  HIDE_GRIDLINES: true,
  SHOW_OUTER_BORDER: true,
  BORDER_COLOR: "#e0e0e0",

  // Numeric format
  CURRENCY_FORMAT: "$#,##0.00",
  PRICE_COLUMN_HEADER: "market_price", // column matched by header name

  // Row banding (alternating row colors)
  ENABLE_BANDING: true,
  BANDING_THEME: SpreadsheetApp.BandingTheme.LIGHT_GREY
};

/**
 * Apply the styled-table theme to the entire used range of the sheet.
 */
function createTableTheme(sheet) {
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow === 0 || lastCol === 0) return;

  const range = sheet.getRange(1, 1, lastRow, lastCol);

  // 1. Row banding — clear any previous banding first to avoid stacking.
  range.getBandings().forEach(b => b.remove());
  if (TABLE_CONFIG.ENABLE_BANDING && lastRow > 1) {
    range.applyRowBanding(TABLE_CONFIG.BANDING_THEME, true, false);
  }

  // 2. Gridline visibility
  sheet.setHiddenGridlines(TABLE_CONFIG.HIDE_GRIDLINES);

  // 3. Header row styling
  const headerRange = sheet.getRange(1, 1, 1, lastCol);
  headerRange.setBackground(TABLE_CONFIG.HEADER_BG_COLOR)
             .setFontColor(TABLE_CONFIG.HEADER_FONT_COLOR)
             .setFontWeight("bold")
             .setFontSize(TABLE_CONFIG.HEADER_FONT_SIZE);

  // 4. Outer border
  if (TABLE_CONFIG.SHOW_OUTER_BORDER) {
    range.setBorder(true, true, true, true, null, null, TABLE_CONFIG.BORDER_COLOR, SpreadsheetApp.BorderStyle.SOLID);
  }

  // 5. Currency format on the price column (located by header name,
  //    not by position, so new TSV columns do not break this).
  const headers = headerRange.getValues()[0];
  const priceIdx = headers.indexOf(TABLE_CONFIG.PRICE_COLUMN_HEADER) + 1;

  if (priceIdx > 0 && lastRow > 1) {
    sheet.getRange(2, priceIdx, lastRow - 1, 1)
         .setNumberFormat(TABLE_CONFIG.CURRENCY_FORMAT);
  }
}
