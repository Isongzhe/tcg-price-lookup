/**
 * View Configurations
 * 您可以在此自定義隱藏清單與分組深度
 */
const VIEW_CONFIG = {
  // 定義不需要在截圖中顯示的欄位標題
  HIDE_LIST: [
    "set_name",
    "product_id", 
    "sku_id", 
    "image_url", 
    "missing", 
    "mp_sample", 
    "released", 
    "condition", 
    "Card Preview" // 原始資料中若有此標題也一併隱藏，因為我們已將圖移至 A 欄
  ],
  
  // 清除舊分組時嘗試的次數 (深度)
  MAX_GROUP_DEPTH_RESET: 3,
  
  // 保護欄位索引 (通常 A 欄為 1，不應被自動隱藏)
  PROTECTED_COLUMN_INDEX: 1
};

/**
 * 建立分組檢視並隱藏冗餘欄位
 */
function createGroupedView(sheet) {
  const lastCol = sheet.getLastColumn();
  if (lastCol === 0) return;

  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  
  // 1. 清除現有的所有分組，確保 Pipeline 重新執行時畫面乾淨
  try {
    for (let i = 0; i < VIEW_CONFIG.MAX_GROUP_DEPTH_RESET; i++) {
      sheet.getRange(1, 1, 1, lastCol).shiftColumnGroupDepth(-1);
    }
  } catch (e) {
    // 若無更多分組層級可移除則忽略
  }

  // 2. 遍歷標題列，根據 HIDE_LIST 進行隱藏與分組
  headers.forEach((title, index) => {
    const colPosition = index + 1;
    
    // 跳過受保護的 A 欄，僅處理 hideList 中的欄位
    if (colPosition > VIEW_CONFIG.PROTECTED_COLUMN_INDEX && VIEW_CONFIG.HIDE_LIST.includes(title)) {
      try {
        // 將欄位加入分組 (上方會出現 [+] 符號)
        sheet.getRange(1, colPosition).shiftColumnGroupDepth(1);
        // 預設執行隱藏
        sheet.hideColumns(colPosition); 
      } catch (e) {
        console.warn("Could not group/hide column: " + title);
      }
    }
  });
}
