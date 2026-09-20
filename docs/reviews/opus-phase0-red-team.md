# scheduler-kernel Phase 0 — Architecture Red-Team Review
(2026-09-20, commit a1b7010)

## 結論

概念層面站得住，實作層面還沒證明 Phase 0 宣稱的三件事。
**現在不該直接拿真實學校 constraints 壓測** —— 不是因為 kernel 爛，而是因為目前的 fixture 與三個機制會讓真實資料產生的失敗「無法解讀」：你會分不出「這條校規太難」和「solver timeout 了」、分不出「repair 成功」和「repair 失敗但指標顯示 100%」。

先做一份真實密度的 fixture，再修文末列的 5 個 gate（估計數天），之後再壓測。屆時真實資料產生的失敗才會是關於學校規則的訊號，而不是關於 kernel 儀表板的雜訊。

## 先講對的地方（這些不要動）

- `unknown` vs `indifferent` 分開，且兩者都不給隱性懲罰 —— 正確，且有 07-tsai 的田野證據支撐。這是整份 domain model 裡最有價值的一個決定。
- Constraint Registry 的「授權軸」分類是對的切法：它回答「誰有權放寬」，而不是把所有規則攤成一張清單。
- authoritative state + version-pinned derived artifact 的方向正確，直接對應 Tsai 案「改了主課表、游泳分配沒跟著更新」。
- Generate / Explain / Repair 三分，以及「Draft 1 需要人工審查不代表生成失敗」的立場，都是對的。
- `validate_schedule()` 不信任 CP-SAT、從實體化結果重新驗證 —— 正確的偏執。

## 八個攻擊點 → 對應發現

| 攻擊點 | 判定 | 見 |
|---|---|---|
| domain model 過早抽象或抽錯？ | 兩者都有：room 過度抽象、lesson↔teacher/class 抽得不夠、課程計畫整個缺席 | S5、B2 |
| constraint registry 分類夠不夠裝台灣規則？ | 授權軸對，但缺「規則形狀」軸；而且沒接上 solver | S1 |
| Generate/Explain/Repair 共享錯誤假設？ | 是，四個，全在 `solve()` 裡 | B3a、S3、B4、B5 |
| Explain 會不會「看似合理但不完整」？ | 會，實測三種：完全沉默、多因回空、可報出假因果 | B4、B3c |
| 95.83% 會不會掩蓋 quality degradation？ | 會，而且更糟：它是恆等式，失敗時回滿分，且對品質雙向盲 | B5 |
| teacher preference 的衝突/未表態/權重？ | 未表態處理正確（保留）；衝突零偵測、權重零正規化、`prefer` 語意寫反 | S2 |
| state / derived artifact 的 boundary 合理嗎？ | 方向對，但兩個方向都欠規格 | B6、S7 |
| 哪些東西現在不該做？ | 七項，從發現推導 | 文末 |

---

# BLOCKER

## B1. synthetic school 不是學校，Generate 通過不代表任何事

`data/fixtures/small_school.json`：6 班 x 4 堂 = 24 lessons，25 個時段。

**太稀疏**（實測）：

- 班級佔用率 **16%**（真實國中約 94%：33–35 節 / 35 格）
- 最忙的老師 3 節 / 25 格（真實約 18–22 / 35）
- 生成結果裡**同一時刻最多只有 2 個班在上課** —— 24 堂課攤在 25 格上，平均每格約 1 堂，這是稀疏度造成的，與房間數無關

**而且房間模型是反的**（另一個獨立問題）：6 班只有 3 間教室，方向和台灣國中小相反（學生不動、老師動，每班有固定班級教室）。實測生成結果裡每個班一週都在 `R-A / R-B / LAB` 三間教室之間跳來跳去，而 `validate_schedule()` 回 `()` 判定完全合法。若 fixture 真的做到密集，3 間教室就會變成全校並行上課的上限 —— 也就是說 fixture 裡唯一會真正咬住的硬限制 H3_ROOM，正好是最不像台灣的那一條。

在 84% 空隙上，任何 constraint 都會通過、任何 repair 都會成功、objective 都會是 0.0（實測）。`test_generate` 綠燈不構成證據。

## B2. 建模成本是模型選擇造成的，不是調參能解決的

實測純 Python 建模時間（CP-SAT 還沒開始跑）：

