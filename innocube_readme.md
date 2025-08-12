# 🎯 Innocube Data Management System

一个强大的问卷调查数据自动化处理系统，支持Excel/CSV数据上传、清洗、存储和可视化分析。

## 🚀 特性

- **自动化数据处理**: 支持Excel/CSV文件自动上传、清洗和标准化
- **关系数据库设计**: 优化的数据库架构，支持多种问卷格式
- **RESTful API**: 完整的API接口，支持数据查询和分析
- **实时仪表板**: 动态数据可视化和统计报表
- **后台任务处理**: 异步文件处理和定时任务
- **云端部署**: 支持多平台部署（Heroku、AWS、DigitalOcean等）
- **数据导出**: 支持Excel格式数据导出
- **系统监控**: 健康检查和自动备份

## 📋 系统要求

- Python 3.9+
- PostgreSQL 12+ (生产环境) 或 SQLite (开发环境)
- Redis 6+
- Docker & Docker Compose (推荐)

## 🛠️ 快速开始

### 方法一：Docker 部署（推荐）

1. **克隆项目**
```bash
git clone https://github.com/your-username/innocube.git
cd innocube
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，设置数据库密码等配置
```

3. **启动服务**
```bash
chmod +x deploy.sh
./deploy.sh local
```

4. **访问应用**
- 应用地址: http://localhost
- 直接访问Flask: http://localhost:5000

### 方法二：手动安装

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **设置数据库**
```bash
# PostgreSQL (推荐)
createdb innocube_db

# 或使用 SQLite (开发环境)
# 系统会自动创建 SQLite 文件
```

3. **配置Redis**
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

4. **初始化数据库**
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

5. **启动应用**
```bash
# 启动主应用
python app.py

# 启动后台任务处理器（新终端）
celery -A app.celery worker --loglevel=info

# 启动定时任务调度器（新终端）
celery -A app.celery beat --loglevel=info
```

## 📊 数据库设计

系统采用关系型数据库设计，主要表结构：

```
Products (产品表)
├── Sales (销售记录)
└── Surveys (问卷调查)
    ├── Questions (问题)
    │   └── Question_Options (选项)
    └── Survey_Results (问卷结果)
        ├── Respondents (受访者)
        └── Answers (答案)
```

### 核心实体关系

- **Products → Surveys**: 一对多（一个产品可以有多个问卷）
- **Surveys → Questions**: 一对多（一个问卷包含多个问题）
- **Questions → Question_Options**: 一对多（一个问题有多个选项）
- **Surveys → Survey_Results**: 一对多（一个问卷有多个回答结果）
- **Respondents → Survey_Results**: 一对多（一个受访者可回答多个问卷）

## 📤 数据上传格式

### Excel/CSV 文件要求

上传的数据文件需要包含以下必需列：

- `respondent_email`: 受访者邮箱（必需）
- `survey_title`: 问卷标题（必需）
- `age_group`: 年龄组（可选）
- `gender`: 性别（可选）
- `location`: 地理位置（可选）
- `income_level`: 收入水平（可选）

其他列将被视为问卷问题和答案。

### 示例数据格式

```csv
respondent_email,survey_title,age_group,gender,location,brand_preference,satisfaction_rating,recommendation_score
user1@example.com,产品满意度调查,25-34,男,北京,品牌A,4,8
user2@example.com,产品满意度调查,35-44,女,上海,品牌B,5,9
```

## 🔌 API 接口

### 数据上传
```http
POST /api/upload
Content-Type: multipart/form-data

# 上传Excel或CSV文件
```

### 获取问卷列表
```http
GET /api/surveys
```

### 获取问卷回答
```http
GET /api/surveys/{survey_id}/responses?page=1&per_page=50
```

### 获取人口统计分析
```http
GET /api/analytics/demographics
```

### 获取趋势分析
```http
GET /api/analytics/trends
```

