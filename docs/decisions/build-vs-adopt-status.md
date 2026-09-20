# Build vs Adopt — 目前狀態

**日期：** 2026-09-21
**稽核當時的 canonical checkpoint：** `d9cf211`（Phase 0.5，17 tests passed）
**完整報告：** [docs/reviews/build-vs-adopt-forensic-audit.md](../reviews/build-vs-adopt-forensic-audit.md)

## 決定

**暫停 Phase 1 與任何 domain capability 擴充。**

scheduler-kernel 保留為 **executable research prototype**——可執行、可驗證、
仍是 Generate / Explain / Repair 三條 path 的乾淨參照實作。
這不是專案失敗，也不是永久 abandoned；停的是**沒有證據支撐的 from-scratch expansion**。

## 理由

forensic audit 比較了 scheduler-kernel、`begin0808/Course_Scheduling_System`（下稱 CSS，
稽核 commit `a53acdf`）與 `klin059/course-scheduling-TWschools`（`3a8c04b`）。

以實測（非 README 宣稱）為準，在 scheduler-kernel 找不到任何 **Category C（架構型）** gap——
也就是「必須改 domain model / solver formulation / repair architecture 才能解，
因此競品難以低成本取得」的能力。最接近的兩項都不合格：

- baseline-deviation 目標項（`change_weight`）：對 CSS 是 **Category B**，
  localized extension 即可補上。
- 診斷紀律（`diagnostic_complete` / `limitations`）：**Category D**，
  尚未證明使用者在意，且其「誠實」建立在診斷解析度較低之上。

## 明確**未**決定的事

- **沒有決定採用 CSS。** 目前只是停止無證據的自建擴充。
- **audit 沒有證明真人的 adoption friction。** 對 CSS 導入成本的評估來自程式碼、
  安裝腳本與匯入範本的存在，**不是使用者測試**。
  「CSS 的 adoption cost 是否過高」仍是 open question；
  稽核只能說「沒有證據顯示過高」。
- 未做三方效能 benchmark，未宣稱任一方較快。

## 下一個 product-level gate

**對 CSS 做真實 onboarding / real-data evaluation。**
取一所真實學校的一學期資料，走完安裝 → 設定精靈 → Excel 匯入 → 自動排課 →
衝突定位 → 匯出，量測到「第一次得到可信結果」的實際成本、卡住的步驟、
以及教學組長看不懂的用語。

在這個 gate 有結果之前，不新增 kernel 功能。

## 重啟條件

未來若要重啟 scheduler-kernel 的功能開發，必須**先**具備下列至少一項證據：

1. 一個競品**無法低成本解決的 Category C gap**（需指出具體的 domain model /
   solver formulation / repair architecture 改動，並說明為何 fork 競品成本更高）；或
2. **真人需求 evidence**——實際使用者在實際資料上遇到、且競品解不了的問題。

「我們的做法比較乾淨」「未來可以做得很簡單」不構成重啟理由（Category D 不自動升格）。

## 封存後的修補

稽核 Probe 3/4 實測到一個 accepted-decision persistence bug：
`repair_teacher_slot()` 在教師當下沒被排在該時段時，會靜默丟棄使用者的請求，
導致後續 Generate 可以把教師排回已被明確拒絕的時段。

此 bug 已修復並補上 regression test（A/B/C/D 四項，含重現稽核所述 leak 的整天情境）。
這是 correctness 修補，**不是 Phase 1 的開始**，未擴充 `SchedulingDecision` ontology，
也未新增 day-level availability API。
