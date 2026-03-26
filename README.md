# 天翼云手机保活脚本 - Docker版

本项目将天翼云手机保活脚本容器化，使其可以在任何支持Docker的系统上运行，无需配置虚拟环境。

## 功能特点

- ✅ 不依赖虚拟环境，直接在Docker容器中运行
- ✅ 数据持久化，配置和状态文件自动保存
- ✅ 自动重启，确保保活服务持续运行
- ✅ 完整的管理脚本，操作简单
- ✅ 支持多平台（Ubuntu、Debian、CentOS等）

## 系统要求

- 支持Docker的操作系统
- Docker 19.03+ 已安装
- Docker Compose 1.24+ 已安装
- 至少2GB内存

## 安装步骤

### 1. 安装Docker和Docker Compose（如果未安装）

```bash
# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo apt-get install -y docker-compose

# 添加当前用户到docker组（可选，避免每次使用sudo）
sudo usermod -aG docker $USER
# 重新登录以生效
```

### 2. 克隆项目

```bash
git clone https://github.com/lovegongqi/ctyun-keepalive-docker.git
cd ctyun-keepalive-docker
```

### 3. 构建和运行

```bash
# 构建Docker镜像
./run_docker.sh build

# 启动容器
./run_docker.sh up

# 进入容器配置账号
./run_docker.sh exec
# 在容器内运行
python ctyun_keepalive.py
# 按照菜单提示添加账号
```

## 使用方法

### 管理命令

```bash
# 构建镜像
./run_docker.sh build

# 启动容器
./run_docker.sh up

# 停止容器
./run_docker.sh down

# 查看日志
./run_docker.sh logs

# 进入容器
./run_docker.sh exec

# 查看状态
./run_docker.sh status
```

### 脚本功能

1. **执行一次保活** - 对所有账号执行保活操作
2. **添加/更新账号** - 添加或更新天翼云账号
3. **查看账号列表** - 查看已添加的账号
4. **删除账号** - 删除指定账号
5. **设备筛选配置** - 配置设备白名单/黑名单
6. **查看配置** - 查看当前配置
7. **后台运行管理** - 管理后台守护进程
8. **依赖管理** - 检查和安装依赖

## 目录结构

```
ctyun-keepalive-docker/
├── Dockerfile           # Docker镜像构建文件
├── docker-compose.yml   # Docker Compose配置文件
├── run_docker.sh        # 运行管理脚本
├── README.md            # 项目说明文档
├── .github/workflows/   # GitHub Actions工作流
└── root/                # 脚本目录
    └── ctyun_keepalive.py  # 保活脚本主文件
```

## 数据管理

- **数据持久化**：容器会自动创建`data`目录并挂载到容器中
- **配置文件**：`data/ctyun_config.json`
- **账号文件**：`data/ctyun_accounts.json`
- **状态文件**：`data/ctyun_state_*.json`

## 注意事项

1. **首次运行**：首次运行需要进入容器添加账号信息
2. **网络连接**：确保容器能够访问互联网，特别是天翼云的相关域名
3. **资源需求**：容器运行需要一定的CPU和内存资源，建议至少2GB内存
4. **自动重启**：容器配置为`restart: unless-stopped`，系统重启后会自动启动
5. **隐私保护**：账号信息和登录状态仅存储在本地，不会上传到GitHub

## 故障排查

### 常见问题

1. **构建失败**：检查网络连接，确保可以下载依赖包
2. **启动失败**：查看日志`./run_docker.sh logs`了解具体错误
3. **无法登录**：检查账号密码是否正确，以及是否需要验证码
4. **保活失败**：检查网络连接和云手机状态

### 查看容器详细信息

```bash
docker inspect ctyun-keepalive
```

## 更新脚本

如果需要更新保活脚本，只需替换`root/ctyun_keepalive.py`文件，然后重新构建和启动：

```bash
./run_docker.sh down
# 替换脚本文件
./run_docker.sh build
./run_docker.sh up
```

## GitHub Actions自动构建

本项目配置了GitHub Actions，当推送代码到main分支时，会自动构建Docker镜像并推送到DockerHub。

### 配置DockerHub凭证

1. 登录DockerHub，创建一个访问令牌
2. 在GitHub仓库的"Settings" > "Secrets and variables" > "Actions"中添加以下secrets：
   - `DOCKERHUB_USERNAME` - 您的DockerHub用户名
   - `DOCKERHUB_TOKEN` - 您的DockerHub访问令牌

## 从DockerHub拉取镜像

其他用户可以直接从DockerHub拉取构建好的镜像：

```bash
docker pull lovegongqi/ctyun-keepalive:latest
```

## 联系方式

如有问题，请参考本文档或联系脚本作者。

---

**版本**: v6.4
**更新日期**: 2026-03-26
**项目地址**: https://github.com/lovegongqi/ctyun-keepalive-docker
触发构建
