# School Scheduler — Build vs Fork vs Adopt Forensic Audit

> Read-only competitive technical audit。三個 repo 皆未修改、未開 PR、未 commit/push。
> 競品以 `--depth 50` clone 至 session scratchpad 的獨立 evaluation workspace，只讀取與匯入執行，未寫入。
> 稽核日期：2026-09-21。稽核當時 scheduler-kernel 的 canonical checkpoint 為 `d9cf211`。
> 本報告依原樣封存，未因後續修補而改寫；其中 Probe 3/4 記錄的
> accepted-decision persistence bug 已於封存後修復，見 [docs/decisions/build-vs-adopt-status.md](../decisions/build-vs-adopt-status.md)。

---

## 1. Executive Summary

**結論：以目前程式碼實際具備的能力衡量，繼續從零開發 scheduler-kernel 沒有技術理由。**

三項關鍵發現：

1. **Probe 1（數 A／數 B 同步分組）在 scheduler-kernel 中是「Not representable」，不是「尚未實作」。**
   `domain.validate()` 主動拒絕多班級與多教師的 lesson（`domain.py:162-169`），且 domain 層完全沒有
   synchronization / group 概念。實測丟出 `ValueError: Phase 0.5 supports exactly one class per lesson`。
   同一個案例在 Course_Scheduling_System（下稱 **CSS**）是 native first-class：我在無 DB、無 UI 的情況下
   直接驅動其 solver，用一個 3 成員的 `UnitSpec(unit_type="group")` 建模，**三個教學單位排出完全相同的時段，
   且數 A 教師的星期四 unavailability 正確傳播到整個同步群**。

2. **scheduler-kernel 唯一在程式碼層面勝過 CSS 的排課能力，是 minimal-change repair 的
   baseline-deviation 目標項**（`engine.py` 的 `change_weight`）。CSS 只有硬鎖（H9）與 `add_hint()` 的
   best-effort 提示，沒有把「與原課表的偏離量」放進目標函數。
   **這個 gap 經實測是實質的，不是裝飾性的**：在 120 堂課的 fixture 上封鎖一位教師的星期四，
   只有 5 堂非動不可，CSS 的 hint 路徑卻動了 89 堂（preservation 0.258）。
   **但它仍是 Category B，不是 Category C** ——CSS 的 `_h9_locked()` 放寬分支
   **已經寫好一個 per-cell 偏離懲罰**（`moved` 布林變數 + `violation_penalty`，`model_builder.py:654-658`），
   `_objective()` 又是乾淨的 `add(code, expr)` 樣板，補一個 `S9_deviation` 是
   localized extension，不是 invasive change。依任務定義，這類 gap 不構成從零開發的理由。

3. **scheduler-kernel 有一個實測可重現的正確性缺陷（非風格問題）**：
   把「T07 星期四全天 unavailable」這個 Probe 3 的需求，用現有 API 逐節套用之後，
   **只有「該教師剛好有課」的那一節會被寫進 `decisions`**；`no_change_needed` 分支直接回傳原 problem，
   意圖被丟棄。結果：重新 Generate 之後 **T07 又被排回星期四**（實測 `L15→(Thu,p1)`、`L23→(Thu,p4)`）。
   這正是 Probe 4 問的「下一次 Generate 是否可能忘記這次人工決定」——答案是**會忘記**。

**對「03 是否足夠」的直接回答：** CSS 在 domain model、solver 表達力、衝突定位、production 成熟度、
導入摩擦五個面向全面領先，且領先幅度不是靠 README 宣稱，而是靠我實際執行其 solver 與讀取其 463 個
測試函式確認的。TWschools（下稱 **TW**）是 2020 年停更的研究原型，測試套件在 HEAD 無法 import，
不應列入採用候選。

**唯一誠實的答案：** 對「scheduler-kernel 目前真正擁有、且 03 難以低成本取得的 capability 是什麼？」
——**沒有。**

---

## 2. Repo / Version / Commit Inspected

| # | Repo | Commit | 日期 | 規模 | 狀態 |
|---|---|---|---|---|---|
| A | `yjlhuang/scheduler-kernel`（本地工作副本） | `d9cf211` | 2026-09 | src 1,101 LOC / 17 tests | 17 passed（實測） |
| B | `begin0808/Course_Scheduling_System` | `a53acdf`（v1.2.4） | 活躍 | backend 15,254 LOC + Vue frontend / 463 test fns、52 test files | CI 綠燈徽章；solver 可獨立匯入執行（實測） |
| C | `klin059/course-scheduling-TWschools` | `3a8c04b` | 2020-09-08（末次 commit） | 3,514 LOC | **測試套件在 HEAD 無法執行**（實測，見 §5） |

驗證環境：Windows 10 / Python 3.13 / scheduler-kernel 的 `.venv`（含 ortools）。
CSS 的 `app.solver` 套件依其 `problem.py` 的純度約定，在 `PYTHONPATH=css/backend` 下
**無需 DB／FastAPI／認證即可匯入並求解**，本稽核的 Probe 1 與 Probe 5 即以此方式實測。

---

## 3. Domain Model Matrix

標示：**N**=Native first-class／**I**=Representable indirectly／**W**=Workaround only／**X**=Not representable／**?**=Unclear

