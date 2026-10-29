# 临时云部署实验：开通、部署、测试、删除

## 目标与当前状态

用一台临时 Linux 主机学习远程部署，测试完成后删除。只有你自己访问，
只放合成数据，parser、embedding、matcher 全部使用 fake。没有模型费用。
这份指南不代表已经完成云端验收，也不代表 P1-13 或正式公网部署已经完成。

第一轮不买域名、不配置公网 HTTPS、不使用托管数据库或负载均衡器。
网页通过 SSH 隧道访问：链路由 SSH 加密，浏览器访问本机 loopback 地址。
Next.js 仍按 production 模式设置 Secure cookie；必须用下面的 loopback URL，
不能换成服务器公网 HTTP 地址或改成不安全 cookie。

```text
Windows 浏览器 http://127.0.0.1:13010
  -> Windows SSH 本地转发（加密链路）
  -> 云服务器 127.0.0.1:13010 -> Next.js -> API -> PostgreSQL/Redis
                                                      -> worker
```

MCP/CLI 本轮保留本地连接约束，不开放远程 MCP。不导入本机个人数据库。
业务表、迁移、认证、授权和 provider adapter 均不改变。

## 开通前准备

本地先完成配置与浏览器验收，再开始云端计费。准备 Windows OpenSSH、一个
AWS 账号和付款方式。付款信息、验证码、私钥和登录密码不要粘贴到聊天。
本地实验输出放 `.cloud-lab/`，它被 Git 忽略；不要把备份加入 Git。

参考路线为 AWS Lightsail：Linux、OS Only、Ubuntu 24.04 LTS、x86_64、
2 vCPU / 4 GB RAM。它只是低并发实验起点，不是经过测量的容量结论。
镜像构建在服务器串行执行；若内存不足，先保存错误，再考虑更大主机，
不要用跳过构建检查的方式继续。

截至 2026-10-28，官方 Medium-4GB Linux 公网 IPv4 套餐列为 $24/月，
按小时计费并有月度上限。按 730 小时粗算，6 小时主机费约 $0.20；
实际以所选区域、架构和创建页面的小时单价为准，税费、流量超额和附加资源另计。
预留 $2–5 是人工预算，不是自动停止或硬性扣费上限。不依赖免费试用资格。
Lightsail 停机继续计费，删除才终止该实例计费。

官方参考（创建前复核）：

