## 中文项目回顾

这是一个合成 MCP 证据回忆演示，不是作者的真实项目经历。

- 项目：`CareerOps MCP Demo - Synthetic`
- 当前证据状态：1 条记录为 `confirmed`，版本 2，复核时间为 `2026-10-28T04:21:34.965133Z`
- 记录 ID：`24b391b8-56af-4d8a-b516-8a488059beb9`
- 演示设计：在提交前保存原始 packet 和幂等键；响应丢失后，使用同一 packet 和同一键重放。来源：`demo/synthetic-decision.md`，原文：“replay the original packet with the same key”
- 演示理由：用 PostgreSQL 唯一性约束保护逻辑保存操作的身份。
- 演示失败模式：若响应丢失后更换幂等键，服务器可能已经提交原记录，从而产生重复记录。来源：`demo/synthetic-failure.md`，原文：“the server may already have committed the original record”
- 验证限制：只有计划中的假传输测试描述，没有实际执行结果。来源：`demo/synthetic-test-description.md`，原文：“This is not a real executed test result”
- 指标：未测量。
- 个人贡献：未确认。`confirmed` 仅表示该合成记录当前已确认，不证明作者进行了设计、实现或测试。记录的 contribution note 明确声明它不是作者的真实经历或实现所有权。

## English candidate resume bullet

> **Synthetic demonstration only — not suitable as a real resume achievement:** Modeled an idempotent checkpoint-submission design that preserves the original packet and logical-operation key across lost responses, using a PostgreSQL uniqueness constraint to illustrate duplicate prevention; implementation ownership, executed tests, and reliability metrics are not evidenced.

Evidence: record `24b391b8-56af-4d8a-b516-8a488059beb9`; `demo/synthetic-decision.md` — “replay the original packet with the same key”; `demo/synthetic-test-description.md` — “This is not a real executed test result”.

## STAR 草稿

- **Situation：** 合成场景假设一次保存已经被服务器提交，但客户端没有收到响应。[记录 `24b391b8-56af-4d8a-b516-8a488059beb9`；`demo/synthetic-failure.md`：“the server may already have committed the original record”]
- **Task：** 演示如何在不创建重复记录的情况下安全重放该逻辑保存操作。
- **Action：** 合成设计建议在首次提交前保留原始 packet 与幂等键，并在响应丢失时使用相同内容和相同键重放；PostgreSQL 唯一性用于保护逻辑操作身份。[`demo/synthetic-decision.md`：“replay the original packet with the same key”]
- **Result：** 该记录仅描述预期行为，没有实际执行测试，也没有可靠性、性能或成功率数据。[`demo/synthetic-test-description.md`：“This is not a real executed test result”]

由于没有提供 JD，这些材料未针对任何职位定制。缺失证据包括真实代码、实际测试输出、运行环境、量化结果，以及作者个人设计、实现或验证该方案的证明。