| # | 概念 | A scheduler-kernel | B CSS | C TW |
|---|---|---|---|---|
| 1 | lesson / scheduling unit | **N** `Lesson` (`domain.py:43`) | **N** `AssignmentSpec` + 內部 lesson 拆解；`periods_per_week` 原生 | **N** `Course`（每週每節各一個物件，`BaseModel.py:9`） |
| 2 | teacher | **N** `TeacherProfile` (`domain.py:36`) | **N** `TeacherSpec`，含 `base_periods`/`admin_reduction`/`is_external` | **N** `Teacher` + `HomeroomTeacher`/`SubjectTeacher` 子類 |
| 3 | class / homeroom | **N** 但僅為 `tuple[str,...]` 字串（`domain.py:81`），無屬性 | **N** `ClassSpec`，含 `grade`/`period_table_id`/`homeroom_teacher_id` | **N** 以 `(grade, homeroom_number)` 表示；homeroom 同時是 Room |
| 4 | student group / cohort | **X** 無任何 cohort 概念 | **N** `UnitSpec(unit_type="group", class_ids=(...))`（`problem.py:112`） | **I** 以 split-and-merge 的課程命名與 `same_period` 表達，無顯式 cohort 物件 |
| 5 | room / room kind | **I** `Room(kind, assigned_class_id)`；一般教室以 `assigned_class_id` 綁班 | **N** `RoomSpec(room_type, subject_ids, capacity)` + `required_room_type`/`lock_room` | **N** `Room(list_of_subject, allowed_homeroom)` |
| 6 | timeslot | **N** `Slot(day, period)`（`domain.py:11`） | **N** `Slot` 含 `start_min`/`end_min`；**多套節次表**與跨表牆鐘重疊判定（`slots_overlap`） | **N** `(day, period_ind)` tuple；**週一~週五、7 節寫死**（`populate_set_of_periods`） |
| 7 | availability | **N** `TeacherProfile.unavailable` | **N** `TeacherSpec.unavailable`（H4，以縮小定義域實作） | **N** `Teacher.restricted_periods`／`Room.restricted_periods`（`BaseModel.py:388,452`） |
| 8 | hard constraint | **N** Constraint Registry 8 條，含 category/relaxable 分類（`registry.py`） | **N** H1–H10，含 `RELAXABLE_CODES`、scope 化的 `ConstraintTag` | **W** 無 constraint 物件；硬約束散落在 `get_feasible_periods_*` 的集合運算 |
| 9 | soft preference | **N** 但語意極薄，見 Probe 2 | **N** S1–S8 加權，含**公平性 S8**與權重上限論證（`MAX_WEIGHT=100`） | **X** 偏好是**全域寫死的模組常數**（`scoring.py:12-20`），依教師*類型*而非個人 |
| 10 | grouped / split / merged teaching | **X** `validate()` 主動拒絕（`domain.py:162-169`） | **N** group unit + 協同教學（`teacher_ids: tuple`） | **I** split-and-merge 靠課程命名慣例 + `same_period` requirement |
| 11 | same-slot synchronization | **X** 完全不存在 | **N** `course_key()` 讓 group 全員共用同一組 lesson 變數（`problem.py:185`）＝ H7 | **N** `requirements["same_period"]`（`BaseModel.py:280`），支援 N>2 |
| 12 | consecutive lessons | **X** 無連堂概念 | **N** `BlockSpec(size, count)` + `_runs()` 保證不跨午休 | **N** `requirements["consecutive"]`，但僅支援 2 連堂且節次配對寫死 |
| 13 | authoritative schedule state | **N** `ScheduleState` + `content_fingerprint`（`domain.py:110`） | **N** `Timetable` 多草稿 + 唯一 published（`models/timetable.py:22`） | **W** `Status` 是可變的 in-memory 物件圖，靠 `deepcopy` 存檔 |
| 14 | accepted manual decisions / locks | **I** `SchedulingDecision` 但**只有一種 kind**（`teacher_avoid_slot`），且寫入有漏（Probe 3/4） | **N** `FixedEntry.locked`（H9 硬約束，`problem.py:155`）+ audit_log | **I** `list_of_fixed_Courses` / `fix_assigned_Courses()` |
| 15 | previous schedule / draft / version | **N** `version`/`parent_version`/`is_stale_for()`（`state.py:49`） | **N** draft/published 狀態機 + 學期複製 + 備份還原 | **X** 無版本概念 |

**矩陣層級的結論：** A 在第 4、10、11、12 四項是 **Not representable**——其中 10、11 是 `validate()`
主動拒絕，不是「還沒寫」。這四項正是台灣高中選修分流排課的核心。

---

## 4. Reality Probe Results

所有 probe 皆為實際執行，腳本置於 scratchpad，未進入任何 repo。

### Probe 1 — 數 A／數 B 同步 cohort

| 檢查項 | A | B | C |
|---|---|---|---|
| 自然表示 split cohort | **否**（ValueError） | **是**（group unit） | 部分（命名慣例） |
| parallel lessons 必須 same-slot | **否** | **是** | **是** |
| 支援 >2 units 的同步群 | **否** | **是（實測 3 個）** | **是**（zhes 問題實際用 3 個課程名） |
| teacher unavailability 傳播至全群 | 不適用 | **是（實測）** | 是（`get_feasible_periods_by_requirement` 取交集） |
| 共同時段不足時如何報告 | 不適用 | `preflight` + `explain()` 具名定位 | 僅「Assigned N out of M」 |

**A 的實測輸出：**

```
PROBE 1a: multi-class lesson   -> REJECTED -> ValueError: Phase 0.5 supports exactly one class per lesson: LX
PROBE 1b: multi-teacher lesson -> REJECTED -> ValueError: Phase 0.5 supports exactly one teacher per lesson: LY
SchedulingDecision kinds allowed: Literal['teacher_avoid_slot']
```

`Lesson` 雖有 `class_ids`/`teacher_ids: tuple`（`domain.py:46,48`），但 `class_id`/`teacher_id`
property 一律取 `[0]`，solver 也只用單數形式（`engine.py` 的 `by_class_slot`/`by_teacher_slot`）。
**欄位形狀是預留，語意未實作，且被 validator 封死。**

**B 的實測輸出（無 DB，直接驅動 `app.solver.model_builder.solve`）：**

```
course_key: 數A -> ('unit',1) / 數B -> ('unit',1) / 數B(二) -> ('unit',1)
unit_slot_consumption (group => max, not sum): 4
solve status: optimal
   數A    : [(1,1),(1,5),(2,1),(5,4)]
   數B    : [(1,1),(1,5),(2,1),(5,4)]
   數B(二) : [(1,1),(1,5),(2,1),(5,4)]
all 3 units share IDENTICAL slots? True
any Thursday slot used by the group? NONE
=> teacher unavailability propagated to the WHOLE sync group? YES
```

B 採用的 abstraction 是「**跑班群組**」：group 內的多門課共用同一個 `course_key`，
因此在模型裡是**同一個 course 的同一批 lesson 變數**，同進同出是結構性保證而非附加約束。
班級的時段消耗用 `max` 而非 `sum`（`problem.py:205`）。B 另有 pre-flight 檢查
`group_shape_mismatch`，群組內節數不一致會在求解前擋下（其自身測試 `test_model_builder.py:187` 涵蓋）。

### Probe 2 — Teacher-specific preferences

| 檢查項 | A | B | C |
|---|---|---|---|
| preference 可 per-teacher | **是** | **是**（`TeacherSpec.avoid/prefer`，`problem.py:74-75`） | **否**（全域常數，依教師類型） |
| 是否只有 global soft-rule weight | 否（per-preference `weight`） | 否（per-teacher 集合 + 全域權重 S1） | **是** |
| unknown / indifferent 與 negative 區分 | **語意上否** | 否（空集合即無偏好） | 否 |
| conflicting preferences 如何計分 | 線性加總 | 線性加總 + **S8 公平性項**平衡各教師未達成率 | 不適用 |
| preference provenance | `note` 欄位 + 4 值 enum | 無 | 無 |

**對 A 的嚴格檢查（實測）：** `PreferenceMode` 有 `prefer/avoid/indifferent/unknown` 四值，
README 與 registry 都把「unknown 與 indifferent 不產生懲罰」列為設計特色。

第一次測試用原 fixture 跑，四種 mode 的 objective 全是 0.0——**該測試不具鑑別力**，
因為課表有餘裕，solver 免費就避開了目標時段。改用能鑑別的設計重測：
把 T05 的可用時段壓到恰好兩格（`d2p5`、`d0p1`），其兩堂課被迫佔滿，
**被 avoid 的 `d2p5` 無法被騰空**：