- [套餐与规格](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html)
- [按小时计费](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html)
- [创建 Linux 主机](https://docs.aws.amazon.com/lightsail/latest/userguide/getting-started-with-amazon-lightsail.html)
- [SSH 密钥](https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-ssh-in-amazon-lightsail.html)
- [删除与剩余资源](https://repost.aws/knowledge-center/shut-down-lightsail)

## 1. 你在控制台开通

### 先注册账号，暂不创建主机

2026-10-28 核对官方文档：AWS 同时提供新的项目式注册和 advanced 注册。
新流程可使用已有 Google/GitHub/Apple/Amazon 登录；符合资格时可以使用 Free plan，
Lightsail 列于新流程 Free Tier 支持服务。免费账号有期限/额度和功能限制，
不是“所有套餐永久免费”。如果界面提供 Free plan，优先选择它，不主动升级 Paid。
实际主机规格和抵扣适用性在创建页面再次核对。

1. 打开 [AWS 创建账号官方入口](https://aws.amazon.com/resources/create-account/)。
2. 按页面选择邮箱或已有身份登录，完成邮箱和联系信息验证。
3. 如果提供 Free/Paid 选择，本实验先选 Free；若提示不符合资格、必须付费或
   功能受限，先记录非敏感提示，再决定是否走小额按需付费路线。
4. 若要求付款验证，只在 AWS 官方页面填写；注册流程可能包含临时验证预授权。
   不购买付费支持或年度承诺。若出现支持计划，选择免费 Basic。
5. 开启该登录方式支持的 MFA；传统 root 账号启用 root MFA，不创建 root access key。
6. 能进入控制台后搜索 Lightsail，先停在实例列表，尚不点击创建收费资源。

参考：[新注册流程](https://docs.aws.amazon.com/accounts/latest/reference/sign-in-new.html)、
[服务支持清单](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html)、
[Free/Paid 区别](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)。
符合资格与否以账号实际页面为准，不为拿免费额度重复注册账号。

### 然后创建临时主机

1. 登录 AWS。账号注册与创建主机是两个步骤，不需要购买年度订阅。
2. 进入 Lightsail，选择一个靠近自己的区域，记录区域名称。
3. 创建上述 Ubuntu 主机。查看小时价格，不购买额外磁盘、负载均衡、
   托管数据库或额外快照服务。主机名称建议 `careerops-cloud-lab`。
4. 选择自己的 SSH key 或该区域默认 key，下载并妥善保存私钥。
5. 在 Networking 检查 IPv4 和 IPv6 防火墙：本次只需要 TCP 22，
   尽量限制为你当前公网 IP；删除默认 HTTP 80 规则，不添加 3000/8000/5432/6379。
6. 记录公网 IPv4、Ubuntu 用户名 `ubuntu` 和实例名称。云端创建到此开始收费。

先与助手确认非敏感的区域、规格和预算即可；账号付款及创建按钮由你操作。
如果 SSH 无法连通，先核对本机公网 IP 是否变化以及规则，不开放所有服务端口。

## 2. 登录并安装 Docker

Windows PowerShell，替换大写占位值。首次连接前通过 AWS 控制台核对主机身份，
不要禁用 SSH host-key 检查。如果私钥权限过宽导致 OpenSSH 拒绝读取，
只调整这一个私钥文件的访问权限，不递归修改整个用户目录。

```powershell
ssh -i "C:\PATH\LightsailKey.pem" ubuntu@PUBLIC_IP
```

云端 Ubuntu：先安装 Docker 官方仓库和 Compose plugin。
下面来自 [Docker Ubuntu 安装指南](https://docs.docker.com/engine/install/ubuntu/)。
仅对这台新建实验主机执行；不是修改你的 Windows 环境。

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker version
sudo docker compose version
free -h
df -h /
```

仓库也提供 `scripts/cloud_lab_bootstrap.sh`，保存相同的 Ubuntu 24.04 x86_64
安装步骤。通过 scp 传输脚本文件后在服务器运行，不用 PowerShell 文本管道
直接喂给 `bash -s`，避免额外 CRLF 字符。仍先核对目标是本次新建实验主机。

本实验使用 `sudo docker`，无需把用户加入具有管理员能力的 docker group。

## 3. 从本机传输本次代码

当前准备工作不自动 commit/push。不要在服务器 clone 后误以为拿到了尚未提交的配置。
在仓库根目录的 PowerShell 打包下列明确路径，不包含 `.env`、私钥、Git 历史、
本机虚拟环境或数据库。tar 包仅用于你自己的临时主机。

```powershell
New-Item -ItemType Directory -Force .cloud-lab | Out-Null
git rev-parse HEAD | Set-Content .cloud-lab/source-head.txt
git status --short | Set-Content .cloud-lab/source-status.txt
tar --exclude=node_modules --exclude=.next --exclude=__pycache__ --exclude=.env --exclude='.env.*' --exclude=playwright-report --exclude=test-results --exclude=coverage -czf .cloud-lab/release.tar.gz Dockerfile .dockerignore pyproject.toml README.md alembic.ini constraints src migrations frontend docker-compose.cloud-lab.yml scripts/cloud_lab.sh
if ($LASTEXITCODE -ne 0) { throw 'Archive creation failed' }
Get-FileHash .cloud-lab/release.tar.gz -Algorithm SHA256
scp -i "C:\PATH\LightsailKey.pem" .cloud-lab/release.tar.gz ubuntu@PUBLIC_IP:~/release.tar.gz
```

保存 SHA256，云端用 `sha256sum ~/release.tar.gz` 比对。这标识本次实际传输内容；
HEAD 只标识原始提交，不包括尚未提交的准备工作。上传前用 `tar -tzf` 检查文件列表。

Ubuntu：

```bash
mkdir -p ~/careerops-cloud-lab
sha256sum ~/release.tar.gz
tar -xzf ~/release.tar.gz -C ~/careerops-cloud-lab
cd ~/careerops-cloud-lab
sudo bash scripts/cloud_lab.sh init
sudo bash scripts/cloud_lab.sh check
sudo bash scripts/cloud_lab.sh build
sudo bash scripts/cloud_lab.sh up
```

`init` 创建独立随机数据库密码和 JWT secret（文件只允许当前所有者读取），
不会打印它们。`build` 不启动服务；`up` 先启动数据库/Redis，执行一次迁移，
成功后才启动 API、worker 和前端。失败时停止发布并保留诊断状态。
重复 `init` 会拒绝覆盖已有凭据。构建只在显式 `build` 时发生；测试期间不要改代码重打同一标签。

## 4. 建立隧道与浏览器验收

另开 Windows PowerShell，保持窗口开启：

```powershell
ssh -i "C:\PATH\LightsailKey.pem" -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:13010:127.0.0.1:13010 ubuntu@PUBLIC_IP
```

打开 **http://127.0.0.1:13010**。如果本机该端口被占用，先停止这次实验并定位占用；
不要只改一端端口，因为前端写操作会检查准确的 Origin。

1. 用一次性账号注册登录，只填写虚构数据。
2. 添加一条 Experience 与 Job，执行 Parse、Analysis，查看证据和 gap。
3. 创建 Action Item，更新 application status，查看 Dashboard。
4. 打开 Projects，创建记录，检查来源与贡献，再确认/撤回。
5. 可选：用合成 TXT/PDF 导入草稿，检查确认前不会创建正式经历。
6. 退出再登录。30 分钟会话过期后需要重新登录，这是现有已知限制。

本机已有 Playwright 时，可在本机运行自动化，浏览器通过隧道操作远程服务：

```powershell
$env:CAREEROPS_E2E_BASE_URL = 'http://127.0.0.1:13010'
npm --prefix frontend run test:e2e
Remove-Item Env:CAREEROPS_E2E_BASE_URL
```

不要为了 HTTP 公网访问而放松 Secure cookie、Origin 或授权检查。

## 5. 排错与恢复实验

Ubuntu，在本次实验目录运行：

```bash
sudo bash scripts/cloud_lab.sh status
sudo bash scripts/cloud_lab.sh logs
sudo bash scripts/cloud_lab.sh recover
sudo bash scripts/cloud_lab.sh backup
sudo bash scripts/cloud_lab.sh restore-check /ABSOLUTE/PATH/TO/backup-TIMESTAMP.dump
```

`recover` 是有界单次恢复，不是永久调度器。先完成一次成功主流程，再在指导下
停止本实验 worker、创建 queued 任务、恢复 worker，观察最终状态。模拟 Redis 丢失
要严格选中 `careerops-cloud-lab`，不能使用全局 `docker prune` 或其他项目。
本轮没有无人值守的周期恢复保证。

`restore-check` 只创建独立 scratch 数据库，拒绝覆盖同名库；还原成功后检查
Alembic 版本，退出时清理。它证明备份可读取和还原，不单独证明业务数据完整。
完整恢复验收还要对比选定合成记录、证据来源和归属；不要把一次命令成功写成 RTO/RPO 指标。

常见问题：

| 现象 | 先检查 |
|---|---|
| SSH 超时 | 实例状态、公网 IP、当前本机 IP、防火墙 22 |
| 隧道提示端口占用 | Windows 13010 是否被已有本地实例使用 |
| 网页可以打开但写入 403 | 是否使用准确的 `http://127.0.0.1:13010` |
| 页面反复要求登录 | loopback URL、cookie、账号密码和会话过期；不放松认证 |
| Analysis 一直 queued | worker 是否运行、其日志、数据库状态，再运行有界恢复 |
| readiness 503 | 依次查 PostgreSQL、Redis、API，不把健康检查改成恒为成功 |
| 构建进程被杀 | `free -h`、磁盘、主机 OOM 记录；保存失败日志 |
| 转换格式失败 | worker 镜像是否包含 LibreOffice，文件是否属于支持格式 |

## 6. 保存结果，然后删除

本机保存：代码包 SHA、实例规格/区域、实际操作起止时间、页面截图、测试结果、
具体失败及解决方式。云端 `.cloud-lab/images.json` 记录镜像 ID；本地构建镜像可能没有 registry digest。
不要把密码、token、私钥或原始私密日志放入提交。下载 root 所有的备份时，
先只为选定合成文件创建一个可由 ubuntu 读取的副本，不修改整个凭据目录权限。

容器收尾：

```bash
sudo bash scripts/cloud_lab.sh down
# down 保留实验数据库，适合检查后重新启动。
# 完成记录且确认只含合成数据后，才执行删除：
sudo bash scripts/cloud_lab.sh destroy DELETE-SYNTHETIC-LAB-DATA
```

Docker down 不会停止云端计费。最后你在 Lightsail 控制台：

1. 删除本次命名的实例，不是 Stop。
2. 检查本次区域的 Disks、Snapshots、Networking、Databases、Containers 和 Load balancers；
   若误建附加资源，只删除本实验所属的项目。
3. 检查其他使用过的区域，确认没有本实验遗留。
4. 查看 Billing，记录成本；账单有延迟，稍后再核对一次。关掉 SSH 窗口。

完成标准：远程浏览器工作流通过、有一次恢复验证、有可追溯记录、
确认本次收费资源已删除。仅创建实例或 readiness 返回 200 不算完成部署实验。
