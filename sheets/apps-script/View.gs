/**
 * View configuration.
 * Declares which columns to hide by default and how aggressively to reset
 * existing groupings before reapplying.
 */
const VIEW_CONFIG = {
  // Columns hidden from the formatted view. Looked up by header name,
  // so append-only changes to the TSV schema do not break anything.
  HIDE_LIST: [
    "set_name",
    "product_id",
    "sku_id",
    "image_url",
    "missing",
    "mp_sample",
    "released",
    "condition",
    "Card Preview" // in case an older run left this header in the data
  ],

  // How many levels of existing column grouping to clear before reapplying.
  MAX_GROUP_DEPTH_RESET: 3,

  // Columns at or below this 1-based index are never auto-hidden.
  // Column 1 is the preview column and must always stay visible.
  PROTECTED_COLUMN_INDEX: 1
};

/**
 * Group and hide the metadata columns named in VIEW_CONFIG.HIDE_LIST.
 */
function createGroupedView(sheet) {
  const lastCol = sheet.getLastColumn();
  if (lastCol === 0) return;

  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];

  // 1. Reset any existing column groupings so the pipeline is idempotent.
  try {
    for (let i = 0; i < VIEW_CONFIG.MAX_GROUP_DEPTH_RESET; i++) {
      sheet.getRange(1, 1, 1, lastCol).shiftColumnGroupDepth(-1);
    }
  } catch (e) {
    // No more group levels to remove; ignore.
  }

  // 2. Walk the header row and hide/group each matching column.
  headers.forEach((title, index) => {
    const colPosition = index + 1;

    // Skip the protected column and anything not in the hide list.
    if (colPosition > VIEW_CONFIG.PROTECTED_COLUMN_INDEX && VIEW_CONFIG.HIDE_LIST.includes(title)) {
      try {
        // Add the column to a group (a [+] toggle appears above the column letters).
        sheet.getRange(1, colPosition).shiftColumnGroupDepth(1);
        // Hide it by default; the user can expand via the toggle.
        sheet.hideColumns(colPosition);
      } catch (e) {
        console.warn("Could not group/hide column: " + title);
      }
    }
  });
}
