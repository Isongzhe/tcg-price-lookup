/**
 * TCG UI Configurations
 * 您可以在此調整表格的長寬數值
 */
const CONFIG = {
  HEADER_HEIGHT: 40,      // 標題列高度
  ROW_HEIGHT: 90,         // 資料列高度
  MIN_COL_WIDTH: 100,     // 一般欄位最小寬度 (Fit data 的下限)
  IMAGE_COL_WIDTH: 100,   // A 欄 (Card Preview) 固定寬度
  CARD_NAME_MIN_WIDTH: 180, // 卡片名稱欄位最小寬度
  IMAGE_URL_HEADER: "image_url", // 原始資料中的圖片網址欄位名稱
  CARD_NAME_HEADER: "card_name", // 原始資料中的卡片名稱欄位名稱
  PREVIEW_LABEL: "Card Preview"  // A1 顯示的標題名稱
};

/**
 * 設定 A 欄的圖片公式
 */
function setupImageColumn(sheet) {
  const lastCol = sheet.getLastColumn();
  const lastRow = sheet.getLastRow();
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  
  // 設定 A1 標題
  sheet.getRange("A1").setValue(CONFIG.PREVIEW_LABEL);
  
  // 尋找目標欄位位置
  const imgColIndex = headers.indexOf(CONFIG.IMAGE_URL_HEADER) + 1;
  
  if (imgColIndex > 0) {
    const colLetter = sheet.getRange(1, imgColIndex).getA1Notation().replace('1','');
    if (lastRow > 1) {
      // 寫入公式
      const imgFormula = `=ARRAYFORMULA(IF(${colLetter}2:${colLetter}="", "", IMAGE(${colLetter}2:${colLetter}, 1)))`;
      sheet.getRange("A2").setFormula(imgFormula);
    }
  }
}

/**
 * 處理高度與基本對齊
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
 * 處理欄位寬度邏輯
 */
function columnSizer(sheet) {
  const lastCol = sheet.getLastColumn();
  
  if (lastCol >= 1) {
    // 1. 先讓所有欄位自動縮放以適應內容
    sheet.autoResizeColumns(1, lastCol);
    
    // 2. 檢查寬度下限
    for (let i = 1; i <= lastCol; i++) {
      let currentWidth = sheet.getColumnWidth(i);
      if (currentWidth < CONFIG.MIN_COL_WIDTH) {
        sheet.setColumnWidth(i, CONFIG.MIN_COL_WIDTH);
      }
    }
    
    // 3. 強制設定 A 欄寬度
    sheet.setColumnWidth(1, CONFIG.IMAGE_COL_WIDTH);
  }
  
  // 4. 卡片名稱欄位保護
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const nameIdx = headers.indexOf(CONFIG.CARD_NAME_HEADER) + 1;
  if (nameIdx > 0) {
    if (sheet.getColumnWidth(nameIdx) < CONFIG.CARD_NAME_MIN_WIDTH) {
      sheet.setColumnWidth(nameIdx, CONFIG.CARD_NAME_MIN_WIDTH);
    }
  }
}