| 班級數 | lessons | rooms = 共用池（現況） | rooms = 固定班級教室 |
|---|---|---|---|
| 3  | 99  | 0.8s  | 0.3s |
| 6  | 198 | 5.3s  | 0.9s |
| 12 | 396 | **63.7s** | 4.9s |

兩個原因疊乘：(1) `engine.py` 每個限制式都在巢狀迴圈裡對整個 `x.items()` 全掃描，而 `|x| = lessons x slots x rooms`；(2) 每堂 general 課都對全校每一間 general 教室開變數，但台灣的 general 課本來就綁死在自己的班級教室。

30 班國中在這個結構下光建模就是十分鐘等級。不是換 solver 參數或加 worker 能救的（`num_workers=1` 反而是次要問題），是 `Room` 語意選錯。

## B3. Explain 在 timeout 區間是不健全的（真實資料一定會進入這個區間）

**(a) `unknown` 被當成 `infeasible`。** `solve()` 把 OPTIMAL/FEASIBLE 以外全回成 `state=None`，呼叫端只檢查 `state is None`。實測：對一個**可行**的問題給緊時限，`explain_infeasibility()` 回 `status="unknown", conflicts=0, verified_relaxations=0` —— 形狀上就是「這所學校排不出來，而且沒有任何東西可以放寬」。

**(b) trial 的預算比 baseline 還少，而且是寫死的。** `service.py:56` 呼叫 `solve(problem)` 吃預設 10s，`service.py:62` 的每個 relaxation trial 寫死 3s。這不是偶發的時序問題 —— 程式碼路徑**保證** baseline 的預算嚴格大於每一個 trial（不需要任何計時實驗就能從原始碼證明）。於是「沒有任何放寬有效」會系統性變成 false negative，回報的放寬集合是 solver 速度的函數，不是邏輯的函數。

**(c) 純軟性項目被拿去做可行性試驗。** `relaxable_codes()` 回 `('H5_AVAIL','H6_DAILY_SUBJECT','P1_MAIN_SPREAD','S1_TEACHER_SLOT')`，後兩者只出現在 `model.minimize()` 裡，**數學上不可能影響可行性**，只影響搜尋速度。實測速度差確實存在且方向危險：同一問題 baseline@10s 得到 `feasible`（11.8s），關掉 P1 後 7.5s 就 `optimal`；關掉 S1 反而 `unknown`。

(a)+(c) 合起來是可達的假因果：baseline timeout 判為 infeasible，P1 trial 剛好跑出解，Explain 輸出「實際關閉『主科分散』後可排出課表」—— 一個關於可行性的因果宣稱，而它不可能為真。（試了 n=5/6 想端到端重現，兩邊都 timeout 沒抓到；但這是結構性缺陷，不需要重現才成立。）

## B4. Explain 對整類真實失敗完全沉默，而且從不指名實體

| 情境 | conflicts | verified_relaxations |
|---|---|---|
| 專科教室不足（10 堂實驗課、1 間實驗室、8 格） | `()` | `()` |
| 需同時放寬 H5 + H6 才可行 | 1 筆 teacher_capacity | `()` |
| 只有 H6 咬住 | `()` | 「關閉同科每日上限後可排出課表」 |

- 第一列是**完全空的解釋**，而專科教室不足是台灣最常見的真實成因之一。`_preflight` 只查教師容量，沒查班級容量、room_kind 容量、每科每日節數的算術下界。空結果和「查遍了真的沒救」在輸出上無法區分。
- 第二列：deletion filter 一次只關一個 code，多因並存就回空。文件承認不是 unsat core，但**輸出 payload 從來沒承認**，下游 UI 只會渲染成「無可放寬項目」。
- 第三列：訊息沒指名哪一班、哪一科。對 30 班的學校，「關閉教師不可排時段後可排出課表」不可行動 —— 沒有人會忽略全校老師的不可排時段。教務主任需要的是「T03 的週三下午那 2 格」。
- `conflicts` 和 `verified_relaxations` 在結構上沒有連結，沒有任何東西斷言前者是後者的成因，但讀的人一定會當成同一個故事。

## B5. 95.83% 不是量測，是恆等式；而且失敗時它回報滿分

**(i) 這個數字在 solver 執行前就決定了。** 所有非目標課程被 `fixed=` 硬綁在 baseline，而 H2 保證一位老師同一格最多一堂課，所以 `|targets| <= 1` 恆成立：`preservation_ratio == 1 - 1/N`。24 堂 -> 95.83%；132 堂 -> 99.24%。它量的是 fixture 大小。`test_repair` 的 `assert >= 0.95` 對任何 >=20 堂的 fixture 都不可能失敗。