```
mode=unknown      -> optimal  objective=0.0
mode=indifferent  -> optimal  objective=0.0
mode=avoid        -> optimal  objective=5.0
mode=prefer       -> optimal  objective=0.0

unknown == indifferent ? True
avoid   != unknown     ? True   (測試此時具鑑別力)
```

`avoid` 確實產生懲罰（5.0 = weight），證明測試有效；
而 `indifferent` 與 `unknown` 仍然完全相同。
根本證據在程式碼——`engine.py`：`if preference.mode not in {"avoid","prefer"}: continue`，
且 `repair/service.py` 的 `evaluate_quality()` 同樣只在 `avoid`/`prefer` 上分支。
**`indifferent` 與 `unknown` 走完全相同的程式路徑，對求解無任何行為差異。**
這個區分目前是 **metadata / provenance，不是 solver 語意**。這是誠實記錄，不是缺陷——
但不得當作 capability 差異。

**C 案例（避免同一天同時出現第一節與最後一節）三套系統都表達不了。**
這是 conditional / pairwise 規則；A 的 `TeacherPreference.slots` 與 B 的 `avoid` 都是**平坦的格位集合**，
懲罰項可加、彼此獨立。A 實測編碼結果：

```
penalty = w*occupied(d0p1) + w*occupied(d0p5)   # 各自獨立
```

即「只上第一節」也會被罰，與 C 老師的真實意思不符。
**Probe 2 不是 A 的乾淨勝場；正確描述是：A 的 preference 有較豐富的 provenance 欄位，
B 有實際起作用的公平性目標項，而三套都無法表達條件式偏好。**

### Probe 3 — Minimal-change repair

| 檢查項 | A | B | C |
|---|---|---|---|
| 真正 optimization-based repair | **是**（`baseline` + `change_weight`，目標函數項） | **否**（H9 硬鎖 + `add_hint()` best-effort） | 否 |
| 能 lock unaffected assignments | 是（`fixed=`） | **是**（H9，且可在部分排課中選擇性放寬） | 是（`fix_assigned_Courses`） |
| preservation 如何定義 | `preservation_ratio = 1 - changed/total` | 無量化指標 | 無 |
| 考慮 teacher days / gaps / preference degradation | **僅量測，未最佳化** | **放進目標函數**（S3 每日節數、S4 空堂、S6 連續節數） | 部分（scoring 的全域常數） |
| 否則只能人工拖曳或全重排 | — | 另有完整**調代課工作流**（見下） | 只能全重排 |

**A 的實測（Probe 3 原案：T07 星期四全天 unavailable）：**
`repair_teacher_slot(problem, baseline, teacher_id, avoid_slot)` **只接受單一 `Slot`**，
無法直接表達「整天」。逐節迴圈的實測結果：

```
d3p1: no_change_needed   d3p2: no_change_needed
d3p3: success  changed=('L15',)  locked=23  preservation=0.958
d3p4: no_change_needed   d3p5: no_change_needed
```

最終 T07 星期四確實淨空，且與「一次性最小變動」的對照組結果相同（皆只動 `L15` 一堂）。
**但注意這不是同一件事**：迴圈是 5 次串接求解，每次以前一次結果為 baseline；
在更密的課表上，貪婪串接不保證得到全域最小變動。

**A 的 quality vector 實測：**

```
before: QualityVector(change_cost=0, teacher_preference_cost=0, teacher_days=20, teacher_gaps=3)
after : QualityVector(change_cost=1, teacher_preference_cost=0, teacher_days=20, teacher_gaps=3)
```

`teacher_days` / `teacher_gaps` 在 `repair/service.py` 被計算並回報，
但 `engine.solve()` 的目標函數只有 `S1_TEACHER_SLOT` + `P1_MAIN_SPREAD` + `change_weight`。
**這兩個指標是被量測、從未被最佳化的。** B 則把對應概念（S3/S4/S6）直接放進目標函數。
因此「是否考慮 teacher days / gaps」這一格，**實質上應判給 B**。

**B 的答案分兩層：**
(a) 重排層——H9 硬鎖保住不受影響的格位，`_hints()` 把既有草稿餵成求解提示
（`model_builder.py:594`，註解明言「重排時盡量少動已排好的課」），但**提示是軟的，CP-SAT 可丟棄**，
沒有偏離量的目標項；
(b) 營運層——`leaves` → `AffectedPeriod` 展開 → `substitution_recommender` 代課推薦 →
`swap_options` 列出數週內真正換得成的調課組合 → 指派即生效 → 通知 → audit_log。
對「某位老師某天請假」這個真實高頻情境，B 的答案是**調代課工作流**，而不是重解整張課表。

**B 的 hint 保留率實測（本稽核補測，量化這個 gap 的大小）：**
建構 6 班 / 120 lessons / 12 教師 / 每班 30 格的 fixture，先求解，
再把結果以 `locked=False` 的 `fixed_entries` 餵回（即 `_hints()` 路徑），
然後封鎖一位教師的星期四後重解。為排除「目標函數改善造成的移動」這個干擾，
以 `SolverConfig.hard_only()`（關閉全部軟約束）執行，兩次求解皆為 `optimal`：

```
total lessons              : 120
lessons FORCED to move     : 5      (該教師的星期四課)
lessons that actually moved: 89
preservation ratio         : 0.258
collateral movement        : 84 lessons moved beyond the forced minimum
```

**只有 5 堂非動不可，實際卻動了 89 堂。** `add_hint()` 是軟提示，
CP-SAT 在找到任一可行解後即無誘因維持原位。
這證明「B 缺少偏離量目標項」**不是裝飾性差異，而是實質差異**——
教學組長會看到整張課表被打散，正是 `_hints()` docstring 想避免卻未達成的結果。

（註：A 在其 `small_school` fixture 上實測 preservation 0.958，但兩者 fixture 不同、
規模不同，**不構成直接可比的數字**；此處只證明 B 的 hint 路徑本身保留率低。）

### Probe 4 — Upstream change after scheduling

| 檢查項 | A | B | C |
|---|---|---|---|
| authoritative source 如何更新 | 手動重建 `SchoolProblem` dataclass | DB（`CourseAssignment` / `AssignmentTeacher`） | 改 Python 腳本 |
| derived schedule 是否知道自己 stale | **是**（`content_fingerprint`，實測） | 部分（draft/published 狀態；未見內容雜湊式 staleness） | 否 |
| 能否局部 repair | **否**（無對應入口） | 部分（鎖定 + 重解） | 否 |
| accepted decision 是否持久化 | **有漏**（見下） | 是（DB + audit_log） | 否 |
| 下一次 Generate 是否可能忘記人工決定 | **會忘記（實測）** | 不會（「該師週四不可排」存於 `TeacherSpec.unavailable` 對應的 teacher 資料表；H9 另外持久化的是**鎖定格位**） | 不適用 |

**A 的 stale 偵測實測（T03→T09 改派）：**

```
old fingerprint: 1bc2c28d0160d4d1
new fingerprint: a40f55ec40f69105
is old schedule stale for new problem? True
validator says: ('schedule problem fingerprint is stale',)
```

