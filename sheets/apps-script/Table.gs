/**
 * Table Styling Configurations
 * 您可以在此自定義表格顏色、字體與格式
 */
const TABLE_CONFIG = {
  // 標題列視覺設定
  HEADER_BG_COLOR: "#444444",    // 標題背景顏色 (深灰色)
  HEADER_FONT_COLOR: "#ffffff",  // 標題文字顏色 (白色)
  HEADER_FONT_SIZE: 11,          // 標題字體大小
  
  // 表格邊框與格線
  HIDE_GRIDLINES: true,          // 是否隱藏工作表預設格線
  SHOW_OUTER_BORDER: true,       // 是否顯示表格外框線
  BORDER_COLOR: "#e0e0e0",       // 邊框顏色
  
  // 數據格式
  CURRENCY_FORMAT: "$#,##0.00",  // 價格顯示格式
  PRICE_COLUMN_HEADER: "market_price", // 觸發價格格式的欄位名稱
  
  // 顏色交替 (Banding) 設定
  ENABLE_BANDING: true,          // 是否啟用斑馬紋 (您之前要求關閉)
  BANDING_THEME: SpreadsheetApp.BandingTheme.LIGHT_GREY 
};

/**
 * 處理表格美化與樣式設定
 */
function createTableTheme(sheet) {
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow === 0 || lastCol === 0) return;

  const range = sheet.getRange(1, 1, lastRow, lastCol);
  
  // 1. 處理顏色交替 (Banding)
  range.getBandings().forEach(b => b.remove());
  if (TABLE_CONFIG.ENABLE_BANDING && lastRow > 1) {
    range.applyRowBanding(TABLE_CONFIG.BANDING_THEME, true, false);
  }
  
  // 2. 處理格線顯示
  sheet.setHiddenGridlines(TABLE_CONFIG.HIDE_GRIDLINES); 
  
  // 3. 標題列美化
  const headerRange = sheet.getRange(1, 1, 1, lastCol);
  headerRange.setBackground(TABLE_CONFIG.HEADER_BG_COLOR)
             .setFontColor(TABLE_CONFIG.HEADER_FONT_COLOR)
             .setFontWeight("bold")
             .setFontSize(TABLE_CONFIG.HEADER_FONT_SIZE);

  // 4. 設定外框線 (提升視覺質感)
  if (TABLE_CONFIG.SHOW_OUTER_BORDER) {
    range.setBorder(true, true, true, true, null, null, TABLE_CONFIG.BORDER_COLOR, SpreadsheetApp.BorderStyle.SOLID);
  }

  // 5. 自動尋找價格欄位並套用格式
  const headers = headerRange.getValues()[0];
  const priceIdx = headers.indexOf(TABLE_CONFIG.PRICE_COLUMN_HEADER) + 1;
  
  if (priceIdx > 0 && lastRow > 1) {
    sheet.getRange(2, priceIdx, lastRow - 1, 1)
         .setNumberFormat(TABLE_CONFIG.CURRENCY_FORMAT);
  }
}