**(ii) 完全失敗時回報 1.0。** 有兩條路徑都會回 ratio = 1.0，只有一條是缺陷：

- `repair/service.py:40` 的 `no_change_needed`（目標時段本來就沒課）回 `state=baseline`，ratio 1.0 是合理的。
- `repair/service.py:54` 的**無解路徑**回 `RepairResult(status, None, (), ...)` -> `changed=()` -> ratio = **1.0**。這條是缺陷。

實測 94% 密度下抽 12 次修復，2 次 `infeasible`，兩次都印 `preserve=1.0000`。而 `cli.py:53` 無條件輸出 `preservation_ratio`，旁邊是 `"schedule": null`。任何建在這個指標上的儀表板，都會在修復失敗當下顯示它最漂亮的數字 —— 而呼叫端無法從這個數字分辨自己落在哪一條路徑上。

**(iii) 它對 schedule quality 在兩個方向上都是盲的。** 重點不是「repair 一定會讓課表變差」，而是 **objective、validator、preservation_ratio 三者都看不見教師真正在意的那些量**，所以變好變壞都量不到：

- 出貨的 small_school：preserve 95.83%、objective 0.0 -> 0.0、`validate_schedule()` 回 `()` —— 但 C1 在 day1 多出一個**空堂**（第 1、3 節），T01 的**到校天數 2 -> 3**。
- 94% 密度下移動 `C02_English_3`：preserve 99.24%，class_gaps 7 -> 6、teacher-days 持平 —— 稍微變**好**，同樣量不到。

在台灣學校，班級空堂是學生管理問題，老師多跑一天是排課裡最政治性的一項。這兩件事不在 objective、不在 validator、不在指標裡。系統會回報「修復成功、保留 95.83%、0 違規」，而教務主任會退件；反過來，一次真正的改善也拿不到任何分數。

（補：`change_weight=100` / `baseline=` 那套機制在這條路徑上是死碼 —— 非目標課全被硬綁了。它是未被測試的程式碼，而 100 對上偏好權重 1–5 意味著：一旦 neighborhood 放寬，它會寧可違反 20 條偏好也不肯動一堂課。）

## B6. authoritative state 兩個方向都欠規格

**向上（這份課表回答的是哪一份問題？）** `ScheduleState` 只有 `placements / version / parent_version / status / created_at`，**沒有 `SchoolProblem` 的指紋**。老師離職、加一堂課、改 `max_same_subject_per_day`，這份 state 就默默失效而沒有東西偵測得到。`state_from_dict()` 的存在正好讓你可以載入一份無法與當前 problem 對帳的課表。而學校裡課務資料的變動頻率遠高於課表本身。目前只實作了 schedule -> artifact 這一跳；真正咬到 Tsai 案的是 problem -> schedule -> artifact，第一跳沒有。

**向下（哪些人的決定塑造了這份課表？）** `repair_teacher_slot(..., avoid_slot)` 把 `avoid_slot` 當一次性硬限制塞進單一次 `solve()`，**既沒寫回 problem，也沒寫進 state**。下一次 generate 會若無其事地把 T01 排回那一格，而且沒有紀錄顯示有人提過這個要求。修復接受的決定就這樣蒸發了。

這兩件是同一件事：authoritative state 不知道自己回答了什麼問題，也不記得自己承載了哪些人工決定。

---

# SHOULD FIX BEFORE REAL DATA

## S1. Registry 少了「規則形狀」軸，而且沒接上 solver

五個分類回答「誰可以放寬」，但沒回答「這條規則長什麼形狀」。solver 目前只能表達兩種形狀：**禁止某格**、**每日計數上限**。台灣至少還需要：

- **連堂 / adjacency**：作文 2 節連堂、理化實驗連堂；反過來體育不連堂
- **不排課日**（天的粒度，不是格的粒度）—— 台灣老師第一順位的訴求
- **每科各自的分散規則**（現在是一個全域 `max_same_subject_per_day: int`）
- **教師工作量平衡**（每日節數上限、連續授課上限）
- 導師第一節必須在班上、週三下午全校不排課

