# 数据库升级指南 (SQLite -> PostgreSQL)

由于您的数据量预计会增长到数百 GB，建议从 SQLite 迁移到 PostgreSQL (TimescaleDB)。

由于检测到您的系统未安装 Docker，无法自动为您搭建数据库。请按照以下步骤手动完成升级。

## 1. 安装 PostgreSQL

### macOS (使用 Homebrew)
```bash
brew install postgresql@14
brew services start postgresql@14
```

### 或者安装 Docker Desktop (推荐)
去 [Docker 官网](https://www.docker.com/products/docker-desktop/) 下载并安装 Docker Desktop for Mac。
安装完成后，运行：
```bash
docker run -d --name crypto-db -e POSTGRES_PASSWORD=password -p 5432:5432 timescale/timescaledb:latest-pg14
```

## 2. 安装 Python 驱动
```bash
pip install psycopg2-binary
```

## 3. 迁移数据
我为您准备了一个迁移脚本，可以将现有的 SQLite 数据一键导入 PostgreSQL。

确保 PostgreSQL 已经启动，然后运行：
```bash
# 替换下面的 URL 为您的实际数据库地址
export PG_DATABASE_URL="postgresql://postgres:password@localhost:5432/postgres"

python scripts/migrate_to_postgres.py $PG_DATABASE_URL
```

## 4. 切换配置
迁移成功后，在项目根目录创建或修改 `.env` 文件，添加：
```bash
DATABASE_URL=postgresql://postgres:password@localhost:5432/postgres
```

重启后端服务后，系统将自动连接到新的 PostgreSQL 数据库。
