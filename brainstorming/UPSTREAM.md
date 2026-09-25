# UPSTREAM

本 skill 适配自 [obra/superpowers](https://github.com/obra/superpowers)
（MIT License）中的 `brainstorming` 技能方法论（苏格拉底式设计精化、
分节呈现设计、逐节确认）。

- 保留的核心思想：先理解需求和既有代码，再比较真实的候选路线，解释
  trade-off；产品形态的决策必须能让用户纠正，落选方案有理由。
- 本仓库的适配：只在实质分叉加载；普通工程选择由 planner 自主决定，
  只有 owner 真实回复才写 brief BD，`/work` 推断保持 assumption。
  上游当前 main 要求所有创意改动先经人工批准（bounded/architectural/spike
  各有 gate）；本项目没有继承该普遍停机规则，也不强制为凑数生成保守+
  激进候选。当前 main 是可变引用，不声称与所记录方法同版本等价。
- 上游许可：MIT（见仓库 LICENSE）。本目录不包含上游代码副本。
