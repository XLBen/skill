---
project: skill-suite-quality
status: draft
brief-hash:
---

# skill-suite-quality requirement brief

用户认为 grill（需求拷问）效果好，但后续流程（contract-review → construction）
的最终产出质量远低于规划质量。经四个真实项目（choujiang / quant / xhs / 魔塔）
的工件勘察与业界调研（Spec Kit / Kiro / BMAD / OpenSpec / BDD / SRE / 曳光弹），
质量流失环节已定位。修复方案（owner 已拍板，详见 JSON BD-03/BD-05、BC-01..05）：

**v0.1 方案概要（纯提示词层，引擎不动）**

1. **运行逻辑换 MVP/薄切片**：contract-review 默认流程改为
   Phase 0 风险探针（最险假设最小真实触碰，带探针预算 BC-04）
   → 第一轮契约只覆盖最薄端到端切片（曳光弹，契约规模受 BC-03 预算约束）
   → 切片真实验证通过 → 经独立的切片增量（SI）迭代加厚，直至满足需求；
   CR 只保留给契约与现实不符的异常恢复，避免正常增量污染故障语义。
2. **切片内规则**：验收标准用 Given-When-Then 量化断言模板
   （具体数据/可判定断言，空产物即失败）；失败熔断（同一失败签名
   第 3 次连续失败后立即升级 owner，禁止第 4 次普通重试，升级带 BC-05
   证据载荷）；测试与实现作者分离（独立 test-author 从规格生成验收测试、
   冻结测试 hash、先行确认失败后才允许 step-executor 写实现）。
3. **仪式瘦身**：ADR 化记录、文档:代码比例超限警告不阻断（BD-04）。
4. **验证与分期**：v0.1 只改/新增 SKILL.md、references 和命令模板
   （BC-01），不改引擎；下个真实项目必须产出 MVP observation report，
   按 BC-02 可观察判据验证 BA-01（提示层是否够用），
   证伪则二期启动引擎硬化（重试上限/空产物断言/比例警告）。
   grill 仅允许接口级微调（BN-01）；魔塔继续按旧规则跑完（BD-02）。