這些在 registry 裡**連位置都沒有**。`ConstraintDefinition` 沒有 `scope`、`params`、`source`、`confidence`、`authority`，但 `docs/constraint-registry.md` 明文要求 tacit rules 必須帶 source 和 confidence。文件和資料結構對不起來。

而且 registry **沒接上 solver**：`engine.py` 把四個 code 當字串硬寫死，`implemented: bool` 沒有任何東西驗證，往 registry 加一筆什麼也不會發生。現階段它是文件形狀的資料，不是機制。

`relaxable_codes()` 把「影響可行性的」和「純目標項」混在一起，這個分類錯誤直接漏進 Explain（B3c），不是裝飾性問題。

## S2. Teacher Preference Profile 的衝突、權重、語意

- **完全沒有衝突偵測。** 實測：同一位老師同時宣告 `prefer d0p1` 和 `avoid d0p1`，`validate()` 不報錯，兩個懲罰無聲抵銷。對自己 `unavailable` 的格子宣告 `prefer`，會在 objective 留下**永遠無法滿足的常數樓地板**（實測 objective = 5.0 而非 0.0），沒有東西指出「這條偏好永遠不可能被滿足」。
- **權重是自己申報的基數，沒有正規化、沒有上限、沒有額度。** 沒有東西擋得住 weight = 10^6。所有懲罰進同一個 `sum()`，一位老師申報的數字可以直接壓過其他所有老師加上兩條校務政策。典型的策略性謊報漏洞，在學校裡同時是政治漏洞。
- **`prefer` 的語意被寫成「你必須在這一格有課」。** `weight * (1 - occupied)` 懲罰的是老師**沒有**被排在那格。那是「請幫我排在這裡」，不是「如果要排我，我偏好這裡」。台灣老師絕大多數是後者，而且多半以「不排課日」表達 —— 天的粒度，目前只能拆成 7 個獨立加權的 slot avoid，於是「滿足 7 格中的 6 格」在 objective 看來接近成功、在老師看來是完全失敗。
- **沒有 provenance。** 只有 `note: str`。interview-guide 特地區分明示偏好與推論偏好，並警告不可未經確認就升級成校規，但資料結構裡沒有「誰說的、何時、是否確認、何時失效」。
- **完全沒有總體維度。** 老師之間的公平性無法表達，因為沒有每位老師的滿意度分數，只能最小化總和 —— 而最小化總和會系統性犧牲「犧牲起來最便宜的那個人」。

建議形狀（不是施工順序）：保留 unknown/indifferent；自由整數換成小的序數量表 + 每位老師的額度；`prefer` 改成條件式（只在被排到別處時才罰）；加「天」粒度的請求型別；加 provenance 與確認狀態；滿意度以**向量**回報。

## S3. objective 是一個無法拆解的純量

Generate / Explain / Repair 共用同一個 `minimize(sum(penalties))`，混了偏好權重（1–5）、分散權重（3）、變更權重（100），沒有分解。整個 codebase 沒有東西能回答「這次修復讓課表變好還變壞」。B5(iii) 是這個失敗的具體展現。在拆解之前不要擴大 repair neighborhood。

## S4. Repair 失敗是死路，三個能力無法組合

無解時回 `RepairResult("infeasible", None, (), ...)`，沒有任何診斷；而 `explain_infeasibility()` 只吃 `SchoolProblem`，**沒辦法問「為什麼這堂課移不走」**。實測 12 次修復有 2 次無解（94% 密度），使用者拿到的就是一個字。三個能力在設計上分開，但在**失敗路徑上完全沒接起來**。

（Repair 本身沒有我預期的脆弱：94% 密度下 12 次抽樣成功 10 次。真正的限制是 neighborhood 只有一步寬，**表達不了 swap** —— 而 swap 正是調課的本體，也正是他們引用的 case 06 class-swap-radar 的全部內容。）

## S5. domain model 抽錯的維度