這一項 A 做得乾淨，是真實優點。

**但 A 的 accepted-decision 持久化有可重現缺陷：**

```
decisions recorded: [('T07', 3, 3)]          # 只有「本來就有課」的那一節
T07 Thursday placements after a fresh Generate: [('L15', 1), ('L23', 4)]
=> LEAKED BACK onto Thursday
```

**最精確、不需要任何組合論證的陳述：**
呼叫 `repair_teacher_slot(problem, baseline, T, s)` 就是在聲明「T 不要排在 s」。
但當 T 在 s 剛好沒課時，函式走 `no_change_needed` 分支，
**直接回傳原 `problem`，不附加任何 `SchedulingDecision`**（`repair/service.py`）——
請求被靜默丟棄。於是後續的 Generate 可以把 T 排進一個使用者已明確拒絕的時段。
這在單次呼叫的層級就成立，與「用單格 API 表達整天」無關。

在 Probe 3 的整天情境中，後果是：五次呼叫只有 d3p3 被記錄，
重新 Generate 後 T07 被排回星期四第 1、4 節——**人工決定被遺忘**。
此外 `SchedulingDecision.kind` 只有 `teacher_avoid_slot` 一種（`domain.py:59`），
Probe 4 的「教師由 T03 改成 T09」這類 upstream 決定**沒有任何可持久化的表示**。

### Probe 5 — Multi-constraint explanation

**A：** 本案例無法照原題建構——A 沒有 synchronization 概念。改建構最接近的交互作用案例
（T09、T10 各自只能在星期四，各自單獨可行；同時存在時 6 堂實驗課擠不進星期四的 5 個實驗室格位）：

```
A only (T09 Thursday-only)  -> optimal
B only (T10 Thursday-only)  -> optimal
A + B together              -> infeasible

status: infeasible | diagnostic_complete: False
preflight conflicts: 0        (每個必要條件單獨都通過)
verified_relaxations: 1
   - H5_AVAIL -> optimal | 實際關閉「教師不可排時段」後可排出課表
limitations:
   - 目前只做必要條件檢查與一次關閉一個 constraint family 的試驗；
     多因衝突可能未被列出，結果不是完整診斷或 MUS。
```

- UNKNOWN 與 INFEASIBLE **有區分**（1ms 預算實測回 `unknown`、`diagnostic_complete=False`，
  且明確拒絕做 relaxation 因果宣稱）——這一點 A 做得嚴謹。
- 方法是 **pre-flight 必要條件檢查 + single-rule deletion（整個 constraint family）**，非 MUS/unsat core。
- **無法指出具體 teacher / class / room**：`H5_AVAIL` 是全校所有教師的一個 family，
  報告說不出「是 T09 和 T10 和那間實驗室湊在一起」。
- diagnostic limitations **對使用者透明**（`limitations` 字串 + `diagnostic_complete` 旗標）。

**B：** 照原題建構（同步群組 + 星期四 unavailability），實測：

```
sync group only  (no Thursday block) -> optimal
Thursday block only (no sync group)  -> optimal
BOTH together                        -> infeasible

status: infeasible | source: analysis | mode: each | explained: True
headline: 以下 1 項各自都是瓶頸,放寬其中任何一項即可排出課表
  [H4] scope=teacher:數A師 relaxable=True
    msg: 教師數A師 有 5 格不可排時段,扣除後只剩 20 格可安排 4 節課,擋住了排課
    detail: {'assigned': 4, 'available': 20, 'unavailable': 5}
```

- **能指出具體 teacher**（entity-specific），且每條結論都被一次真實求解驗證過。
- 有 `each` / `joint` / `structural` 三態（`conflict_explainer.py:219-266`），
  `_joint()` 會在「沒有單一項能解決」時找一組夠小的組合——**這是 A 完全沒有的能力**。
- UNKNOWN 有保守處理：`_Prober` 在 `unknown` 時把 `certain=False`，`explain()` 在基準解回 unknown
  時回報 `status="unknown"`（`conflict_explainer.py:154`），不會誤報 infeasible。
- 刻意不用 CP-SAT assumption/unsat core，並在 docstring 記錄實測理由
  （enforcement literal 使 presolve 認不出鴿籠結構，0.8 秒 → 60 秒證不完）。

**但 B 在此案例踩到了 Probe 5 明文警告的陷阱。** 它報告的**結論正確**（放寬數 A 師的不可排時段
確實就能排出來，且經真實求解驗證），但附帶的**因果敘述不成立**：
「只剩 20 格可安排 4 節課,擋住了排課」——20 格排 4 節根本不是瓶頸，這段數字自相矛盾。
真正原因是同步群組把三位教師的可用時段取交集後只剩 2 格。
成因在 `_unavailable_cause()`（`conflict_explainer.py:386`）**用固定模板另外算一組容量數字**，
與「這個旋鈕為何是關鍵」的實際理由脫鉤。
更根本的限制是 `RELAXABLE_CODES = ("H4","H9","H10")`——**H7（群組同時段）不在旋鈕清單中，
也不可放寬，所以 B 的 explain 在結構上永遠無法把成因歸給同步群組本身。**

**Probe 5 綜合判讀：** B 的診斷**能力**明顯較強（entity-specific、joint 模式、求解驗證）；
A 的診斷**紀律**較嚴（明確的 `diagnostic_complete=False` 與 limitations，不做超出證據的宣稱）。
兩者的弱點不同：A 沉默而誠實，B 具體但敘述可能失真。**這是 Category D（research advantage），
不是產品能力優勢**——因為 A 的誠實是靠「幾乎不做宣稱」換來的。

---

## 5. Solver / Engineering Audit

### Correctness

| | A | B | C |
|---|---|---|---|
| independent validator | **有**（`solver/validator.py`，不信任 CP-SAT 模型，從 materialized schedule 重驗） | **有**（`solver/validator.py` 310 LOC，另有 `services/conflict_checker.py` 374 LOC 供單格即時檢查） | 無獨立 validator；靠 `assign_course_period` 內的 assertion |
| infeasible / unknown semantics | **清楚**（`unknown` 不做因果宣稱） | **清楚**（`certain` 旗標；unknown 保守視為未證明可行） | **無此概念**——排不進的課留在 `list_of_unassigned_Courses`，以 `UNASSIGNED_COURSE_PENALTY=100000` 計分（`scoring.py:20,174`） |
| hard constraint enforcement | 模型內 + 事後驗證 | 模型內 + 事後驗證 + API 層檢查 | 指派時 assertion |
| regression tests | 17 passed（實測） | 463 test functions / 52 files；CI 含**遷移與架構文件同步閘門** | **4 tests, all ERROR**（見下） |

**C 的測試套件在 HEAD 無法執行（實測）：** 2020-08-28 的 `reorganize files` commit 把模組移入
`eduscheduler/` 套件並改用相對匯入（`from . import BaseModel`），但 `testing/*.py` 仍是扁平匯入
（`import BaseModel as bm`）。最寬容的路徑設定下仍然全數 ImportError：

