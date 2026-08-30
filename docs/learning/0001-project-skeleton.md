# 0001 项目骨架

## 这一步做了什么

第一步没有直接写注册、职位、经历这些业务功能，而是先搭了一个很小但可验证的后端骨架：

- `src/careerops/main.py`：创建 FastAPI 应用。
- `src/careerops/api/routes.py`：提供 `GET /healthz` 和 `GET /readyz`。
- `src/careerops/core/`：放配置、日志、错误响应、request id 这类全局基础能力。
- `src/careerops/db/`：放数据库连接与依赖检查。
- `src/careerops/schemas/`：放 API 输入输出模型。
- `src/careerops/services/`：预留业务服务层。
- `src/careerops/repositories/`：预留数据库访问层。
- `tests/test_health.py`：验证健康检查接口。
- `docker-compose.yml`：启动 PostgreSQL + pgvector 和 Redis。
- `pyproject.toml`：统一管理依赖、测试、格式检查、类型检查和分层边界检查。
- `.github/workflows/ci.yml`：让 GitHub Actions 自动跑质量检查。
- `docs/decisions/ADR-002-backend-first-skeleton.md`：记录为什么先做后端骨架。

这一步的目标是：先证明项目可以启动、可以测试、可以被 CI 检查，再往上加业务。

## 为什么不先写业务功能

这个项目不是展示“页面上有多少功能”，而是展示后端工程能力。后端项目最怕一开始就把业务逻辑、数据库、AI 调用和测试混在一起。那样短期看起来快，后面会很难解释、很难测试，也很难在面试里讲清楚边界。

先搭骨架的好处是：

- 后续每个功能都有固定位置，不会越写越乱。
- 质量门槛一开始就存在：`pytest`、`mypy`、`ruff`、`lint-imports`。
- 面试时可以说清楚：“我不是把功能堆出来，而是先建立工程约束，再在约束里迭代。”

## 你需要理解的几个概念

### FastAPI app factory

`create_app()` 是一个函数，它返回 FastAPI 应用对象。我们没有直接在模块顶层写 `app = FastAPI(...)`，是因为函数形式更容易测试，也更容易在以后根据环境切换配置。

最小理解：

```python
def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app
```

以后测试里可以直接创建一个 app，不需要真的启动服务器。

### `/healthz` 和 `/readyz`

这两个接口容易混，但职责不同。

`/healthz` 只回答：“API 进程还活着吗？”  
即使数据库没启动，它也应该返回成功。否则监控系统会误以为整个进程坏了。

`/readyz` 回答：“API 现在能不能正常对外服务？”  
它会检查 PostgreSQL 是否可连接。数据库挂了，进程还活着，但服务没有准备好。

面试里可以这样讲：

> 我把 liveness 和 readiness 分开。`healthz` 只检查进程存活，`readyz` 检查关键依赖。这样部署系统可以区分“进程要不要重启”和“流量要不要打进来”。

### Pydantic schema

`src/careerops/schemas/health.py` 里的模型定义了接口返回结构。我们不用裸 `dict` 在层之间传递，因为裸 `dict` 很容易把字段写错，类型检查也帮不上忙。

比如：

```python
class HealthCheck(BaseModel):
    status: Literal["ok"]
    service: str
```

这里 `Literal["ok"]` 的意思是：`status` 只能是 `"ok"`，不能随便写成 `"healthy"` 或 `"success"`。

### `mypy --strict`

`mypy` 是 Python 的静态类型检查工具。`--strict` 会很严格，逼我们把边界写清楚。

这对本项目很重要，因为我们想证明：“虽然用 Python，但不是随便写的脚本，而是有工程纪律的后端服务。”

上一轮它已经帮我们抓到一个真实问题：`readyz` 里普通字符串不能直接当作固定枚举状态。这个问题运行时可能没事，但 API 契约会变松。我们已经改成显式分支。

### import-linter

`import-linter` 用来检查分层边界。现在配置了两个规则：

- `services` 和 `repositories` 不能 import `api`。
- `repositories` 不能 import `services`。

这保证依赖方向是单向的：API 调用服务层，服务层调用仓储层。底层不能反过来知道上层存在。

不用它会出现什么问题？  
项目变大后，数据库层可能偷偷 import API 的异常类或请求对象，最后业务逻辑和框架绑死，测试也会变难。

### Docker Compose

`docker-compose.yml` 现在只启动两个基础设施：

- PostgreSQL + pgvector：未来存用户、职位、经历、分析结果和向量。
- Redis：未来做缓存、限流和 worker 队列 broker。

PostgreSQL 是事实来源。Redis 里的数据必须都能丢掉重建。

最小理解：

```powershell
docker compose up -d postgres redis
```

这条命令会在本机启动数据库和 Redis，避免你手动安装和配置它们。

### CI

`.github/workflows/ci.yml` 是 GitHub Actions 配置。以后代码推到 GitHub，它会自动跑：

- `ruff check .`
- `mypy`
- `lint-imports`
- `pytest`

这就是“项目质量门”。不是靠记忆和自觉，而是让工具阻止低质量代码进入主分支。

### ADR

ADR 是 Architecture Decision Record，架构决策记录。

我们新增的骨架决策记录是 `docs/decisions/ADR-002-backend-first-skeleton.md`，记录为什么先做后端骨架。它的价值不是文档好看，而是以后面试官问“为什么这样设计”时，你有一条清楚的决策线。

## 当前验证结果

上一轮已经跑通：

```text
pytest: 1 passed
mypy: no issues in 15 source files
ruff: all checks passed
lint-imports: 2 contracts kept, 0 broken
```

还验证过：

```powershell
uvicorn careerops.main:create_app --factory --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

`uvicorn` 只是本地测试服务器。我已经把它关掉了，不会继续占用内存。

## 当前最容易出问题的地方

第一，开发依赖曾经装进了当前 Anaconda 环境，pip 提醒 `streamlit` 和 `rich` 版本有冲突。项目后续应该使用独立 `.venv`，不要继续污染全局 Python 环境。

第二，`/readyz` 需要 PostgreSQL 驱动和数据库都可用。它是依赖检查，不是普通存活检查。如果没有启动 Docker Compose，`/readyz` 返回 not ready 是正常现象。

第三，现在还没有 Alembic 迁移和业务表。也就是说，骨架已经站起来了，但数据库 schema 还没开始正式管理。

## 下一步应该做什么

下一步建议进入“数据库迁移基础”：

1. 加 Alembic。
2. 建立 SQLAlchemy metadata 和迁移入口。
3. 创建 `users` 表。
4. 启用 PostgreSQL 的 `citext` 扩展，支持 email 大小写不敏感唯一约束。
5. 让 `/readyz` 在 Docker Compose 数据库启动后真正返回 ready。

这一小步会引入 PostgreSQL、迁移、DDL 约束三个核心概念。它们都是这个项目后面认证、授权、三层证据防护的地基。

## Knowledge Check

1. 为什么这个项目先实现 `/healthz` 和 `/readyz`，而不是直接写注册登录？
2. `/healthz` 和 `/readyz` 分别应该在什么故障场景下返回成功或失败？
3. 为什么 API 返回结构要用 Pydantic schema，而不是直接返回裸 `dict`？
4. `mypy --strict` 在这个项目里证明的是什么？它不能证明什么？
5. import-linter 防止了哪类分层问题？如果没有它，后续服务层和仓储层可能怎么变乱？
6. 为什么 PostgreSQL 是事实来源，而 Redis 必须被设计成可以清空并重建？
7. 下一步加入 Alembic 时，为什么数据库约束比只写应用层校验更适合支撑三层证据防护？
