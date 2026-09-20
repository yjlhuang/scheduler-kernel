# scheduler-kernel

校園排課系統的 Phase 0.5 核心。這不是既有產品的 fork，也暫時不是完整校務系統；Phase 0 只證明三條 execution path 跑得通，Phase 0.5 才開始補上接近真實密度的證據：

- **Generate**：從 synthetic school 資料產生合法課表。
- **Explain**：資料無解時，指出可重現的衝突，並實際驗證哪些授權後可放寬的限制能恢復可行性。
- **Repair**：鎖住已接受區域，只對局部偏好做重新最佳化。

## 快速開始

需要 Python 3.11–3.13 與 `uv`：

```powershell
uv sync --extra dev
uv run scheduler-kernel generate data/fixtures/small_school.json
uv run scheduler-kernel explain data/fixtures/unsat_teacher_capacity.json
uv run scheduler-kernel demo-repair data/fixtures/small_school.json
uv run scheduler-kernel generate data/fixtures/dense_school_6.json
uv run python tools/benchmark_scaling.py
uv run pytest
```

CLI 輸出 JSON，方便之後接 UI、試算表或其他 workflow，但 Phase 0 刻意不實作那些層。

## 專案邊界

現在包含 domain model、Constraint Registry、Teacher Preference Profile、authoritative schedule state、derived-artifact dependency、CP-SAT solver、衝突說明、局部修復與測試。

現在不包含正式 UI、登入權限、通知、報表、資料庫、完整調代課流程或正式校務資料匯入。

詳見 [docs/architecture.md](docs/architecture.md) 與 [docs/constraint-registry.md](docs/constraint-registry.md)。

## 現況與已知問題

上面三項驗證的是「三條 execution path 跑得通」，**還不等於這三個能力在接近真實密度的課表上成立**。
Phase 0 architecture red-team review 列出 6 個 BLOCKER（fixture 密度、resource semantics、
`UNKNOWN`/`INFEASIBLE` 混用、Explain 的沉默與假因果、preservation metric、state boundary）
與 Phase 0.5 的 gate：[docs/reviews/opus-phase0-red-team.md](docs/reviews/opus-phase0-red-team.md)。

Phase 0.5 的先紅後綠紀錄、dense fixture 統計與 6/12/24 scaling 結果見
[docs/phase05-verification.md](docs/phase05-verification.md)。Opus review 保留原文，未改寫。