```
Ran 4 tests in 0.000s
FAILED (errors=4)
ImportError: attempted relative import with no known parent package
```

且 `unittest_course_search.py` 需要的 `status.pkl` fixture 不在 repo 中。

### Search / scalability

| | A | B | C |
|---|---|---|---|
| solver family | CP-SAT（OR-Tools） | CP-SAT（OR-Tools） | 自製 LNS + 隨機重啟（`CourseScheduling.py`） |
| variable formulation | `x[lesson, slot, room]` 三元布林 | `x[course, lesson, start-candidate]` + 獨立 `y[assignment, room]`；候選已預先剔除不可排時段 | 無變數；直接在物件圖上指派 |
| 已知擴展特性 | 24 班 / 840 lessons / 42,000 vars → 15.8s optimal（`docs/phase05-scaling-results.json`） | 有背景 worker + 進度回報 + 可取消（`workers/solve_job.py`）；為長時間求解設計 | README 宣稱 994 courses / 66 teachers / 49 rooms，「two weeks → minutes」 |
| realistic fixture evidence | `dense_school_6`：6 班 / 210 lessons / 35 格 = **100% 飽和**（實測），但僅 10 位教師、4 個科目 | 內建多學制 fixture（國小/國中/普高/綜高/技高），`tests/fixtures/vocational.py` 含跑班群組 | `zhes_scheduling_problem.py` 537 行**寫死**的單一學校案例 |
| timeout handling | `max_time_in_seconds`，逾時回 `unknown` | `SolveControl` + 求解回呼 + 逐步預算（`STEP_SECONDS=15`、`DEFAULT_MAX_SECONDS=60`） | `max_iteration` 上限，逾限即回傳部分解 |

**A 的 formulation 有一個值得記錄的成本：** 變數是 `lesson × slot × room` 的稠密三元組
（`engine.py` 的三層迴圈），24 班就到 42,000 變數。B 的 `x[course, lesson, candidate]`
在建模時就把教師不可排時段剔出定義域（`model_builder.py:223`，註解明言「比加約束便宜」），
且跑班群組整組共用一組變數，變數成長較緩。**兩者不在同一個 benchmark 上比較過，
本稽核不宣稱效能優劣**——只記錄 formulation 差異。

### Objective

| | A | B | C |
|---|---|---|---|
| 目標分解 | 3 項：S1 偏好、P1 主科分散、change_weight | 8 項：S1–S8，逐項可關（權重 0） | 6 類全域常數 |
| 權重 | per-preference `weight`；`change_weight=100` 硬編預設 | `DEFAULT_WEIGHTS` + **`MAX_WEIGHT=100` 的正確性論證**（軟約束總和須 < 放寬硬約束 1000 < 整節不排入 10000，否則 solver 會理性地丟課） | 模組常數，無上限論證 |
| explainability | 目標值為單一純量，無分項 | `solver/report.py` 368 LOC 產生分項報告 | 無 |
| preference semantics | 4 值 enum（但 2 值無行為差異，見 Probe 2） | 2 值集合（avoid/prefer），空=無偏好 | 依教師類型的全域規則 |
| fairness | **無** | **有**（S8：平衡各教師偏好未達成率） | 部分（鐘點教師集中天數） |

B 的 `MAX_WEIGHT` 註解是本次稽核見到最成熟的單一工程論證：它把權重上限論證成
**部分排課的正確性前提**，而非美觀限制。A 沒有等價的論證，因為 A 沒有部分排課。

### Repair / Explain

已於 Probe 3–5 詳述，此處不重複。

### Production maturity

| 面向 | A | B | C |
|---|---|---|---|
| persistence | 無 DB（JSON fixture + in-memory） | PostgreSQL + Alembic（17 支遷移） | pickle 檔 |
| import/export | 無 | Excel 匯入（含可下載範本，`services/importer.py`）；匯出 Excel/PDF(內嵌中文字型)/PNG/zip | 讀 `timetable/*.xlsx`，輸出 DataFrame |
| UI | 無（CLI 輸出 JSON） | Vue 前端，拖拉式週課表、單格衝突檢查 <100ms | Tkinter/webbrowser 小工具（`app/`，689 LOC） |
| authentication / RBAC | 無 | **有**（4 角色：管理員/主任/組長/教師，`models/user.py:24`） | 無 |
| backups | 無 | 每日自動備份 + 手動備份/下載/上傳還原（還原前自動保護、還原後強制重登） | 無 |
| deployment | `uv sync` | Docker Compose 一鍵 + `install.ps1`/`install.sh` 互動安裝腳本 | 手動 |
| audit log | 無 | **有**（`models/audit.py`，帳號刪除後保留軌跡） | 無 |
| version / draft management | `ScheduleState.version`/`parent_version` | 多草稿 + 唯一 published + 學期複製 | 無 |
| substitution workflow | 無 | **完整**（請假→受影響節次→代課推薦→調課驗證→指派→站內+Email 通知→A4 公告列印→月結鐘點 Excel） | 無 |

**依任務要求，不因 A 刻意沒有 production shell 就忽略這些。** 上表右欄代表
**若繼續從零蓋，需要重新支付的成本**：DB schema + 17 支遷移、認證與 RBAC、
備份還原、稽核、匯入匯出（含中文字型 PDF）、前端、部署腳本、調代課全流程。
以 B 的 backend 15,254 LOC + frontend 推估，這是**數千至上萬行、數人月**等級的重複投入，
且其中絕大多數與排課演算法無關。

### Adoption Cost / Friction Audit

對象假設：一位目前用 Excel／人工排課、沒有 solver 或 AI 背景的教學組長。

| 步驟 | A scheduler-kernel | B CSS | C TW |
|---|---|---|---|
| installation / deployment | 需裝 Python + `uv`，命令列 | 裝 Docker → 下載 `install.ps1`/`install.sh` → 回答校名/管理員密碼/埠號三個問題（金鑰自動產生、埠號衝突自動閃開） | 需裝 Python + pandas，手動跑腳本 |
| account / login | 無（也代表多人協作無從談起） | 有（管理員帳號於安裝時建立） | 無 |
| initial master-data setup | **手寫 JSON fixture** | 設定精靈（`wizard`，多步驟狀態機）+ 多學制節次表範本 + demo 資料 | **改 537 行 Python 腳本** |
| existing timetable import | **無** | Excel 匯入，四種實體（科目/教師/班級/配課）各有可下載範本 | 讀特定格式 xlsx |
| constraint configuration | 編輯 JSON | UI 表單 + 權重設定（S1–S8 可關） | **改 library 原始碼**——ZHES 專屬的年級/科目規則寫死在 `BaseModel.py` 的 `get_feasible_periods_by_grade_and_subject()` 裡，換一所學校要改套件本身 |
| 使用者須學會的概念 | CP-SAT 狀態、constraint code、JSON schema | 配課、跑班群組、連堂、硬/軟約束（以教務語言呈現） | Python、物件圖、LNS 參數 |
| ongoing maintenance | 不適用 | Docker 更新 + 每日自動備份 | 無 |
| failure recovery / debugging | 讀 JSON 與 traceback | 衝突定位以教務語言具名 + 備份還原 + 稽核軌跡 | 讀 traceback |
| 是否需要另一位技術人員 | **是（必須）** | 安裝時可能需要一次；日常不需要 | **是（持續需要）** |
| recurring vs one-time | 每次改資料都要工程介入 | 一次性安裝 + 每學期資料維護 | 每次都要工程介入 |