- `Lesson.teacher_id` / `class_id` 都是單數。台灣常態需要多對多：協同教學、分組教學（英數分組，一班拆兩組同時上）、跨班合班（體育/社團/彈性）。文件說「a later phase may generalize」—— 但 `lesson_id` 是 `x[(lesson_id, slot, room_id)]`、`fixed`、`Placement`、`by_lesson`、validator、repair target、io 的承載鍵。改多對多是**改寫，不是擴充**，延遲成本持續變大。
- `Room` 當成開放字串 + 相等比對的共用池：既表達不了容量/場地共用，又逼出 B2 的成本。台灣的 general 課應該是綁定關係，不是分派問題。
- `is_main_subject: bool` 掛在 Lesson 上而不是科目上：24 列可以彼此矛盾，沒有驗證。
- `subject: str` 裸字串：沒有領域分組、沒有科目層級的規則掛載點。
- **缺一個抽象：課程計畫 / 節數表。** 輸入是攤平的 lesson 清單，「C1 每週需要 5 節國文」無法表達，所以 kernel 無法檢查課綱節數，也無法在節數變更時重新產生 lesson 清單。諷刺的是：他們在輸出側模型化了 derived artifact，卻沒在輸入側模型化 authoritative 課程計畫。

## S6. 「暴露未完成工作」的目標與 H4_COMPLETE 互相矛盾（已升級為 gate item 2）

`docs/research/01-kent-css.md` 寫 "automatic generation should expose unresolved work"，但 H4_COMPLETE 是硬限制且 `relaxable: False`，排不完就是整份 infeasible、一堂都排不出來。case 03 也提到 partial scheduling，同樣沒採納。對 human-in-the-loop 工具而言，「這 6 堂我排不進去」遠比「infeasible」可行動。

## S7. 小型正確性與衛生

- `cli.py` 的 `generate` **沒有呼叫 `validate_schedule()`**。「不信任 CP-SAT」的信任邊界只存在於測試裡，實際管線沒有執行。
- `version = str(uuid4())`：非內容定址。輸入沒變重跑一次會產生「新版本」的相同課表，兩份 state 無法用版本比較相等。
- `status: str = "draft"` 是沒有狀態轉換、沒有消費者的自由字串。Repair 的前提「鎖住已接受區域」在資料上**根本不存在** —— Repair 是無條件鎖住全部，不是因為誰標記了 accepted。
- `DependencyGraph.stale_for(v)` 回傳所有 `source != v` 的 artifact。那是「不相等」不是「過期」：分不出祖先與旁支，同時有 accepted 與 draft 時相對於兩者都全部過期。更重要的是粒度錯了：動一堂課會把 30 份班級課表全標過期，而學校要的是「只有 C1 和 T01 變了，通知這兩邊」。
- `time_limit_seconds` 是與問題規模無關的固定常數（10.0 / 3.0）。
- objective 有浮點噪訊（實測 5.000000000032756）。

---

# SAFE TO DEFER

- 連堂 / 多教師 / 多班級的**實作**（但 S5 的「鍵是單數」要現在就決定，它決定之後是擴充還是改寫）
- 正式 UI、登入、通知、報表、資料庫、調代課交易流程、SIS 匯入 —— README 已正確排除，維持
- minimum unsatisfiable core / MUS
- solver hints、warm start、多 worker、搜尋策略調校
- 學期 / 學年 / 多校 的多租戶結構
- `DerivedArtifact` 的實際產生器
- 教師工作量平衡、場地器材、雨天備案這類「再來一批 constraint」

---

# 現在不該做的事（從發現推導，不是從品味）

1. **不要加新的 constraint 類型。** fixture 有 84% 空隙，加什麼都會通過 —— 你是在對雜訊調參。
2. **不要做 minimum unsat core。** `unknown` 和 `infeasible` 還沒分開，在 timeout 上算出來的 core 沒有意義；而且便宜的必要條件檢查都還沒做完。
3. **不要擴大 repair neighborhood（swap、多課移動）。** objective 還沒拆解，你無法判斷一次修復是變好還變壞 —— B5(iii) 就是這個失敗本身。
4. **不要把 registry 做成 plugin 機制或 DSL。** 現在只有 8 條規則、2 種形狀。先用真實規則把形狀軸問清楚，不要先蓋框架。
5. **不要調 solver 參數。** 主要成本在 Python 建模迴圈（12 班 63.7s），在那裡優化是優化錯地方。
6. **不要為了 preservation metric 再加指標。** 先拆 objective，指標會自己長出來。
7. **不要開始做 UI / 持久化 / 權限。** 維持現有邊界。

---

# 第一個動作

**建一份真實密度的 fixture。**

最便宜、位在 B2 / B5 / B6 的上游，而且會把這份 review 裡三個斷言直接變成會紅的迴歸測試。規格：12–24 班、每班 33–35 節 / 35 格、每班固定班級教室（綁定而非分派）、專科教室真的稀缺、教師負擔 18–22 節、真實的不可排時段（週三下午研習）。

