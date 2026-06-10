=== Slip 貼圖資料夾 ===

放置規則（不用改程式，丟資料夾→重新部署即可）：
1. 每個「子資料夾」＝一個貼圖組，資料夾名稱就是面板上顯示的組名（可中文）。
   例：  static/stickers/小芽/        → 組名「小芽」
2. 組內圖片依「檔名」排序，建議零補位命名：01.png、02.png、03.png ...
3. 支援格式：.png（去背最佳）、.webp、.gif、.apng（動態）。
4. 想控制組的先後順序，可在資料夾名加數字前綴「數字_」，顯示時會自動去掉前綴：
   例：  1_小芽/  2_醫療/   → 面板依序顯示「小芽」「醫療」
5. 圖一定要放在「專案的 static/stickers/」並跟程式一起部署（commit、push 上 Railway）。
   不要只丟到線上容器，否則下次部署會被覆蓋消失。貼圖是站內靜態檔，不佔使用者上傳容量。

建議規格：正方形、約 320x320 px、單張 < 200KB、去背 PNG。

------------------------------------------------------------
=== 產生貼圖的標準 Prompt（給 AI 繪圖工具）===

中文版（把【主題】換成你要的角色/風格，例如「綠色小芽芽吉祥物」）：
  一張可愛的通訊軟體貼圖，主題是【主題】，單一角色置中，
  正在【表情或動作，例如：開心揮手 / 比讚 / 疑惑 / 加油 / 謝謝】，
  乾淨的粗線條、扁平上色、明亮色調，角色佔畫面約 80%，
  純透明背景、無文字、無邊框、無陰影投影，正方形構圖。

English（多數繪圖模型英文效果較好）：
  Cute messaging-app sticker of 【SUBJECT】, single character centered,
  doing 【expression/action: waving happily / thumbs up / confused / cheering / thank you】,
  bold clean outline, flat colors, bright palette, character fills ~80% of frame,
  fully transparent background, no text, no border, no drop shadow, square composition.

小提醒：
- 一次只請它畫「一個角色、一個表情」，整組表情用同一個角色＋同一種畫風，風格才一致。
- 若工具不支援透明背景，請輸出後去背（背景設透明）再存成 PNG。
- 匯出後依上面規則命名（01.png、02.png…）放進對應組資料夾。
- 你自行確認所用素材的版權（自製或已授權），請勿使用 LINE 官方貼圖或受版權保護的角色。