**摩擦所換得的 benefit：**

- **B**：涵蓋排課 + 調代課全年流程。調代課是**高頻高痛**——排課一學期一次，請假代課天天發生。
  月結鐘點統計、A4 公告列印、Email 通知都是教學組長現在用人工在做的事。
  以「pain / expected benefit ↔ adoption + switching + maintenance cost」衡量，B 的摩擦有明確對價。
- **A**：目前對教學組長的 expected benefit **為零**——沒有任何非工程師可用的入口。
  這不是貶低；A 的 README 明白宣告 Phase 0.5 只驗證三條 execution path。
  但依任務要求，**不得因「未來可以做得很簡單」給分**。
- **C**：一次性解決過一所學校的真實大型問題（994 courses），但成果綁在寫死的腳本裡，
  換校即需重寫，且套件已停更五年、測試無法執行。

**降低摩擦最合理的方法（A/B/C/D 四選一）：**

**選 A——改善／fork 03 的 onboarding。** 但必須附帶一個證據上的修正：
**目前沒有證據顯示 03 的 adoption cost 過高。** 03 已經有一鍵安裝腳本、設定精靈、
Excel 匯入範本、demo 資料、多學制範本與部署手冊。問題的前提（「03 technical capability 已足夠，
但 adoption cost 過高」）在本次稽核中**未被證實**。
若實地測試後確認仍有摩擦，合理順序是 A（改善 onboarding）→ B（加薄層 adapter），
兩者都是對 03 的貢獻或 fork，成本遠低於 C。
**明確反對 D→C 的推論**：即使存在 UX friction，也不構成從零重寫的理由——
重寫要重新支付本節 production 表格中的全部成本，而那些成本與 UX friction 無關。

---

## 6. Gap Classification

### Category A — 競品已解決（不構成 scheduler-kernel 存在理由）

- split cohort / 跑班群組（B：`UnitSpec`）
- same-slot synchronization，含 N>2（B：`course_key`；C：`same_period`）
- 連堂 / block（B：`BlockSpec`）
- 協同教學多教師（B：`teacher_ids: tuple`）
- per-teacher avoid/prefer（B：`TeacherSpec.avoid/prefer`）
- 硬鎖定格位（B：H9）
- entity-specific 衝突定位 + joint 模式（B：`conflict_explainer`）
- 教師每日節數／空堂／連續節數進入目標函數（B：S3/S4/S6）
- 公平性目標項（B：S8）
- 多套節次表與跨表牆鐘重疊（B：`slots_overlap`）
- 部分排課（B：`Relaxation`）

### Category B — 小幅競品 gap（合理可 fork / contribute，**不得當作從零開發理由**）

- **baseline-deviation 目標項**：B 只有 H9 硬鎖 + `add_hint()`，缺「與原課表偏離量」的懲罰項。
  **實測 gap 大小：preservation 0.258（5 堂該動、實際動 89 堂），屬實質差異。**
  補法：在 `_objective()` 加一個 `add("S9", self._s9_deviation())`，
  而 `_h9_locked()` 的放寬分支已經有現成的 per-cell `moved` 懲罰可直接沿用
  （`model_builder.py:654-658`），另加 `DEFAULT_WEIGHTS["S9"]` 與 `SOFT_NAMES["S9"]`。
  **localized extension。**
- **preservation 量化指標**（`preservation_ratio`）：純計算，可在 `report.py` 加。
- **content-hash staleness 偵測**：B 有 draft/published 狀態機但未見內容雜湊；可加一欄。
- **conditional / pairwise preference**（A、B 皆缺）：需擴充 preference 資料結構與一個
  reified 布林變數，對 B 是新增一個 S 項，非架構改動。

### Category C — 架構 gap（才可能構成獨立 kernel 的技術理由）

**本次稽核未在 scheduler-kernel 找到任何一項。**

反向則存在：**B 相對 A 有多項 Category C gap**——A 要支援 Probe 1 必須改寫
`Lesson`/`validate()`/`engine.py` 的 `by_class_slot`/`by_teacher_slot` 索引結構、
新增 group 抽象與 `course_key` 等價物，這是 domain model + solver formulation 的同時改動。

### Category D — 僅研究優勢（不得自動升格為產品優勢）

- **診斷紀律**：`diagnostic_complete` 旗標 + `limitations` 字串 + UNKNOWN 時拒絕因果宣稱。
  B 的 explain 能力更強但敘述可能失真（Probe 5 實證）；A 的誠實是靠「幾乎不做宣稱」換來的。
  這是可以移植到 B 的**做法**（在 `Cause` 加 `certain` 與 limitations 欄位），不是 A 獨有的能力。
- **Constraint Registry 的五層分類**（physical / explicit institutional / tacit domain /
  negotiable policy / soft preference）：概念清晰，但尚未證明使用者在意，且 B 的
  `RELAXABLE_CODES` + `ConstraintTag(scope)` 已達成實務等效。
- **preference provenance 欄位**（4 值 enum + `note`）：目前 2 值無行為差異（Probe 2 實證）。

### Category E — scheduler-kernel deficit（明確記錄，不淡化）

- **Probe 1 完全不可表達**，且是 validator 主動拒絕（`domain.py:162-169`）。
- **accepted decision 持久化有可重現缺陷**：Probe 3/4 實測「T07 星期四」意圖遺失、
  重新 Generate 後排回星期四。
- **`SchedulingDecision` 只有一種 kind**，upstream 改派（Probe 4）無法持久化。
- **teacher days / gaps 只量測不最佳化**；B 已放進目標函數。
- **無公平性考量**；B 有 S8。
- **無連堂、無多節次表、無部分排課、無 block**。
- **Explain 無法指出具體實體**，只能說「關掉 H5_AVAIL 這個 family 就有解」。
- **`indifferent` 與 `unknown` 行為完全相同**，README／registry 的表述高於實作。
- **無 DB／UI／認證／備份／稽核／匯入匯出／調代課**——依任務要求列為「從零繼續蓋需重新支付的成本」。
- **測試量級差距**：17 vs 463 test functions。

---

## 7. Build / Fork / Adopt Evidence Matrix

