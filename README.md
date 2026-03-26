# 天翼云手机保活脚本 - Docker版

本项目将天翼云手机保活脚本容器化，使其可以在任何支持Docker的系统上运行，无需配置虚拟环境。

**更新时间：2026-03-26**

## 功能特点

- ✅ 不依赖虚拟环境，直接在Docker容器中运行
- ✅ 数据持久化，配置和状态文件自动保存
- ✅ 自动重启，确保保活服务持续运行
- ✅ 完整的管理脚本，操作简单
- ✅ 支持多平台（Ubuntu、Debian、CentOS等）
- ✅ 默认使用中国上海时区，确保推送通知时间准确
- ✅ 默认以守护进程模式运行，避免交互式菜单导致的问题

## 系统要求

- 支持Docker的操作系统
- Docker 19.03+ 已安装
- Docker Compose 1.24+ 已安装
- 至少2GB内存

## 安装步骤

### 方法一：直接使用DockerHub镜像（推荐）

```bash
# 1. 安装Docker和Docker Compose（如果未安装）
# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo apt-get install -y docker-compose

# 添加当前用户到docker组（可选，避免每次使用sudo）
sudo usermod -aG docker $USER
# 重新登录以生效

# 2. 创建docker-compose.yml文件
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  ctyun-keepalive:
    image: mlmll/ctyun-keepalive:latest
    container_name: ctyun-keepalive
    volumes:
      - ./data:/app/data
    restart: unless-stopped
EOF

# 3. 先以交互式模式启动容器进行账号登录和保活
# 这样可以看到登录过程并处理可能的验证码

docker-compose run -it ctyun-keepalive python ctyun_keepalive.py
# 按照菜单提示添加账号并执行保活
# 完成后使用菜单中的"0. 退出"选项退出

# 4. 停止并清理临时容器，然后后台启动正式容器

# 清理临时容器（由docker-compose run创建）
docker-compose down
# 后台启动正式容器（名称为ctyun-keepalive）
docker-compose up -d
```

### 方法二：从源码构建

```bash
# 1. 安装Docker和Docker Compose（如果未安装）
# 安装Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo apt-get install -y docker-compose

# 添加当前用户到docker组（可选，避免每次使用sudo）
sudo usermod -aG docker $USER
# 重新登录以生效

# 2. 克隆项目

git clone https://github.com/lovegongqi/ctyun-keepalive-docker.git
cd ctyun-keepalive-docker

# 3. 先以交互式模式构建并运行容器进行账号登录

docker-compose build
docker-compose run -it ctyun-keepalive python ctyun_keepalive.py
# 按照菜单提示添加账号并执行保活
# 完成后使用菜单中的"0. 退出"选项退出

# 4. 停止并清理临时容器，然后后台启动正式容器

# 清理临时容器（由docker-compose run创建）
docker-compose down
# 后台启动正式容器（名称为ctyun-keepalive）
docker-compose up -d
```

## 使用方法

### 管理命令

#### 使用run_docker.sh脚本（推荐）
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

#### 直接使用docker-compose命令
```bash
# 查看当前运行的容器
 docker ps

# 只停止本项目的容器
 docker-compose stop

# 清理本项目的容器
 docker-compose down

# 启动本项目的容器
 docker-compose up -d
```

### 脚本功能

1. **执行一次保活** - 对所有账号执行保活操作
2. **添加/更新账号** - 添加或更新天翼云账号
3. **查看账号列表** - 查看已添加的账号
4. **删除账号** - 删除指定账号
5. **设备筛选配置** - 配置设备白名单/黑名单
6. **查看配置** - 查看当前配置
7. **修改配置** - 修改脚本配置参数
8. **依赖管理** - 检查和安装依赖

### 交互菜单

当以交互式模式运行容器时，会显示以下菜单：

```
==================================================
  天翼云手机保活脚本 v6.4
==================================================
  [1] 执行一次保活
  [2] 添加/更新账号
  [3] 查看账号列表
  [4] 删除账号
  [5] 设备筛选配置
  [6] 查看配置
  [7] 修改配置
  [8] 依赖管理
  [0] 退出
==================================================
```

**使用方法**：
1. 首次运行时，选择 "2. 添加/更新账号" 添加您的天翼云账号
2. 选择 "1. 执行一次保活" 测试保活功能
3. 退出容器后，容器会自动以守护进程模式后台运行

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
docker pull mlmll/ctyun-keepalive:latest
```

## 更新Docker镜像

当项目有更新时，您可以通过以下步骤更新Docker镜像：

```bash
# 停止并删除当前容器
docker-compose down

# 拉取最新镜像
docker-compose pull

# 重新启动容器
docker-compose up -d

# 查看容器状态
docker ps | grep ctyun-keepalive
```

## 企业微信推送设置

### 步骤 1：创建企业微信群机器人
1. **打开企业微信**，进入一个群聊（可以是专门创建的通知群）
2. **点击群聊右上角的三个点**（群设置）
3. **滚动到底部**，找到并点击 **"群机器人"**
4. **点击 "添加"** 按钮，创建一个新的群机器人
5. **填写机器人名称**（例如：天翼云保活通知）
6. **点击 "添加"**，然后会显示 **webhook URL**
7. **复制这个 URL**，格式应该是：`https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

### 步骤 2：配置脚本
1. **以交互式模式运行容器**：
   ```bash
   docker-compose run -it ctyun-keepalive python ctyun_keepalive.py
   ```

2. **选择 "7. 修改配置"** 选项
3. **选择 "企业微信推送地址"**（通常是第 3 项）
4. **粘贴您刚才复制的 webhook URL**
5. **确保 "推送通知开关"** 处于开启状态（值为 True）

### 步骤 3：测试推送
1. **选择 "1. 执行一次保活"** 选项
2. **完成保活操作后**，您应该会在企业微信中收到推送通知

### 推送频率说明
- **推送触发频率**：默认每10分钟执行一次保活操作，只有在有实际操作结果时才会推送
- **推送触发条件**：当有设备开机、保活成功或出现错误时才会推送通知
- **推送内容**：包含执行结果汇总、设备操作记录和执行时间（使用中国上海时区）
- **推送配置**：可通过修改配置中的 `daemon_interval` 参数调整执行间隔，默认为600秒（10分钟）

## 联系方式

如有问题，请参考本文档或联系脚本作者。

---

**版本**: v6.4
**更新日期**: 2026-03-26
**项目地址**: https://github.com/lovegongqi/ctyun-keepalive-docker
触发构建
更新时间: Thu Mar 26 13:28:05 CST 2026