做完之後，通往「可以拿真實 constraints 壓測」的門檻是四件事：

1. `SolveResult` 把 `unknown` 和 `infeasible` 分開，呼叫端分別處理；Explain 在 `unknown` 時明說「未證明無解」而不是輸出解釋形狀的東西。relaxation trial 的預算 >= baseline，且只試會影響可行性的 code。
2. **部分排課（partial placement）**：讓 H4_COMPLETE 可以降級成「能排的排、排不掉的列出來」。這是把 30 班真實 constraints 丟進來之後**唯一會真正有用的輸出** —— 回一個 `infeasible` 等於什麼都沒有，回「這 6 堂排不進去，它們共用 T03 的週三」就是 Phase 0 Explain 真正的交付物。比第 3 項便宜、價值更高，可能該排在最前面。
3. `_preflight` 補齊便宜的必要條件：班級容量、room_kind 容量、每科每日算術下界；每個 conflict 與 relaxation 都要指名實體（哪位老師、哪一班、哪一科、哪幾格）。
4. objective 拆成具名分量（preference / spread / change / gap / teacher-days），`RepairResult` 回報 before-after 向量；`preservation_ratio` 在 `state is None` 時不得回 1.0。
5. `ScheduleState` 帶 `SchoolProblem` 指紋；repair 接受的決定寫回 authoritative 資料（帶 provenance），而不是留在函式參數裡蒸發。

這五件加上 fixture 大概是數天的工作量。做完之後真實資料產生的失敗才會是**關於學校規則的訊號**，而不是關於 kernel 儀表板的雜訊。

---

# 附錄：對 Phase 0.5 施工計畫的回應（2026-09-20，第二輪）

上面的 review 提交後，計畫端提出了一份 Phase 0.5「Make the tests honest」施工計畫，對本 review 的建議做了幾處修正。以下是逐項回應。**本附錄是追加，不修改上面任何內容。**

## 接受的修正

**「Phase 0 證明三條 execution path 跑得通」這個重新表述是準確的**，比本 review 原本的講法更精確。Phase 0 沒有證明 Generate / Explain / Repair 這三個*能力*成立，它證明的是三條程式路徑會跑完並回傳結構正確的東西。

**第一份 dense fixture 用 6 班而非 12–24 班 — 接受，這比本 review 的建議好。** 原建議把「密度語意」和「規模擴展」混成一件事；若一次跳 24 班，失敗時分不出是 semantics、scalability、explain 還是 repair 哪一層出問題。

但有一個細節要補（見下）。

**原 small_school 保留為 smoke test — 接受。** 補一點：保留它的同時，`test_repair` 裡那句 `assert preservation_ratio >= 0.95` 應該改寫或標註，否則它會繼續以「證據」的身分存在，而它不是。

**「先紅給我們看，不要偷偷修到綠」— 強烈背書。** 這是這份計畫裡最重要的一條紀律。

## 四點推回

### R1. B2 不該綁在單一 fixture 上

6 班對 B1 / B3 / B5 都夠：
- B1（密度）：6 班 × 33–35 節 = 94% 佔用，直接成立
- B3（unknown/infeasible）：實測 4 班 94% 密度在 10s 限制下只到 `feasible` 而非 `optimal`，6 班極可能落進 `unknown`，成立
- B5（preserve 恆等式）：與規模無關；198 堂時 ratio = 1 − 1/198 = **99.49%**，比 95.83% 更荒謬

**但對 B2 不夠。** 實測 6 班共用池建模 5.3s — 看起來只是「有點慢」。真正嚇人的是 12 班的 **63.7s**。若 B2 的證據只有 5.3s 這一個數字，它會被合理地降級成「效能待優化」，而它其實是 resource semantics 選錯。

建議：B2 的迴歸不要做成 fixture 檔，做成**以程式產生 6 / 12 / 24 班的 scaling 曲線測試**，斷言的是成長率與 pinned-homeroom 對照組的比值，不是單點秒數。這樣既保留分層隔離，又不稀釋 B2 的證據。

### R2. S5 的 schema decision 有三個案例，不是一個

本 review 的 S5 把「多對多」講成一件事，這不夠精確。實際上是三個不同的東西：