| Capability | A scheduler-kernel | B CSS | C TWschools | Gap depth | Evidence |
|---|---|---|---|---|---|
| split cohort / 跑班群組 | **X** | **N** | I | **C**（對 A） | A `domain.py:162-169` 實測 ValueError；B `problem.py:112` + 實測 3 成員群組 optimal |
| same-slot sync（N>2） | **X** | **N** | **N** | **C**（對 A） | B `problem.py:185` `course_key`；實測三單位時段完全相同；C `BaseModel.py:280` |
| unavailability 傳播至同步群 | n/a | **N** | **N** | **C**（對 A） | B 實測：群組完全不用星期四 |
| per-teacher preference | **N** | **N** | **X** | A | A `domain.py:29`；B `problem.py:74-75`；C `scoring.py:12-20` 全域常數 |
| conditional / pairwise preference | **X** | **X** | **X** | **B**（三方皆缺） | A 實測：懲罰項獨立可加 |
| unknown vs indifferent 語意 | **I（僅 metadata）** | — | — | **D** | 實測 objective 相同；`engine.py` 同一 continue 分支 |
| preference fairness | **X** | **N** | I | **E** | B `_s8_fairness()` |
| 硬鎖定格位 | **N** | **N** | **I** | A | A `fixed=`；B `model_builder.py:623` H9 |
| baseline-deviation 目標項 | **N** | **X**（僅 hint） | **X** | **B** | A `engine.py` `change_weight`；B `model_builder.py:594` `_hints()` 註明提示是軟的 |
| preservation 量化 | **N** | **X** | **X** | **B** | A `preservation_ratio` |
| teacher days / gaps 最佳化 | **X（僅量測）** | **N** | I | **E** | A `repair/service.py` 算但不入目標；B S3/S4/S6 |
| 多節次表 / 跨表時段 | **X** | **N** | **X** | **E** | B `slots_overlap()` |
| 連堂 / block | **X** | **N** | **I** | **E** | B `BlockSpec` + `_runs()` |
| INFEASIBLE vs UNKNOWN | **N** | **N** | **X** | A | A 實測 1ms→unknown；B `certain` 旗標；C 只有 unassigned 計分 |
| 衝突定位方法 | preflight + single-family deletion | preflight + per-entity deletion + **joint** + structural | **無** | **E** | A `explain/service.py`；B `conflict_explainer.py:219-266` |
| explain 指出具體實體 | **X** | **N** | — | **E** | A 實測只回 `H5_AVAIL`；B 實測回 `teacher:數A師` |
| explain 因果敘述正確性 | 保守但沉默 | **具體但可能失真** | — | **D** | B 實測：「20 格排 4 節擋住排課」不成立（`conflict_explainer.py:386`） |
| 診斷侷限對使用者透明 | **N** | I | **X** | **D** | A `diagnostic_complete` + `limitations` |
| content-hash staleness | **N** | I | **X** | **B** | A `state.py:49` 實測 |
| accepted decision 持久化 | **有漏（實測）** | **N** | **X** | **E** | A 實測 leak back；B DB + audit_log |
| 部分排課 | **X** | **N** | I | **E** | B `Relaxation` + `MAX_WEIGHT` 論證 |
| independent validator | **N** | **N** | **X** | A | A/B 皆有 `solver/validator.py` |
| regression tests | 17 | **463** | **0 可執行** | **E** | 實測 |
| DB / 匯入匯出 / UI / RBAC / 備份 / 稽核 / 調代課 | **全無** | **全有** | 全無 | **E** | §5 production 表 |

### 若選 Adopt 03

**會得到什麼：**
完整可部署的單校系統——CP-SAT 排課引擎（H1–H10 / S1–S8）、跑班群組與協同教學、連堂、
多學制節次表、entity-specific 衝突定位（含 joint 模式）、部分排課、多草稿版本管理、
Excel 匯入與 Excel/PDF/PNG 匯出、拖拉式課表 UI、RBAC、稽核軌跡、每日備份與還原、
Docker 一鍵部署，以及**完整調代課工作流**（請假→代課推薦→調課驗證→通知→月結鐘點）。
463 個測試與含文件同步閘門的 CI。MIT 授權。

**還缺什麼：**

1. minimal-change repair 的偏離量目標項（現為 H9 硬鎖 + 軟提示）與 preservation 量化指標。
2. conditional / pairwise 教師偏好（Probe 2 的 C 案例）。
3. 衝突敘述的因果正確性——`_unavailable_cause()` 的模板數字可能與實際關鍵性脫鉤；
   且 H7 不可放寬，explain 結構上無法歸因於同步群組。
4. content-hash 式的 derived-artifact staleness。
5. （未驗證）真實學校規模的求解效能——本稽核未做效能 benchmark。

### 若選 Fork 03

**最小需要修改的 architecture / module：**

- `solver/model_builder.py`：新增 `_s9_deviation()` 一個方法 + `_objective()` 一行 `add("S9", ...)`。
- `solver/problem.py`：`DEFAULT_WEIGHTS` / `SOFT_NAMES` 各加一筆 `S9`；
  （偏好擴充時）`TeacherSpec` 加一個 conditional rule 欄位。
- `solver/conflict_explainer.py`：`Cause` 加 `certain` / `limitations` 欄位；
  把 `_describe()` 的模板數字改為「只在 pre-flight 真的算出瓶頸時才陳述數字」。
- `solver/report.py`：加 preservation 指標。

**估計：localized extension，不是 invasive change。**

最強證據不是 `_hints()`，而是 **`_h9_locked()` 的「放寬」分支已經寫好了一個 per-cell 偏離懲罰**
（`model_builder.py:654-658`）：

```python
moved = self.m.new_bool_var(f"r9_{f.assignment_id}_{f.weekday}_{f.period_no}")
self.m.add(sum(lits) + moved == 1)
self.relaxed.append(self.relax.violation_penalty * moved)
```

這正是 `S9` 所需的形狀——對每一個 `fixed_entries` 格位生成一個「被搬走」布林變數並計入懲罰。
要做的只是把它從「僅在放寬 H9 時啟用、用 `violation_penalty` 計價」
改成「對未鎖定的 `fixed_entries` 也適用、用 `cfg.weight("S9")` 計價」。

這同時預先回應了對本 Fork 方案最明顯的反駁：因為同長度的 lesson 可互換
（`_break_symmetry` 強制位置遞增），**per-lesson 的偏離項在 B 的模型裡沒有良好定義**；
per-cell 的形式才有——而上面的程式碼顯示 B 已經把它蓋好了。

其餘理由：`_objective()` 已是 `add(code, expr)` 樣板；`fixed_entries` 已貫通至模型；
軟約束權重有 `MAX_WEIGHT` 的既定上限論證，新增一項不破壞既有正確性前提。
`app.solver` 套件不依賴 ORM（有 `test_purity.py` 把關），可獨立測試——
本稽核已實證可在無 DB 環境下驅動。

### 若繼續 scheduler-kernel

**它目前真正擁有、且 03 難以低成本取得的 capability 是什麼？**

**沒有。**

最接近的兩項都不合格：

- `change_weight` 偏離量目標項——是真實差異，但對 03 是 Category B 的 localized extension
  （上節已列出具體改法）。
