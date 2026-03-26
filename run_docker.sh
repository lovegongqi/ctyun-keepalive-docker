#!/bin/bash

echo "===================================="
echo "天翼云手机保活脚本 - Docker 运行工具"
echo "===================================="
echo

case "$1" in
    build)
        echo "正在构建Docker镜像..."
        docker-compose build
        echo "构建完成!"
        ;;
    up)
        echo "正在启动容器..."
        docker-compose up -d
        echo "容器启动成功!"
        echo "运行命令: docker-compose logs -f 查看日志"
        ;;
    down)
        echo "正在停止容器..."
        docker-compose down
        echo "容器已停止!"
        ;;
    logs)
        echo "查看容器日志..."
        docker-compose logs -f
        ;;
    exec)
        echo "进入容器终端..."
        docker-compose exec ctyun-keepalive bash
        ;;
    status)
        echo "容器状态..."
        docker-compose ps
        ;;
    *)
        echo "使?       echo "使?       echo "使?       echo "使?   ??       echo "使?       ec- 构建Docker镜像"
        echo "  up      - 启动容器"
        echo "  down    - 停止容器"
        echo "  logs    - 查看容器日志"
        echo "  exec    - 进入容器终端"
        echo "  status  - 查看容器状态"
        ;;
esac
