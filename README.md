# GM PKI Service

**基于国密算法的PKI体系数字证书认证系统** — A lightweight PKI Certificate Authority system based on SM2/SM3 national cryptographic algorithms.

## 项目简介

本项目是一个轻量级PKI体系数字证书认证系统，以CA根证书为信任锚，为用户生成SM2签名证书和加密证书，并通过CRL发布机制维护证书状态。系统支持证书从签发、查询、导出到撤销的完整生命周期管理。

### 核心模块

| 模块                   | 功能                                                                     |
| ---------------------- | ------------------------------------------------------------------------ |
| **根证书签发**   | CA初始化、SM2密钥对生成、自签名根证书签发、根证书查询与下载              |
| **用户证书签发** | 用户DN生成、SM2密钥生成/公钥导入、签名证书与加密证书签发、证书详情与下载 |
| **CRL签发**      | 证书撤销登记、撤销原因记录、CRL生成与签名、CRL下载、证书状态查询         |

### 技术栈

| 层级       | 技术                                           |
| ---------- | ---------------------------------------------- |
| 前端       | Vue 3 + TypeScript + Vite + Pinia + Vue Router |
| 后端       | Python FastAPI (全异步)                        |
| ORM        | SQLAlchemy 2.0 (async)                         |
| 开发数据库 | SQLite (文件:`backend/data.db`)              |
| 生产数据库 | MySQL                                          |
| 密码算法   | SM2 / SM3 (gmssl + cryptography)               |

## 快速开始

### 环境要求

- **Python** ≥ 3.10
- **Node.js** ≥ 22.18
- **npm** ≥ 10

### 一键启动

```bash
chmod +x run.sh
./run.sh
```

启动后访问：

- **前端**: http://localhost:5173
- **后端API文档**: http://localhost:8000/api/docs
- **健康检查**: http://localhost:8000/api/health

### 手动启动

**后端**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**前端**

```bash
cd frontend
npm install
npm run dev
```

## 项目结构

```
GM_PKI_Service/
├── run.sh                    # 一键启动脚本
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── data.db               # SQLite数据库（开发环境）
│   ├── keystore/             # 密钥库文件存储
│   └── app/
│       ├── main.py           # FastAPI入口
│       ├── config.py         # 配置管理
│       ├── database.py       # 异步数据库引擎
│       ├── models/           # ORM模型
│       │   ├── ca_config.py
│       │   ├── root_cert.py
│       │   ├── user_cert.py
│       │   └── crl.py
│       ├── schemas/          # Pydantic请求/响应模型
│       │   ├── ca.py
│       │   ├── cert.py
│       │   └── crl.py
│       ├── routers/          # API路由
│       │   ├── ca.py
│       │   ├── user_cert.py
│       │   └── crl.py
│       └── services/         # 业务逻辑
│           └── crypto.py     # SM2/SM3密钥与证书操作
└── frontend/
    └── src/
        ├── views/            # 页面
        │   ├── Dashboard.vue
        │   ├── RootCA.vue
        │   ├── UserCert.vue
        │   └── CRL.vue
        ├── stores/           # Pinia状态管理
        │   ├── ca.ts
        │   ├── cert.ts
        │   └── crl.ts
        └── api/              # API客户端
            └── index.ts
```

## API 接口

### CA 根证书管理

| 方法     | 路径                                    | 说明                 |
| -------- | --------------------------------------- | -------------------- |
| `POST` | `/api/ca/initialize`                  | 初始化CA并签发根证书 |
| `GET`  | `/api/ca/root-cert`                   | 查询根证书列表       |
| `GET`  | `/api/ca/root-cert/{serial}`          | 查询根证书详情       |
| `GET`  | `/api/ca/root-cert/{serial}/download` | 下载根证书PEM        |
| `GET`  | `/api/ca/status`                      | 查询CA初始化状态     |

### 用户证书管理

| 方法     | 路径                            | 说明             |
| -------- | ------------------------------- | ---------------- |
| `POST` | `/api/cert/issue`             | 签发用户证书     |
| `GET`  | `/api/cert/list`              | 查询证书列表     |
| `GET`  | `/api/cert/{serial}`          | 查询证书详情     |
| `GET`  | `/api/cert/{serial}/download` | 下载证书及证书链 |
| `GET`  | `/api/cert/{serial}/status`   | 查询证书状态     |

### CRL 证书撤销列表

| 方法     | 路径                  | 说明        |
| -------- | --------------------- | ----------- |
| `POST` | `/api/crl/revoke`   | 撤销证书    |
| `POST` | `/api/crl/generate` | 生成CRL     |
| `GET`  | `/api/crl/current`  | 查询当前CRL |
| `GET`  | `/api/crl/download` | 下载CRL文件 |

## 环境变量

在 `backend/app/.env` 中配置（或通过系统环境变量）：

| 变量                           | 默认值                            | 说明                       |
| ------------------------------ | --------------------------------- | -------------------------- |
| `DATABASE_URL`               | `sqlite+aiosqlite:///./data.db` | 数据库连接（开发用SQLite） |
| `DEBUG`                      | `false`                         | 调试模式                   |
| `KEYSTORE_DIR`               | `backend/keystore/`             | 密钥库存储路径             |
| `CA_DEFAULT_VALIDITY_DAYS`   | `3650`                          | CA根证书默认有效期（天）   |
| `CERT_DEFAULT_VALIDITY_DAYS` | `365`                           | 用户证书默认有效期（天）   |
| `CRL_VALIDITY_HOURS`         | `24`                            | CRL有效期（小时）          |

### 生产环境配置

```bash
# 使用 MySQL
DATABASE_URL=mysql+aiomysql://user:password@host:3306/gm_pki
DEBUG=false
```

## 开发说明

### 数据库

- **开发环境**：使用 SQLite，数据库文件 `backend/data.db` 自动创建
- **生产环境**：设置 `DATABASE_URL` 为 MySQL 连接字符串

### SM2双证书体系

系统遵循国密规范，为每个用户签发两张证书：

- **签名证书** (`cert_type=sign`)：用于身份认证和电子签名
- **加密证书** (`cert_type=encrypt`)：用于密钥协商和数据加密

### 证书撤销

1. 调用 `/api/crl/revoke` 登记撤销证书
2. 调用 `/api/crl/generate` 生成CRL（使用根证书私钥签名）
3. 通过 `/api/cert/{serial}/status` 查询证书是否已被撤销

## 参考规范

- GM/T 0003 SM2椭圆曲线公钥密码算法
- GM/T 0004 SM3密码杂凑算法
- GM/T 0015 基于SM2密码算法的数字证书格式规范
- X.509 数字证书标准
- RFC 5280 (CRL Profile)