| 案例 | 形狀 | 複數鍵吸收得掉嗎 |
|---|---|---|
| 協同教學 | 2 師、1 班、1 室、1 格 | ✅ |
| 跨班合班（體育／社團／彈性） | 1 師、2 班、1 室、1 格 | ✅ |
| **分組教學**（英數分組） | 1 班拆 2 組、2 師、**2 室**、**同一格** | ❌ |

分組教學不是「一堂課有兩位老師」，而是**兩堂課共同佔用該班的同一格**。要表達它，`H1_CLASS` 必須從 `at_most_one` 改成 group-aware — 那是 **solver 改動，不是 schema 改動**。

所以 Phase 0.5 的 schema decision 必須明講它吸收哪幾個、哪個留給後面，否則會誤以為「鍵改複數 = 多對多解決了」。

**建議只做複數鍵**：`teacher_ids: tuple[str, ...]` / `class_ids: tuple[str, ...]`，Phase 0.5 在 `validate()` 裡斷言 `len == 1`。地基不被刻死，成本接近零，且完全可逆。

**建議不要現在發明 `CourseOffering / SchedulingUnit / LessonRequirement` 三層本體。** 那要有真實的課程計畫／節數表才做得好；現在做就是計畫端自己說要避免的 anticipatory architecture。缺「課程計畫」這個抽象（本 review S5 最後一段）是真的，但它的解法要等真實節數表，不是現在先蓋。

### R3. room_kind 容量的 preflight 不能 defer，要跟 fixture 同批

計畫把「完整 preflight」整包往後推。但新 fixture 的規格裡明寫「真的有稀缺專科教室」，而本 review B4 實測過：**專科教室不足時 Explain 回 `conflicts=()` + `verified_relaxations=()`，完全空白。**

等於特地造了一個會踩專科教室的 fixture，然後第一次踩到時得到一個讀不出來的紅燈。

這段是純算術（room_kind 需求數 vs 該 kind 房間數 × 時段數），大約 30 行，沒有 solver 參與。班級容量與每科每日算術下界同理。建議跟 gate item ①（UNKNOWN/INFEASIBLE correctness）同批出。

其餘的 preflight 擴充（指名實體、conflict 與 relaxation 的因果連結）可以延後，那些確實比較貴。

### R4. partial scheduling 的 defer 接受，但要設 tripwire；S6 的文件矛盾現在就改

**Defer 的理由成立**：等真實 failure 出現再決定 failure output 的形狀，避免 anticipatory architecture。而且 gate item 修完 resource semantics 之後，6 班 dense 很可能根本不會 infeasible，那就真的不需要。

**但要設一個明確的 tripwire**：如果 dense fixture 回 `infeasible` 而你看不出是哪幾堂卡住，那就是立刻把 partial scheduling 拉到最前面的訊號 — 不要在那個狀態下硬啃。

**另外 S6 有一半現在就該處理**：`docs/research/01-kent-css.md` 寫 "Useful concept: automatic generation should expose unresolved work"，宣稱已採納；但 H4_COMPLETE 是 `relaxable: False` 的硬限制，使這個概念在結構上不可能實現。這是**文件與程式碼互相矛盾**，不是功能缺口。改一句話的事，不必等能力做出來。

## 計畫漏掉的兩個一行修正

計畫的 step 4 寫「修 `UNKNOWN / INFEASIBLE / FEASIBLE` correctness，feasibility explanation 禁止拿純 soft objective 冒充 relaxation」— 涵蓋了 B3(a) 與 B3(c)，但：

1. **漏了 B3(b)**：`explain/service.py:56` 的 baseline 吃預設 `time_limit_seconds=10.0`，而 `service.py:62` 的每個 relaxation trial 寫死 `3.0`。程式碼路徑**保證** baseline 的預算嚴格大於每一個 trial，於是「沒有任何放寬有效」會系統性變成 false negative。一行。

2. **漏了 S7 的第一項**：`cli.py` 的 `generate` 沒有呼叫 `validate_schedule()`。「不信任 CP-SAT」的信任邊界目前只存在於測試裡，實際管線沒有執行。而 step 2 的整個紀律（先紅給我們看）建立在管線真的會驗證上。一行。

## 施工順序的判斷

計畫把「修 resource semantics」排在「修 UNKNOWN/INFEASIBLE」之前 — **這個順序是對的**。修完 resource semantics 之後 timeout 可能大幅減少，那會改變 UNKNOWN 處理的緊迫程度與正確做法。反過來排會在錯誤的壓力下設計 timeout 語意。