- 診斷紀律（`diagnostic_complete` / `limitations`）——是 Category D，且其「誠實」建立在
  診斷能力較弱之上：A 說不出是哪位教師，所以也不會說錯。移植這套紀律到 03 是加兩個欄位。

---

## 8. Unknowns / Things Not Proven

誠實列出本次稽核**沒有**證明的事：

1. **未做效能 benchmark 比較。** A 的 scaling 數字來自其自身 `docs/phase05-scaling-results.json`
   （24 班 / 840 lessons / 15.8s），B 的效能**完全未測**。任務明文禁止用單一 benchmark 宣布勝負，
   本稽核亦未宣稱任一方較快。
2. **未執行 B 的完整測試套件。** 463 這個數字來自 `grep -c "def test_"` 計數與檔案清點，
   未實際安裝 FastAPI/PostgreSQL 依賴跑過。已實測的是其 `app.solver` 套件可獨立匯入並正確求解。
3. **未執行 B 的前端、UI、調代課工作流。** 這些的評估來自程式碼與 migration 讀取，非實機操作。
4. **未驗證 C 的 994 courses 宣稱。** 其測試套件無法執行，`status.pkl` 不在 repo，未嘗試重跑 ZHES 案例。
5. **未實地測試教學組長的 onboarding。** Adoption 評估基於安裝腳本、wizard 程式碼與
   匯入範本的存在，**不是**使用者測試。「03 的 adoption cost 是否過高」因此仍是 open question——
   本稽核只能說「沒有證據顯示過高」。
6. **A 的 dense fixture 代表性有限**：6 班 / 210 lessons 雖達 100% 格位飽和，但只有 10 位教師、
   4 個科目、無專科教室競爭（僅 1 間 LAB）、無跑班、無連堂。與真實高中的密度結構不同。
7. **未評估三者的長期維護風險**（B 的 bus factor、對單一維護者的依賴等），這需要社群與
   commit 歷史分析，超出本次程式碼稽核範圍。
8. **B 的衝突敘述失真問題只在我建構的單一案例上觀察到**，未系統性量化其發生頻率。

---

## 9. Recommended Next Experiment

依「先證偽、成本由低到高」排序：

**E1（最高優先，1–2 天）——對 03 做真實資料的端到端導入測試。**
取一所真實學校的一學期資料，走完 `install.sh` → wizard → Excel 匯入 → 自動排課 → 衝突定位 → 匯出。
量測：到「第一次得到可信結果」的實際時數、卡住的步驟、教學組長看不懂的用語。
**這是唯一能證實或推翻「03 adoption cost 過高」這個前提的實驗**，而整份決策都懸在這個前提上。
若 E1 順利，Build 的討論即可結束。

**E2（1 天）——在 03 的 fork 上實作 `S9_deviation` 並驗證 Category B 判定。**
若如本稽核推估只需 `_s9_deviation()` + `_objective()` 一行 + 兩筆 weights，
則「minimal-change repair 需要獨立 kernel」的論點被實證推翻。
若實作過程發現必須改動 `_Course` 結構或候選生成，則該項應升格為 Category C，本稽核的判定需修正。
**這個實驗的設計目的是給 scheduler-kernel 一個翻案機會。**

**E3（0.5 天）——修 scheduler-kernel 的 accepted-decision 漏失。**
無論最後決定 Adopt/Fork/Build，Probe 3/4 實測的「意圖遺失 → 重新 Generate 排回星期四」
是正確性缺陷。至少應讓 `no_change_needed` 分支也寫入 `SchedulingDecision`，
並補一個 regression test（「repair 後重新 Generate，該教師不得再出現在該時段」）。
本稽核依任務要求**未實作任何修補**。

**E4（若 E1 顯示摩擦確實過高）——在 03 上加薄層 import adapter（選項 B）。**
不要另做獨立工具。先確認 03 的 API 邊界是否足以支撐外掛匯入層
（`app.solver` 的純度約定顯示邊界是乾淨的）。

**不建議的實驗：** 繼續擴充 scheduler-kernel 的 Phase 1 功能。
在 E1/E2 有結果之前，任何新增功能都是在未驗證的前提上加碼；
而 Probe 1 所需的改動（domain model + solver formulation 同時改寫）
正是 03 已經付過一次的成本。

---

## 附錄：本稽核實際執行過的驗證

| Probe | 對象 | 方式 | 結果 |
|---|---|---|---|
| 多班級 lesson | A | `domain.validate()` | ValueError（Not representable） |
| 多教師 lesson | A | `domain.validate()` | ValueError |
| indifferent vs unknown | A | 三種 mode 求解比對 | objective 相同（無行為差異） |
| Probe 3 整天 repair | A | 逐節迴圈 `repair_teacher_slot` | 淨空成功，但僅 1 節寫入 decisions |
| Probe 4 decision 持久化 | A | 帶 decisions 重新 Generate | **排回星期四（leak back）** |
| Probe 4 staleness | A | 改派教師後比對 fingerprint | 正確偵測 stale |
| Probe 5 交互作用 | A | 建構 T09/T10 + LAB 案例 | infeasible；僅回 family 級 `H5_AVAIL` |
| UNKNOWN 區分 | A | 1ms 時限 | 回 `unknown`，拒絕因果宣稱 |
| 17 tests | A | `pytest -q` | 17 passed |
| Probe 1 同步群組 | B | 無 DB 直接驅動 `model_builder.solve` | 3 單位時段完全相同；星期四完全避開 |
| Probe 5 原案 | B | 無 DB 驅動 `conflict_explainer.explain` | 正確 infeasible；具名 `teacher:數A師`；**敘述數字不成立** |
| hint 保留率 | B | 120 lessons，結果餵回為未鎖定 `fixed_entries` 後封鎖教師重解（`hard_only`，兩次皆 optimal） | 5 堂被迫移動，實際動 89 堂；preservation 0.258 |
| preference 鑑別力複測 | A | 壓縮 T05 可用時段使 avoid 目標無法騰空 | avoid=5.0 vs indifferent/unknown=0.0 |
| 測試套件 | C | `unittest discover`（最寬容路徑） | 4 tests, all ERROR |
| 活躍度 | C | `git log` | 末次 commit 2020-09-08 |

驗證腳本位於 session scratchpad（`probe_kernel*.py`、`probe_css*.py`、`probe_pref.py`），
未進入任何 repo。競品 clone 位於 scratchpad `eval/`，全程唯讀。

---

## 關於 AI 協作方式

本專案使用多模型協作開發。依任務要求，**這是 development process，不是 scheduler capability，
本稽核未將其列為任何一項產品差異。** 檢查過是否已轉化為可驗證的產品能力：

- 更可靠的 constraint elicitation — **未見**（A 無 elicitation 介面）
- 更好的 Explain — **未見**（Probe 5 實測 A 的診斷解析度低於 B）
- 更好的 minimal repair — 部分（`change_weight`，但為 Category B）
- 更容易吸收學校特有規則 — **未見**（A 需改 JSON 與程式碼；B 有 UI 與匯入）