### 导出数据
```http
GET /api/export/{survey_id}
```

### 系统统计
```http
GET /api/stats
```

## 🚀 部署指南

### Heroku 部署

```bash
# 安装 Heroku CLI
# 登录 Heroku
heroku login

# 部署到 Heroku
./deploy.sh heroku
```

### DigitalOcean 部署

```bash
# 安装 doctl CLI
# 配置 DigitalOcean 访问令牌
doctl auth init

# 部署到 DigitalOcean
./deploy.sh digitalocean
```

### AWS 部署

```bash
# 配置 AWS CLI
aws configure

# 部署到 AWS（需要额外配置 ECS/EKS）
./deploy.sh aws
```

### 自定义服务器部署

```bash
# 在目标服务器上
git clone https://github.com/your-username/innocube.git
cd innocube
cp .env.example .env
# 编辑 .env 文件配置

# 使用 Docker Compose
docker-compose up -d --build

# 或手动安装
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
```

## 🔧 配置说明

### 环境变量配置

主要配置项说明：

- `FLASK_ENV`: 运行环境 (development/production)
- `SECRET_KEY`: Flask 密钥，生产环境必须更改
- `DATABASE_URL`: 数据库连接字符串
- `REDIS_URL`: Redis 连接字符串
- `MAX_CONTENT_LENGTH`: 文件上传大小限制（字节）
- `CORS_ORIGINS`: 允许的跨域来源

### 数据库配置

#### PostgreSQL (生产环境推荐)
```bash
DATABASE_URL=postgresql://username:password@host:port/database_name
```

#### SQLite (开发环境)
```bash
DATABASE_URL=sqlite:///innocube.db
```

### Redis 配置
```bash
REDIS_URL=redis://localhost:6379
# 或远程 Redis
REDIS_URL=redis://username:password@host:port/db_number
```

## 📈 监控和维护

### 健康检查

系统提供自动健康检查功能：

```bash
# 手动健康检查
curl http://localhost:5000/api/stats

# 或使用部署脚本
./deploy.sh health
```

### 数据备份

```bash
# 创建手动备份
./deploy.sh backup

# 从备份恢复
./deploy.sh restore backup_file.sql
```

系统每天凌晨3点自动创建备份，保留30天。

### 日志监控

```bash
# 查看应用日志
./deploy.sh logs

# 查看特定服务日志
docker-compose logs -f web
docker-compose logs -f worker
```

### 性能优化

#### 数据库优化
- 每周自动执行数据库统计更新
- 定期清理过期数据
- 使用连接池优化数据库连接

#### 缓存策略
- Redis 缓存频繁查询的数据
- 静态文件 CDN 加速
- API 响应缓存

#### 扩展性
```bash
# 水平扩展 worker 进程
./deploy.sh scale worker 3

# 垂直扩展（增加资源）
# 编辑 docker-compose.yml 中的资源限制
```

## 🔍 故障排除

### 常见问题

#### 1. 数据库连接失败
```bash
# 检查数据库状态
docker-compose ps db

# 查看数据库日志
docker-compose logs db

# 重启数据库
docker-compose restart db
```

#### 2. Redis 连接失败
```bash
# 检查 Redis 状态
docker-compose ps redis

# 测试 Redis 连接
redis-cli ping
```

#### 3. 文件上传失败
- 检查文件大小是否超过限制
- 检查磁盘空间是否充足
- 验证文件格式是否正确

#### 4. 后台任务不执行
```bash
# 检查 Celery worker 状态
docker-compose ps worker

# 查看 worker 日志
docker-compose logs worker

# 重启 worker
docker-compose restart worker
```

### 调试模式

开发环境启用调试：

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python app.py
```

### 性能分析

```bash
# 查看系统资源使用
docker stats

# 查看数据库性能
# PostgreSQL
docker-compose exec db psql -U innocube_user -d innocube_db -c "SELECT * FROM pg_stat_activity;"

