# GM PKI Service

基于国密算法的 PKI 体系数字证书认证系统。系统以 CA 根证书为信任锚，为用户签发 SM2/SM3 证书，并通过 CRL 维护证书撤销状态。

## 功能概览

| 模块 | 功能 |
| --- | --- |
| 根 CA 管理 | CA 初始化、根证书签发、根证书查询与下载 |
| 证书申请审核 | 用户提交证书申请，管理员审核通过后自动签发 |
| 用户证书管理 | 签名证书、加密证书、双证书签发，证书详情、下载和状态查询 |
| 证书链验证 | 展示根 CA 到用户证书的链路，并验证签发关系、CA 约束和有效期 |
| CRL 管理 | 证书撤销登记、CRL 生成、当前 CRL 查询与下载 |
| 系统设置 | CA 信息、默认有效期、数据库表信息、密钥库信息查看 |

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Vue Router |
| 后端 | Python FastAPI |
| ORM | SQLAlchemy 2.0 async |
| 开发数据库 | SQLite，默认文件为 `backend/data.db` |
| 生产数据库 | MySQL，可通过 `DATABASE_URL` 配置 |
| 密码算法 | SM2 / SM3，依赖 `gmssl` 和 `cryptography` |

## 环境要求

- Python 3.10+
- Node.js 22.18+
- npm 10+

默认登录账号：

```text
admin / admin123
```

首次启动时，后端会自动迁移数据库并创建默认管理员。

## Windows 一键启动

在项目根目录双击：

```text
start-windows.bat
```

或在 PowerShell 中运行：

```powershell
cd C:\Users\86184\Desktop\codex\gm-pki-certificate-system
.\start-windows.ps1
```

脚本会自动完成：

- 检查 Python、Node.js、npm
- 创建后端虚拟环境 `backend/.venv`
- 安装后端依赖
- 安装前端依赖
- 启动后端和前端

启动后访问：

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/api/docs
- 健康检查：http://localhost:8000/api/health

停止服务：

```powershell
.\stop-windows.ps1
```

也可以双击：

```text
stop-windows.bat
```

如果端口被占用，可以指定其它端口：

```powershell
.\start-windows.ps1 -BackendPort 8001 -FrontendPort 5174
```

如果依赖已经安装好，只想快速启动：

```powershell
.\start-windows.ps1 -SkipInstall
```

日志位置：

```text
.logs/
```

## Linux / macOS 一键启动

在项目根目录运行：

```bash
chmod +x run.sh
./run.sh
```

启动后访问：

- 前端：http://localhost:5173
- API 文档：http://localhost:8000/api/docs
- 健康检查：http://localhost:8000/api/health

停止服务：在运行脚本的终端按 `Ctrl+C`。

## 手动启动

### 后端

Windows PowerShell：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Linux / macOS：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

Windows / Linux / macOS：

```bash
cd frontend
npm install
npm run dev
```

Windows PowerShell 如果遇到 `npm.ps1` 执行策略问题，请使用：

```powershell
npm.cmd install
npm.cmd run dev
```

## 项目结构

```text
gm-pki-certificate-system/
├── run.sh                  # Linux/macOS 一键启动脚本
├── start-windows.bat       # Windows 双击启动
├── start-windows.ps1       # Windows PowerShell 启动脚本
├── stop-windows.bat        # Windows 双击停止
├── stop-windows.ps1        # Windows PowerShell 停止脚本
├── backend/
│   ├── requirements.txt
│   ├── data.db             # SQLite 开发数据库
│   ├── keystore/           # 证书和密钥存储目录
│   ├── alembic/            # 数据库迁移
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models/
│       ├── schemas/
│       ├── routers/
│       └── services/
└── frontend/
    ├── package.json
    └── src/
        ├── api/
        ├── router/
        ├── stores/
        └── views/
```

## 主要 API

### 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/auth/login` | 管理员登录 |
| `POST` | `/api/auth/logout` | 管理员退出 |

### CA 根证书

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/ca/initialize` | 初始化 CA 并签发根证书 |
| `GET` | `/api/ca/root-cert` | 查询根证书列表 |
| `GET` | `/api/ca/root-cert/{serial}` | 查询根证书详情 |
| `GET` | `/api/ca/root-cert/{serial}/download` | 下载根证书 PEM |
| `GET` | `/api/ca/status` | 查询 CA 初始化状态 |

### 用户证书

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/cert/issue` | 直接签发用户证书 |
| `GET` | `/api/cert/list` | 查询证书列表 |
| `GET` | `/api/cert/{serial}` | 查询证书详情 |
| `GET` | `/api/cert/{serial}/download` | 下载用户证书和证书链 |
| `GET` | `/api/cert/{serial}/chain` | 查询结构化证书链 |
| `POST` | `/api/cert/verify` | 验证证书链 |

### 证书申请审核

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/cert/apply` | 提交证书申请 |
| `GET` | `/api/cert/applications` | 查询申请列表 |
| `POST` | `/api/cert/applications/{id}/approve` | 审核通过并签发证书 |
| `POST` | `/api/cert/applications/{id}/reject` | 拒绝申请 |

### CRL

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/crl/revoke` | 撤销证书 |
| `POST` | `/api/crl/generate` | 生成 CRL |
| `GET` | `/api/crl/current` | 查询当前 CRL |
| `GET` | `/api/crl/download` | 下载 CRL |

## 环境变量

可在 `backend/.env` 或系统环境变量中配置：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data.db` | 数据库连接 |
| `DEBUG` | `false` | 调试模式 |
| `KEYSTORE_DIR` | `backend/keystore/` | 密钥库存储目录 |
| `CA_DEFAULT_VALIDITY_DAYS` | `3650` | CA 根证书默认有效期 |
| `CERT_DEFAULT_VALIDITY_DAYS` | `365` | 用户证书默认有效期 |
| `CRL_VALIDITY_HOURS` | `24` | CRL 有效期 |
| `DEFAULT_ADMIN_USERNAME` | `admin` | 首次启动自动创建的管理员用户名 |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | 首次启动自动创建的管理员密码 |
| `DEFAULT_ADMIN_ROLE` | `admin` | 首次启动自动创建的管理员角色 |

MySQL 示例：

```bash
DATABASE_URL=mysql+aiomysql://user:password@host:3306/gm_pki
DEBUG=false
```

## 常见问题

### Windows 下提示 npm.ps1 无法加载

这是 PowerShell 执行策略导致的。使用 `start-windows.bat` 或脚本里的 `npm.cmd` 即可避开。

### Windows 下没有 bash

`run.sh` 用于 Linux/macOS。如果在 Windows 原生环境运行，请使用 `start-windows.bat`。如果想运行 `run.sh`，需要先安装 WSL。

### 启动后端时报数据库表缺失

启动时会自动执行 Alembic 迁移，并用 SQLAlchemy 创建缺失表。正常情况下重新启动即可修复。

## 参考规范

- GM/T 0003 SM2 椭圆曲线公钥密码算法
- GM/T 0004 SM3 密码杂凑算法
- GM/T 0015 基于 SM2 密码算法的数字证书格式规范
- X.509 数字证书标准
- RFC 5280 CRL Profile