```json brief
{
  "schema_version": 1,
  "revision": 7,
  "status": "draft",
  "summary": "grill 层良好；下游六类流失（验证不碰现实/自证闭环/风险后置/无熔断/仪式膨胀/交付漂移）。修复逻辑定为 MVP：套件默认流程改为'Phase 0 风险探针 + 薄端到端切片先行 + SI 正常增量加厚'，CR 仅处理异常恢复；v0.1 纯提示词层（引擎不动），新增独立 test-author、明确三次熔断语义，并以必填 observation report 验证提示层是否足够，待 owner 整体确认后定稿",
  "items": [
    {
      "id": "BF-01",
      "kind": "fact",
      "statement": "套件链路为 grill（docs/brief.md）→ contract-review（/review 契约、/plan 编译 PLAN）→ construction（/build /resume /finish），reviewer 与 step-executor 为被调用子 skill",
      "source": "各 SKILL.md frontmatter 与 calls-skills 声明",
      "evidence_status": "verified"
    },
    {
      "id": "BF-02",
      "kind": "fact",
      "statement": "引擎 check.py（约 3000 行）只做确定性文书校验（哈希/账本/覆盖率/状态机），从不执行 V 命令、从不接触产品代码",
      "source": "scripts/check.py 模块 docstring；两个项目的 grep 证实无 subprocess/pytest/node 调用",
      "evidence_status": "verified"
    },
    {
      "id": "BF-03",
      "kind": "fact",
      "statement": "step-executor 每次只接收一个步骤 spec，在 minimal-diff 纪律下工作，禁止查看其他段落；代码与测试由同一执行者编写",
      "source": "step-executor/SKILL.md",
      "evidence_status": "verified"
    },
    {
      "id": "BF-04",
      "kind": "fact",
      "statement": "用户陈述：grill 满意；其余功能最终产出'一坨大的'；失败维度自选为全部五项并追加：测试形同虚设、过程毫无记忆点、上下文总结混乱",
      "source": "user-stated；后经四项目工件勘察佐证",
      "evidence_status": "verified"
    },
    {
      "id": "BF-05",
      "kind": "fact",
      "statement": "验证门语义空心化：choujiang 的 V-08 退出码 0 通过但数据库 0 行、25 篇中 21 篇 mojibake 漏判（验收记录.md:45,62-68）；xhs 的 V-06 打印'不可用'仍 EXIT=0（verify-capture.mjs:5,131），V-08/V-13'未配置/无产出'也退出 0；quant 的 V-00 机器部分全绿而 gate=blocked（ev-sv-i00-v00-001.json）",
      "source": "choujiang/xhs/quant 项目工件与脚本源码实测",
      "evidence_status": "verified"
    },
    {
      "id": "BF-06",
      "kind": "fact",
      "statement": "自证闭环：xhs 146/146 单测全绿但对象是执行者自造的假 DOM/假 chrome（MV3 入门级错误、选择器猜测均无法暴露），CR-01 在 7 步全绿后才发现扩展没有保存按钮；魔塔 V-02 的 expected 要求'与引擎对照值一致'但测试文件自声明'不测战斗公式'，同一 pytest 输出 hash 被记为两个步骤各自的验证",
      "source": "xhs trigger.test.mjs/fields.mjs、change-orders.md:46；魔塔 test_combat_model.py:7-8、事件账本 :40/:44",
      "evidence_status": "verified"
    },
    {
      "id": "BF-07",
      "kind": "fact",
      "statement": "风险验证后置：xhs 把唯一能验证核心假设（登录态可提取 A-01、可用 LLM A-02）的 e2e 排在最后，在零有效原料、未配置 LLM 的前提下建完全部蒸馏/索引管线；choujiang 人工真实验证排在最尾，最贵的否证信息最晚到达（CR-06 整周期方向作废）",
      "source": "xhs contract.md A-01/A-02 pending-verification + I-05 排序；choujiang build-log.md:104-136",
      "evidence_status": "verified"
    },
    {
      "id": "BF-08",
      "kind": "fact",
      "statement": "失败无熔断：quant 同一失败模式（+12 标注重跑 V-00）机械重复 16+ 轮、S-I00 达第 27 次 attempt、owner 手工标注 36 小时后 CR-002 把 920 个已计入配额的标注清零；xhs 的 CR 恢复策略是整体重放 3 遍（RPL3 零新代码提交、100+ 条纯仪式事件）；choujiang 前 6 步平均 9.3 次 attempt",
      "source": "quant workflow-events.jsonl 128 条统计、labels-hand.jsonl 时间戳、change-orders.md:53；xhs PLAN.md:93-103、git log；choujiang 账本统计",
      "evidence_status": "verified"
    },
    {
      "id": "BF-09",
      "kind": "fact",
      "statement": "仪式远超产品：choujiang 约 14.4k 行仪式文档对 3.2k 行产品代码（4.2:1）；quant 76KB/54 节点/17 个 V 的契约对应策略产品 0 行（全部 4.4k 行产出是标注合规元工具）；xhs 5000+ 行仪式对约 2500 行功能代码",
      "source": "三项目目录逐文件统计",
      "evidence_status": "verified"
    },
    {
      "id": "BF-10",
      "kind": "fact",
      "statement": "交付一致性漂移无人兜底：choujiang README 与 sources/__init__.py 在 CR-07 后与代码相反且 PLAN 工件路径与实际目录不符；魔塔 owner 重开后契约散文摘要与 JSON 不同步穿过两次终审；xhs 的 AnythingLLM docker-compose 残留入库违反本契约 B-01；xhs build-log 在 7 个提交前就停止更新（70KB 账本对 2KB 日志）",
      "source": "choujiang README.md:52、52pojie.py:95；魔塔 contract.md:37 vs :1485；xhs deploy/docker-compose.yml、build-log.md",
      "evidence_status": "verified"
    },
    {
      "id": "BF-11",
      "kind": "fact",
      "statement": "门禁可达性无人评估：quant 的 V-00 需要 ≥20 个终止结局标注，观测发生率 0.37%，manifest 耗尽预计也只能凑 2-4 条——发布前三轮 review 与两次 final-audit 均未算出'统计上不可达'这笔账",
      "source": "quant contract.md D-11、ev-sv-i00-v00-026 配额数据、change-orders.md:53",
      "evidence_status": "verified"
    },
    {
      "id": "BF-12",
      "kind": "fact",
      "statement": "grill/intake 层在四个项目均表现良好：魔塔 8 轮拷问 40/40 dispositions 合法；xhs 砍掉旧论文方案与 AnythingLLM 依赖；choujiang 三次方向否证均由流程拦截；与用户'grill 满意'的判断一致",
      "source": "四项目 brief.md 与事件账本",
      "evidence_status": "verified"
    },
    {
      "id": "BF-13",
      "kind": "fact",
      "statement": "魔塔（今日在施工）是目前最健康的一跑：测试为真断言、终审拦截过 P-02 覆盖缺口与不可执行变体；但存在 V-id 跨步骤共享、执行者自写测试、无施工期独立审计的结构风险，风险预计在 I-02（求解正确性）与 V-08（真实回放）阶段放大",
      "source": "魔塔 docs/ 全套工件与已产出源码勘察（只读）",
      "evidence_status": "verified"
    },
    {
      "id": "BA-01",
      "kind": "assumption",
      "statement": "待 MVP 验证的核心假设：提示词层的'现实触碰门+独立测试+熔断'足以显著改善产出质量，无需引擎强制（BC-01 的二期触发条件即此假设被证伪）",
      "source": "agent-analysis",
      "evidence_status": "unverified"
    },
    {
      "id": "BD-01",
      "kind": "decision",
      "question": "本次改进的范围是什么？",
      "choice": "先诊断再定：先找到质量流失环节，再决定改哪里",
      "rationale": "诊断已完成（BF-05..BF-13）；用户进一步指示先做业界调研再定改法",
      "owner_confirmed": true
    },
    {
      "id": "BD-02",
      "kind": "decision",
      "question": "正在施工的魔塔项目怎么处理？",
      "choice": "继续跑完，套件改进自下一个项目生效",
      "rationale": "魔塔已是最健康一跑且已产出真断言测试，停掉重跑浪费已验证成果",
      "owner_confirmed": true
    },
    {
      "id": "BD-03",
      "kind": "decision",
      "question": "修复逻辑：瀑布上打补丁，还是换成 MVP 迭代逻辑？",
      "choice": "薄切片+纯提示层：套件默认流程改为 Phase 0 风险探针 + 第一轮契约只覆盖最薄端到端切片（曳光弹）+ SI（slice increment）迭代加厚；CR 仅用于契约与现实不符的异常恢复；v0.1 只改或新增 SKILL.md/references/命令模板（引擎不动）；断言模板/熔断/测试分离作为切片内规则；二期引擎硬化以 MVP 验证结果为准",
      "rationale": "owner 提议 MVP 先行迭代，agent 认同为 BF-07/09 的根治法；也实践'最险假设先验证'于改造本身（检验 BA-01）",
      "owner_confirmed": true
    },
    {
      "id": "BD-04",
      "kind": "decision",
      "question": "'仪式文档 ≤ 产品代码'作为硬门禁还是警告？",
      "choice": "警告不阻断，由 owner 人工裁量",
      "rationale": "可量化但硬门可能误伤超小工具项目",
      "owner_confirmed": true
    },
    {
      "id": "BD-05",
      "kind": "decision",
      "question": "v0.1 的具体改动清单是什么？",
      "choice": "① contract-review：默认流程改为 Phase 0 风险探针→薄切片契约→SI 正常增量加厚，CR 仅处理异常恢复（重写 SKILL.md 工作流与 requirement-protocol/plan-template 参考）；② 验收模板：Given-When-Then 具体数据+可量化断言，空产物即失败（进 contract-template/evidence-protocol）；③ construction/SKILL.md+step-protocol：同失败签名第 3 次连续失败后强制升级并禁止第 4 次普通重试（带证据载荷）、恢复禁整体重放改定点返工；④ 新增独立 test-author/SKILL.md，从规格生成并冻结验收测试，step-executor 不得编辑冻结测试，reviewer 审计作者身份、red/green 顺序和测试 hash；⑤ 仪式瘦身：ADR 化记录+文档代码比例超限警告（BD-04）；⑥ 新增 MVP observation report 模板以承载 BC-02 观测；⑦ grill 仅接口级微调（BN-01）",
      "rationale": "BD-03 的落地分解；全部提示词层，满足 BC-01",
      "owner_confirmed": true
    },
    {
      "id": "BC-01",
      "kind": "constraint",
      "statement": "v0.1 不改 scripts/check.py 引擎：薄切片流程、探针、断言模板、熔断、测试分离全部以修改或新增 SKILL.md/references/命令模板的提示词层落地；允许新增独立 test-author skill 和 observation report 模板，但不新增 Python/Node 执行引擎；引擎级硬规则（重试上限/空产物断言/比例警告/测试文件写保护）列为二期候选，仅当 MVP 验证显示提示层约束不住执行者时启动",
      "source": "BD-03 的落地约束（owner 选定'纯提示层'）"
    },
    {
      "id": "BC-02",
      "kind": "constraint",
      "statement": "MVP 验证判据必须可观察（BA-01 的证伪条件）：下个真实项目必须生成 docs/mvp-observation.md，逐项记录 V 内容断言、产物非空、失败签名/attempt/耗时、test-author 与 implementation-author 的 subagent/session ID、冻结测试 hash、首轮切片预算与实际值、真实数据结果和 owner 验收；若出现任一——V 命令无真断言（只查退出码）、空产物通过、同一失败签名第 3 次失败后仍进行第 4 次普通重试、测试与实现作者相同或实现者修改冻结测试、薄切片契约超预算——即判定提示层约束失败，触发二期引擎硬化；无以上现象且 BS-01 达成则 BA-01 获得一次支持性证据而非永久成立",
      "source": "agent 对抗评审（四项目证据：机器可查仪式被严格执行，散文语义被弱化）"
    },
    {
      "id": "BC-03",
      "kind": "constraint",
      "statement": "薄切片的'薄'要有可核查预算：进入第一轮契约前必须声明 active P/F/I/V 数、PLAN segment 数、契约正文行数和预计产品代码增量的数字上限；具体值由项目风险决定并经 owner 确认，不得留空或事后补填，超限必须在继续施工前缩小切片或取得 owner 明示例外，防止 quant 式 76KB 契约对 0 行产品的膨胀复发",
      "source": "BF-09 教训"
    },
    {
      "id": "BC-04",
      "kind": "constraint",
      "statement": "Phase 0 风险探针必须带探针预算与最小副作用纪律：最小请求数、结果缓存、指数退避、禁止重复全量踩点——早碰现实不等于狠碰现实",
      "source": "choujiang CR-04 教训：一天 4 轮 smoke 把 IP 烧黑被 WAF 封锁"
    },
    {
      "id": "BC-05",
      "kind": "constraint",
      "statement": "熔断升级发生在同一失败签名第 3 次连续失败之后，第三次计入总尝试次数，升级后禁止第 4 次普通重试；升级必须携带计算好的证据载荷：失败签名、三次原始结果、已耗成本（attempt 数/时长）、按当前发生率的预测成本，以及至少两条可选路径；禁止无数据升级换取 owner 橡皮图章",
      "source": "quant 教训：owner 批准三次计划均无人计算'统计不可达'"
    },
    {
      "id": "BD-06",
      "kind": "decision",
      "question": "切片验证后的正常加厚是否继续复用 CR？",
      "choice": "不复用。新增 SI（slice increment）作为计划内增量：每个 SI 只描述新增/修改/移除的需求与受影响步骤，验证通过后合入当前契约基线；CR 保持现有语义，只处理事实、接口、范围或验收与现实不符的异常恢复",
      "rationale": "OpenSpec 将 proposed change/delta spec 与已生效 specs 分离并在 archive 时合并，说明正常增量和异常恢复应使用不同语义；这也避免每轮正常加厚触发 blocking CR 与故障审计",
      "owner_confirmed": true
    },
    {
      "id": "BD-07",
      "kind": "decision",
      "question": "v0.1 由谁生成验收测试，如何与实现者隔离？",
      "choice": "新增独立 test-author skill/subagent：只读取冻结规格和允许的测试上下文，先生成验收测试并确认 red，再把测试路径/hash 交给 construction；step-executor 只实现产品代码且不得编辑冻结测试；规格或测试错误必须停机走 CR，由 test-author 修订后重新冻结",
      "rationale": "BMAD TEA 已采用独立 Test Architect 和 ATDD→dev implements 的角色/阶段分离；在本套件中新增提示层 skill 比把写测试职责塞给只读 reviewer 更清晰，也不破坏 reviewer 的独立审计席位",
      "owner_confirmed": true
    },
    {
      "id": "BC-06",
      "kind": "constraint",
      "statement": "v0.1 的失败签名采用可人工复核的规范化规则：V ID + 命令/场景 ID + 失败断言名或异常类型 + 去除时间戳、绝对路径、随机 ID、堆栈行号后的首个稳定错误摘要；只有失败断言/异常类型或根因类别发生实质变化才重置连续计数，改文案、换 attempt ID、重复同一数据不得重置",
      "source": "Tenacity/Resilience4j 都将重试条件、attempt 上限和运行状态分开建模；本规则把该成熟模式映射到提示层，防止靠噪声规避熔断"
    },
    {
      "id": "BC-07",
      "kind": "constraint",
      "statement": "作者分离以不同 subagent/session ID 为最低标准，不要求不同模型或不同自然人；test-author 生成测试后记录 spec hash、测试文件列表和内容 hash，step-executor 的允许写集排除这些文件。实现者若认为测试错误，只能报告 blocker 并走 CR，不能直接改测；reviewer 在步骤完成前核对作者 ID、red 证据、green 证据和冻结 hash",
      "source": "BMAD TEA 的独立 Test Architect、ATDD red phase、dev implements 和后置 test-review 流程；github.com/bmad-code-org/bmad-method-test-architecture-enterprise"
    },
    {
      "id": "BC-08",
      "kind": "constraint",
      "statement": "SI 是正常增量而非恢复：只有当前切片通过真实验证后才能创建；每个 SI 使用 ADDED/MODIFIED/REMOVED delta，声明受影响 P/F/I/V 与预算，不重放未受影响步骤，验证后合入下一契约 revision。事实被证伪、接口不存在、验收错误或既有契约需纠错时仍必须走 blocking CR",
      "source": "OpenSpec 的 change folder + delta specs + archive merge 模式；github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md"
    },
    {
      "id": "BC-09",
      "kind": "constraint",
      "statement": "MVP observation report 是 v0.1 的必填提示层工件，不宣称机器强制；construction 在每次 attempt 后追加事实，reviewer 在 converge-audit 中逐项复核，owner 在真实场景验收时签署。缺字段、字段无法追溯到原始输出或报告未签署，均视为 BA-01 不可判定并默认触发二期评估，不能按成功处理",
      "source": "Resilience4j 通过独立实例和事件流提供 attempt、耗时与状态可观察性；Tenacity RetryCallState 提供 attempt_number、seconds_since_start、outcome 和 start_time"
    },
    {
      "id": "BC-10",
      "kind": "constraint",
      "statement": "协议迁移采用项目级标记：新项目的首份 build-log/observation report 写 workflow_protocol: v0.1；已有 contract/PLAN 的项目保持 legacy，不在中途混用 SI/test-author 新语义。文档:代码比例按本次 diff 的人工维护流程文档非空行数 / 产品代码与测试非空行数计算，排除 node_modules、vendor、生成文件、缓存和二进制；分母为 0 且新增流程文档时直接警告",
      "source": "Spec Kit 明确区分 managed tooling 更新与 feature artifacts 演进，OpenSpec 用独立 change/archive 保存增量边界；用于避免魔塔等在建项目协议混跑"
    },
    {
      "id": "BF-14",
      "kind": "fact",
      "statement": "同类工具调研（GitHub Spec Kit、AWS Kiro、BMAD-METHOD、Task Master、OpenSpec、Backlog.md）：可迁移机制包括 Spec Kit 的测试先行红绿门（测试经批准并确认失败后才许写实现，文件顺序 contracts→tests→source）与 converge 现状收敛审计（以规格为唯一意图源逐条分级 missing/partial/contradicts）；BMAD 的多镜头独立评审+triage 必须读码验证声称、'risky/foundational 故事先做'、'第三轮仍有重大发现=上游有病'熔断启发式；Task Master 的 1-10 复杂度评分高风险先做；Kiro 的 EARS 可测句式与阻塞式 hooks；OpenSpec 的 Delta 规格+归档机器合并+Lite 默认",
      "source": "各工具官方文档/仓库（github/spec-kit、kiro.dev、bmad-method.org、claude-task-master、Fission-AI/OpenSpec）",
      "evidence_status": "verified"
    },
    {
      "id": "BF-15",
      "kind": "fact",
      "statement": "软件工程标准调研映射六类流失点：验证门→BDD Given-When-Then（强制具体数据+可量化断言）与'空产物即失败'（phmdoctest --fail-nocode 思想）；自证→变异测试门禁（Stryker/mutmut：存活变异体=测试盲区）、属性测试（Hypothesis）、四眼原则（Google 评审：作者之外的人检查）、测试从规格而非实现生成；风险后置→Lean Startup 最险假设先行、曳光弹/端到端最薄线（PragProg Tip 20/68）、XP spike；无熔断→max-attempts+指数退避+失败签名去重（AWS）、错误预算政策（SRE：预算耗尽冻结+强制复盘）、熔断器（Fowler）；仪式膨胀→ADR 轻文档（Nygard：大文档永远不会被更新）、'可工作的软件高于详尽的文档'；交付漂移→doctest/phmdoctest 可执行文档进 CI、行为变更与文档更新同一提交",
      "source": "cucumber.io、martinfowler.com、testing.googleblog.com、stryker-mutator.io、hypothesis.readthedocs.io、theleanstartup.com、pragprog.com/tips、aws architecture blog、sre.google、adr.github.io、agilemanifesto.org、docs.python.org/doctest、writethedocs.org",
      "evidence_status": "verified"
    },
    {
      "id": "BF-16",
      "kind": "fact",
      "statement": "调研综合排序（影响/成本比）：首期性价比最高的三件引擎级机制是 (1) 重试熔断：max_attempts+失败签名去重，同签名连续失败强制升级；(2) 空产物即失败+断言密度门禁：V 必须断言真实内容（行数/不变量/schema），禁止'无产出也 exit 0'；(3) Phase 0 风险探针：最险假设在任何施工前做最小真实触碰，失败即止损。提示词级：Given-When-Then 验收模板、测试/实现作者分离、ADR 化瘦身、可执行文档门",
      "source": "两份调研报告的 Top-10 交叉排序",
      "evidence_status": "verified"
    },
    {
      "id": "BF-17",
      "kind": "fact",
      "statement": "GitHub Spec Kit 的 tasks-template 按 user story 组织任务，要求每个 story 可独立实现和测试；MVP First 明确只完成 User Story 1 后 STOP and VALIDATE，再逐 story 增量交付；有测试时要求 tests first 且先确认失败",
      "source": "https://github.com/github/spec-kit/blob/main/templates/tasks-template.md",
      "evidence_status": "verified"
    },
    {
      "id": "BF-18",
      "kind": "fact",
      "statement": "OpenSpec 将当前 specs 与 proposed changes 分离，每个 change 使用 ADDED/MODIFIED/REMOVED delta specs，验证后 archive 合并进 source of truth；其默认理念是 iterative not waterfall 和 progressive rigor，提供了不滥用异常恢复状态的正常增量轮子",
      "source": "https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md",
      "evidence_status": "verified"
    },
    {
      "id": "BF-19",
      "kind": "fact",
      "statement": "BMAD Test Engineering Architect 是独立测试角色；其每 story 流程为 create-story → ATDD → dev implements → automate，ATDD 在实现前生成红测，test-review 再独立检查测试质量；同时明确区分 generation/write/review/gate 控制点",
      "source": "https://github.com/bmad-code-org/bmad-method-test-architecture-enterprise",
      "evidence_status": "verified"
    },
    {
      "id": "BF-20",
      "kind": "fact",
      "statement": "成熟重试轮子不会采用无界机械重放：Tenacity 提供 stop_after_attempt、stop_after_delay、指数退避和 RetryCallState 统计；Resilience4j RetryConfig 默认 maxAttempts=3，并将 Retry、CircuitBreaker、事件和指标分层",
      "source": "https://github.com/jd/tenacity ; https://github.com/resilience4j/resilience4j/blob/master/resilience4j-retry/src/main/java/io/github/resilience4j/retry/RetryConfig.java",
      "evidence_status": "verified"
    },
    {
      "id": "BS-01",
      "kind": "success",
      "statement": "下一次真实项目运行结束时，owner 拿到的交付物在真实场景可用（核心链路以真实数据跑通并通过 owner 人工验收），而不是'某些地方完美但用户无法使用'",
      "source": "owner 原始成功标准"
    },
    {
      "id": "BS-02",
      "kind": "success",
      "statement": "机器门全绿与'核心功能真实可用'一致：不再出现 xhs 式'8/9 步全绿×3 重放但核心链路一次未成功'",
      "source": "owner+agent（对 BF-05/06 的验收化）"
    },
    {
      "id": "BS-03",
      "kind": "success",
      "statement": "最险假设在施工最早期被真实触碰（探针/曳光弹步骤），且同一失败签名第 3 次连续失败后立即升级 owner、不得进行第 4 次普通重试",
      "source": "agent（对 BF-07/08/11 的验收化）"
    },
    {
      "id": "BN-01",
      "kind": "non-goal",
      "statement": "不修改 grill skill 的拷问流程本身（BF-12 证明四项目表现良好）；允许为下游集成（如把成功信号/约束传给契约）做最小接口级微调",
      "source": "owner 多次陈述 grill 满意并允许接口级微调"
    },
    {
      "id": "BN-02",
      "kind": "non-goal",
      "statement": "v0.1 不做：变异测试门禁、属性测试强制、可执行文档 CI、引擎硬规则（列为二期候选）；不在魔塔在施工项目上生效（BD-02）",
      "source": "BD-02/BD-03 的分期决定"
    }
  ],
  "frontier": [],
  "owner_confirmation": {
    "confirmed": false,
    "summary": "草稿：原问题均已决出并移除伪 deferred BQ；结合 GitHub Spec Kit、OpenSpec、BMAD TEA、Tenacity/Resilience4j 补入 SI 与 CR 分离、独立 test-author、精确熔断、观测报告和迁移口径。BD-06/07 为本轮新增决策，待 owner 整体确认后置 final"
  }
}
```
