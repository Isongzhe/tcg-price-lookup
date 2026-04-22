/**
 * TCG Data Management System - Core Pipeline
 * Version: 1.0.0
 * Description: Automates image generation, layout formatting, and data grouping.
 */

const DATA_SHEET_NAME = "Price Reference"; // Set your target data sheet name here

function mainFormatProcess() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(DATA_SHEET_NAME);
  
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Error: Sheet '" + DATA_SHEET_NAME + "' not found.");
    return;
  }

  // 1. Initialization: Expand all columns and remove existing groups
  const lastCol = sheet.getLastColumn();
  if (lastCol > 0) {
    sheet.showColumns(1, lastCol);
    try {
      // Clears up to 5 levels of column grouping depth to reset the view
      for (let i = 0; i < 5; i++) {
        sheet.getRange(1, 1, 1, lastCol).shiftColumnGroupDepth(-1);
      }
    } catch (e) {
      // Ignore if no groupings exist
    }
  }

  // 2. Execution Chain
  setupImageColumn(sheet);   // Configure Image Preview logic in Column A
  basicFormatter(sheet);     // Apply Row Heights (40px/70px) and alignments
  columnSizer(sheet);        // Apply Column Widths (80px for A, 100px+ for others)
  createTableTheme(sheet);   // Apply professional table styling and number formats
  createGroupedView(sheet);  // Auto-hide/group metadata columns for clean export

  // 3. Finalization
  sheet.activate();
  SpreadsheetApp.getUi().alert("Data Pipeline Execution Successful.");
}

/**
 * Standard Workspace Menu Configuration
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('TCG Management')
    .addItem('Run Data Formatting', 'mainFormatProcess')
    .addSeparator()
    .addItem('Expand All Columns', 'showAllColumns')
    .addToUi();
}

/**
 * Helper: Expand all columns in the active sheet
 */
function showAllColumns() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastCol = sheet.getLastColumn();
  if (lastCol > 0) {
    sheet.showColumns(1, lastCol);
  }
}
