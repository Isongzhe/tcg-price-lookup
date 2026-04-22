/**
 * Layout configuration.
 * Adjust row heights, column widths, and header-driven column lookups here.
 */
const CONFIG = {
  HEADER_HEIGHT: 40,
  ROW_HEIGHT: 90,
  MIN_COL_WIDTH: 100,          // floor for autoResizeColumns
  IMAGE_COL_WIDTH: 100,        // fixed width for column A (Card Preview)
  CARD_NAME_MIN_WIDTH: 180,    // wider minimum for the card_name column

  // TSV headers the script looks up by name.
  IMAGE_URL_HEADER: "image_url",
  CARD_NAME_HEADER: "card_name",

  PREVIEW_LABEL: "Card Preview" // text written into cell A1
};

/**
 * Replace column A with an =IMAGE() formula fed by the image_url column.
 */
function setupImageColumn(sheet) {
  const lastCol = sheet.getLastColumn();
  const lastRow = sheet.getLastRow();
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

  // Rewrite the A1 header label.
  sheet.getRange("A1").setValue(CONFIG.PREVIEW_LABEL);

  // Locate the image_url column by name.
  const imgColIndex = headers.indexOf(CONFIG.IMAGE_URL_HEADER) + 1;

  if (imgColIndex > 0) {
    const colLetter = sheet.getRange(1, imgColIndex).getA1Notation().replace('1', '');
    if (lastRow > 1) {
      // ARRAYFORMULA so one cell hydrates the whole column; IF guards empty rows.
      const imgFormula = `=ARRAYFORMULA(IF(${colLetter}2:${colLetter}="", "", IMAGE(${colLetter}2:${colLetter}, 1)))`;
      sheet.getRange("A2").setFormula(imgFormula);
    }
  }
}

/**
 * Apply row heights, center alignment, and frozen header/preview.
 */
function basicFormatter(sheet) {
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();

  if (lastRow > 1) {
    sheet.setRowHeight(1, CONFIG.HEADER_HEIGHT);
    sheet.setRowHeights(2, lastRow - 1, CONFIG.ROW_HEIGHT);
  }

  if (lastCol > 0 && lastRow > 0) {
    sheet.getRange(1, 1, lastRow, lastCol)
         .setVerticalAlignment("middle")
         .setHorizontalAlignment("center");
  }

  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(1);
}

/**
 * Size columns: auto-resize to content, then enforce a per-column minimum.
 */
function columnSizer(sheet) {
  const lastCol = sheet.getLastColumn();

  if (lastCol >= 1) {
    // 1. Auto-resize everything to fit content.
    sheet.autoResizeColumns(1, lastCol);

    // 2. Enforce the global minimum width.
    for (let i = 1; i <= lastCol; i++) {
      let currentWidth = sheet.getColumnWidth(i);
      if (currentWidth < CONFIG.MIN_COL_WIDTH) {
        sheet.setColumnWidth(i, CONFIG.MIN_COL_WIDTH);
      }
    }

    // 3. Force column A to the image width regardless of content.
    sheet.setColumnWidth(1, CONFIG.IMAGE_COL_WIDTH);
  }

  // 4. Special-case the card_name column: ensure it is wide enough to read.
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const nameIdx = headers.indexOf(CONFIG.CARD_NAME_HEADER) + 1;
  if (nameIdx > 0) {
    if (sheet.getColumnWidth(nameIdx) < CONFIG.CARD_NAME_MIN_WIDTH) {
      sheet.setColumnWidth(nameIdx, CONFIG.CARD_NAME_MIN_WIDTH);
    }
  }
}
