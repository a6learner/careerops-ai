# 0051 临时云部署：从本地容器到远程实验

## What Changed

新增独立云端实验 Compose 配置、Linux 操作脚本和开通/下线指南。
不修改业务接口、数据库迁移、授权和本地 MCP 限制。

## Why It Exists

在真实服务器上练习环境准备、网络边界、迁移、日志、故障恢复和资源删除。
无需长期订阅：本地准备完成再开主机，测试后删除。账户验证和付款由你完成。

## Failure Modes It Prevents

- 把开发密码、模型密钥或个人数据库上传云端。
- 把数据库和 Redis 端口发布到公网。
- 每个 API/worker 启动时同时迁移数据库。
- 只看到 readiness 200 就误以为 worker 能处理任务。
- 只停止容器/主机，误以为云服务已经停止收费。
- 把备份文件存在即当作业务恢复成功。

## How It Was Verified

实际结果写在 `../metrics/2026-10-28-cloud-lab-preparation.md`，
区分配置检查、本地容器/浏览器结果与尚未执行的 AWS 操作。
云端第一次测试后另存实际结果；本地通过不代替云端通过。

## What You Must Understand

Level 1：云端也是一台机器。容器网络、宿主机 loopback、你电脑的 loopback
是不同边界；SSH 转发连接这两个 loopback。关闭公网端口不会阻止 SSH 隧道。

Level 1：PostgreSQL volume 在重建容器后仍在，但删除 volume 或服务器会丢数据。
备份需要离开原主机，并验证能够恢复。Redis 不是备份来源。

Level 1：镜像/代码回退和数据库恢复不同。迁移不兼容时不能只换旧镜像，
更不能自动 downgrade；失败时先保留证据、核对边界。

Level 2：`.cloud-lab/environment` 是 Compose 插值输入，不能把完整
`docker compose config` 输出发到聊天。脚本 check 只打印检查结论。
本轮凭据是单人实验文件，不是生产 secret manager。

Level 2：生产前端仍保留 Secure cookie。浏览器通过受支持的 loopback
地址访问；公网 HTTPS、域名和远程 MCP 尚不属于已验证范围。

## Remote Execution Lessons

Windows OpenSSH rejected a private key readable by an additional local group.
The author tightened the permissions of that single file and confirmed login.
This is a local key-protection check, distinct from an incorrect server password
or an unavailable VM. Use the key through `ssh -i`; never paste it into a chat or
copy it into the release archive.

The author then authorized assistant execution on the project and the new lab
server. Preflight established OS/architecture/resources before installation.
Docker Engine and Compose were installed from the official Docker repository;
Engine runs containers, while Compose describes and coordinates project services.
System package installation is provisioning; image build and release are later
steps. A successful Docker installation does not establish app correctness.

PowerShell text pipes can append CRLF when sending a Bash script to `bash -s`.
The first streamed install ended with a stray carriage-return command after
successfully installing Docker. Verify actual state, then transfer a file and
execute it on Linux; do not repeat installation solely because its wrapper
returned a failure. The observed cloud steps are recorded separately in
`../metrics/2026-10-28-cloud-lab-run.md`.

The actual remote browser flow, queue-loss recovery and backup restoration later
passed. Host listener inspection verified that only SSH was public; web ports
remained loopback-only. A local SSH forward made the remote app accessible to
the existing browser tests without publishing database or web ports. Readiness
stayed green with the worker stopped: terminal task state, not HTTP readiness,
proved recovery. An off-VM checksum-verified synthetic backup now exists before
teardown. The author later reported deleting the VM; final billing and residual
cloud resources remain unverified. A stopped Lightsail instance still incurs
plan charges, so application shutdown and ending cloud billing are different steps.

## Knowledge Check

1. 云端服务绑定 127.0.0.1 后，为什么你本机还能通过 SSH 隧道访问？
2. 为什么前端能显示页面却可能在保存时返回 403？
3. readiness 成功为什么不能证明 worker 正常？你用什么行为证明？
4. down、destroy 和删除云主机分别移除哪些东西？哪一步停止主机计费？
5. 为什么不能在每次启动 API 时自动执行迁移和自动降级？
6. 数据库 dump 恢复成功后，还要检查哪些业务事实？
7. 如果任务一直 queued，你会按什么顺序排查？