# 查看 Redis 状态
docker-compose exec redis redis-cli info
```

## 📚 API 文档

### 完整 API 端点列表

| 方法 | 端点 | 描述 | 参数 |
|------|------|------|------|
| POST | `/api/upload` | 上传数据文件 | file (multipart) |
| GET | `/api/surveys` | 获取所有问卷 | - |
| GET | `/api/surveys/{id}/responses` | 获取问卷回答 | page, per_page |
| GET | `/api/analytics/demographics` | 人口统计分析 | - |
| GET | `/api/analytics/trends` | 趋势分析 | - |
| GET | `/api/export/{id}` | 导出问卷数据 | - |
| GET | `/api/stats` | 系统统计信息 | - |

### 响应格式

#### 成功响应
```json
{
  "data": {...},
  "status": "success",
  "message": "操作成功"
}
```

#### 错误响应
```json
{
  "error": "错误描述",
  "status": "error",
  "code": 400
}
```

### 分页响应
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "pages": 10,
    "per_page": 50,
    "total": 500
  }
}
```

## 🛡️ 安全考虑

### 数据安全
- 数据库连接加密
- 敏感信息环境变量存储
- 定期安全更新

### 访问控制
- CORS 策略配置
- API 速率限制
- 文件类型验证

### 生产环境安全清单
- [ ] 更改默认密钥和密码
- [ ] 启用 HTTPS
- [ ] 配置防火墙规则
- [ ] 设置监控告警
- [ ] 定期备份验证
- [ ] 日志审计配置

## 🤝 贡献指南

### 开发环境设置

```bash
# 克隆项目
git clone https://github.com/your-username/innocube.git
cd innocube

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 设置pre-commit钩子
pre-commit install
```

### 代码规范

- 使用 Black 格式化代码
- 使用 flake8 进行代码检查
- 编写单元测试
- 更新文档

### 提交规范

```bash
# 格式：type(scope): description

git commit -m "feat(api): add new analytics endpoint"
git commit -m "fix(upload): handle large file processing"
git commit -m "docs(readme): update installation guide"
```

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🆘 支持

### 获取帮助

- 📧 邮箱: support@innocube.com
- 💬 GitHub Issues: [提交问题](https://github.com/your-username/innocube/issues)
- 📖 文档: [完整文档](https://docs.innocube.com)

### 常用命令速查

```bash
# 部署相关
./deploy.sh local          # 本地部署
./deploy.sh heroku         # Heroku 部署
./deploy.sh backup         # 创建备份
./deploy.sh health         # 健康检查
./deploy.sh logs           # 查看日志
./deploy.sh cleanup        # 清理资源

# Docker 相关
docker-compose up -d       # 启动所有服务
docker-compose down        # 停止所有服务
docker-compose restart     # 重启服务
docker-compose ps          # 查看服务状态
docker-compose logs -f web # 查看应用日志

# 数据库相关
python -c "from app import db; db.create_all()"  # 创建表
flask db upgrade           # 数据库迁移
```

## 🎯 路线图

### v1.0 (当前版本)
- [x] 基础数据上传和处理
- [x] RESTful API
- [x] 基础仪表板
- [x] Docker 部署

### v1.1 (计划中)
- [ ] 用户认证和权限管理
- [ ] 高级数据可视化
- [ ] 数据导入模板定制
- [ ] 移动端响应式界面

### v1.2 (未来版本)
- [ ] 机器学习数据分析
- [ ] 实时数据同步
- [ ] 多租户支持
- [ ] 高级报表生成

## 📊 项目统计

- **代码行数**: ~3000 行
- **支持文件格式**: Excel (.xlsx, .xls), CSV
- **数据库表**: 8 个核心表
- **API 端点**: 10+ 个
- **自动化任务**: 5 个定时任务
- **部署平台**: 4+ 个云平台支持

---

**Innocube** - 让数据管理变得简单高效 🚀