#!/usr/bin/env python3
"""
天翼云手机保活脚本 v6.4
"""

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext

# 版本号
__version__ = "6.4"
VERSION = f"v{__version__}"

# ============================================================================
# 配置参数
# ============================================================================

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "ctyun_config.json"
ACCOUNTS_FILE = DATA_DIR / "ctyun_accounts.json"

# 默认配置
DEFAULT_CONFIG = {
    "notify_enabled": True,
    "parallel_enabled": True,
    "qywx_webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
    "keepalive_duration": 60,
    "keepalive_duration_poweron": 90,
    "health_check_interval": 15,
    "min_data_rate": 1.0,
    "max_zero_rate_count": 3,
    "max_reconnect_attempts": 2,
    "daemon_interval": 600,
    "max_concurrent_accounts": 2,
    "account_timeout": 600,
    "retry_on_failure": 1,
    "login_timeout": 120,
    "captcha_retry": 3
}

# 配置项中文映射
CONFIG_LABELS = {
    "notify_enabled": "推送通知开关",
    "parallel_enabled": "多账号并行运行",
    "qywx_webhook": "企业微信推送地址",
    "keepalive_duration": "保活时长(秒)",
    "keepalive_duration_poweron": "开机后保活时长(秒)",
    "health_check_interval": "健康检查间隔(秒)",
    "min_data_rate": "最小数据率(KB/s)",
    "max_zero_rate_count": "最大零速率次数",
    "max_reconnect_attempts": "最大重连次数",
    "daemon_interval": "守护进程间隔(秒)",
    "max_concurrent_accounts": "最大并发账号数",
    "account_timeout": "账号超时时间(秒)",
    "retry_on_failure": "失败重试次数",
    "login_timeout": "登录超时时间(秒)",
    "captcha_retry": "验证码重试次数"
}


def load_config() -> dict:
    """加载配置，首次运行自动生成"""
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[配置] 已生成配置文件: {CONFIG_FILE.name}")
        return DEFAULT_CONFIG.copy()
    
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        # 合并默认配置（处理新增配置项）
        for key, value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config
    except Exception as e:
        print(f"[配置] 读取失败，使用默认配置: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """保存配置到文件"""
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def reload_config():
    """重新加载配置并更新全局变量"""
    global _CONFIG
    _CONFIG = load_config()


# 初始化配置
_CONFIG = load_config()


def _cfg(key: str, default=None):
    """获取配置值的便捷函数"""
    return _CONFIG.get(key, DEFAULT_CONFIG.get(key, default))


# 配置变量
NOTIFY_ENABLED = _cfg("notify_enabled", True)
PARALLEL_ENABLED = _cfg("parallel_enabled", True)
QYWX_WEBHOOK = _cfg("qywx_webhook", "")
KEEPALIVE_DURATION = _cfg("keepalive_duration", 60)
KEEPALIVE_DURATION_POWERON = _cfg("keepalive_duration_poweron", 90)
HEALTH_CHECK_INTERVAL = _cfg("health_check_interval", 15)
MIN_DATA_RATE = _cfg("min_data_rate", 1.0)
MAX_ZERO_RATE_COUNT = _cfg("max_zero_rate_count", 3)
MAX_RECONNECT_ATTEMPTS = _cfg("max_reconnect_attempts", 2)
DAEMON_INTERVAL = _cfg("daemon_interval", 600)
MAX_CONCURRENT_ACCOUNTS = _cfg("max_concurrent_accounts", 2)
ACCOUNT_TIMEOUT = _cfg("account_timeout", 600)
RETRY_ON_FAILURE = _cfg("retry_on_failure", 1)
LOGIN_TIMEOUT = _cfg("login_timeout", 120)
CAPTCHA_RETRY = _cfg("captcha_retry", 3)


def get_state_file(phone: str) -> Path:
    """获取账号对应的状态文件路径"""
    return DATA_DIR / f"ctyun_state_{phone}.json"


def load_accounts() -> list[dict]:
    """加载账号列表"""
    if ACCOUNTS_FILE.exists():
        try:
            return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_accounts(accounts: list[dict]):
    """保存账号列表"""
    ACCOUNTS_FILE.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")


def find_account(phone: str) -> Optional[dict]:
    """查找账号"""
    for acc in load_accounts():
        if acc.get("phone") == phone:
            return acc
    return None


def add_account(phone: str, password: str):
    """添加或更新账号"""
    accounts = load_accounts()
    for acc in accounts:
        if acc.get("phone") == phone:
            acc["password"] = password
            acc["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_accounts(accounts)
            return
    accounts.append({
        "phone": phone,
        "password": password,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_accounts(accounts)


def delete_account(phone: str) -> bool:
    """删除账号"""
    accounts = load_accounts()
    for i, acc in enumerate(accounts):
        if acc.get("phone") == phone:
            del accounts[i]
            save_accounts(accounts)
            # 删除状态文件
            state_file = get_state_file(phone)
            if state_file.exists():
                state_file.unlink()
            return True
    return False


def update_device_filter(phone: str, mode: str, devices: list[str] = None):
    """更新账号的设备筛选配置
    
    Args:
        phone: 手机号
        mode: 筛选模式 ('none', 'whitelist', 'blacklist')
        devices: 设备名或ID列表
    """
    accounts = load_accounts()
    for acc in accounts:
        if acc.get("phone") == phone:
            acc["device_filter"] = {
                "mode": mode,
                "devices": devices or []
            }
            save_accounts(accounts)
            return True
    return False


def check_device_allowed(account: dict, device_name: str, device_id: str) -> tuple[bool, str]:
    """检查设备是否被允许保活
    
    Returns:
        (allowed, reason)
    """
    device_filter = account.get("device_filter", {})
    mode = device_filter.get("mode", "none")
    devices = device_filter.get("devices", [])
    
    if mode == "none" or not devices:
        return True, ""
    
    # 检查设备是否在列表中（支持名称或ID匹配）
    in_list = device_name in devices or device_id in devices
    
    if mode == "whitelist":
        if in_list:
            return True, ""
        return False, "不在白名单"
    elif mode == "blacklist":
        if in_list:
            return False, "在黑名单"
        return True, ""
    
    return True, ""


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class DeviceInfo:
    name: str
    obj_id: str
    use_status: str
    status: str
    real_status: str = ""  # State API 返回的状态（运行中/已关机等），仅用于显示
    
    @property
    def is_powered_off(self) -> bool:
        """设备是否关机"""
        return "关机" in self.use_status
    
    @property
    def is_online(self) -> bool:
        """用户是否正在操作云手机（在线运行=用户在操作，应跳过保活）"""
        return "在线运行" in self.use_status
    
    @property
    def is_running(self) -> bool:
        """设备是否正在运行（运行中=设备正常，离线运行也属于运行中）"""
        if self.real_status:
            return "运行中" in self.real_status
        # 根据 useStatus 判断：离线运行/在线运行 都算运行中
        return "运行" in self.use_status and "关机" not in self.use_status


@dataclass
class KeepaliveResult:
    device_name: str
    action: str = "无操作"
    initial_status: str = ""
    final_status: str = ""
    data_received: int = 0
    reconnect_count: int = 0


@dataclass
class AccountResult:
    phone: str
    power_on_count: int = 0
    keepalive_count: int = 0
    devices: list = field(default_factory=list)
    error: Optional[str] = None


# ============================================================================
# 工具函数
# ============================================================================

def print_header(title: str, width: int = 50):
    print(f"\n{'=' * width}")
    print(f" {title}")
    print(f"{'=' * width}")


def print_step(step: int, message: str):
    print(f"[{step}] {message}")


def print_device(device: DeviceInfo, index: int):
    print(f"\n    ┌─ 设备 {index + 1}: {device.name}")
    print(f"    │  ID: {device.obj_id}")
    print(f"    │  状态: {device.use_status}")
    print(f"    └─ 健康度: {device.status}")


def print_progress(elapsed: int, received_kb: float, rate: float, status: str):
    icons = {"good": "●", "warning": "◑", "error": "○"}
    icon = icons.get(status, "·")
    print(f"        {icon} {elapsed:3d}s │ {received_kb:7.1f} KB │ {rate:5.1f} KB/s")


def send_notification(title: str, content: str):
    if not NOTIFY_ENABLED:
        return
    if not QYWX_WEBHOOK:
        return
    try:
        import requests
        requests.post(
            QYWX_WEBHOOK,
            json={"msgtype": "markdown", "markdown": {"content": f"# {title}\n\n{content}"}},
            timeout=10
        )
    except Exception as e:
        print(f"推送失败: {e}")


def input_with_default(prompt: str, default: str = "") -> str:
    """带默认值的输入"""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


# ============================================================================
# 登录模块
# ============================================================================

async def login_account(phone: str, password: str) -> tuple[bool, str]:
    """登录账号并保存状态，支持验证码重试"""
    print_header(f"登录账号: {phone}")
    
    async def do_login() -> tuple[bool, str]:
        """执行登录的内部函数"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            api_responses = []
            
            async def capture_api(response):
                url = response.url
                if 'desk.ctyun.cn' in url or 'ctyun.cn' in url:
                    try:
                        body = await response.text()
                        api_responses.append({'url': url, 'body': body})
                    except:
                        pass
            
            page.on('response', capture_api)
            
            try:
                print_step(1, "访问登录页...")
                await page.goto('https://pm.ctyun.cn/', timeout=60000)
                await asyncio.sleep(2)
                
                print_step(2, "点击登录按钮...")
                login_btn = page.get_by_role("button").filter(has_text="登录")
                await login_btn.click()
                await asyncio.sleep(2)
                
                print_step(3, "填写登录信息...")
                await page.locator('input[type="text"]').fill(phone)
                await page.locator('input[type="password"]').fill(password)
                
                print_step(4, "提交登录...")
                submit_btn = page.locator('button').filter(has_text="登").first
                await submit_btn.click()
                await asyncio.sleep(3)
                
                current_url = page.url
                print(f"    当前URL: {current_url}")
                
                # 检查是否需要设备验证
                if 'device_verify' in current_url:
                    print_step(5, "需要设备验证...")
                    
                    # 验证码重试循环
                    for retry in range(CAPTCHA_RETRY):
                        if retry > 0:
                            print(f"\n    ⟳ 验证码重试 ({retry + 1}/{CAPTCHA_RETRY})...")
                        
                        # 捕获验证码
                        captcha_data = None
                        
                        async def capture_captcha(response):
                            nonlocal captcha_data
                            if 'captcha' in response.url.lower():
                                ct = response.headers.get('content-type', '')
                                if 'image' in ct:
                                    captcha_data = await response.body()
                        
                        page.on('response', capture_captcha)
                        
                        # 点击验证码图片刷新
                        captcha_img = page.locator('img').first
                        await captcha_img.click()
                        await asyncio.sleep(1)
                        
                        if not captcha_data:
                            # 等待验证码加载
                            for _ in range(5):
                                await asyncio.sleep(0.5)
                                if captcha_data:
                                    break
                        
                        if not captcha_data:
                            await browser.close()
                            return False, "无法获取图形验证码"
                        
                        # 识别验证码
                        try:
                            import ddddocr
                            ocr = ddddocr.DdddOcr(show_ad=False)
                            captcha_code = ocr.classification(captcha_data)
                            print(f"    图形验证码: {captcha_code}")
                        except Exception as e:
                            await browser.close()
                            return False, f"验证码识别失败: {e}"
                        
                        # 填写图形验证码
                        inputs = await page.locator('input').all()
                        if len(inputs) >= 2:
                            await inputs[1].fill(captcha_code)
                        else:
                            await browser.close()
                            return False, "页面结构异常"
                        
                        # 发送短信
                        print_step(6, "发送短信验证码...")
                        try:
                            get_code_btn = page.locator('button').filter(has_text="获取")
                            await get_code_btn.click()
                            await asyncio.sleep(2)
                        except Exception:
                            await browser.close()
                            return False, "发送短信按钮未找到"
                        
                        # 检查发送结果
                        sms_sent = False
                        sms_error = ""
                        for r in api_responses:
                            if 'getSmsCode' in r['url'] or 'sms' in r['url'].lower():
                                try:
                                    data = json.loads(r['body'])
                                    if data.get('code') == 0:
                                        print("    ✓ 短信发送成功!")
                                        sms_sent = True
                                    else:
                                        sms_error = data.get('msg', '未知错误')
                                        print(f"    ✗ 发送失败: {sms_error}")
                                except:
                                    pass
                        
                        # 如果发送失败且是验证码错误，继续重试
                        if not sms_sent:
                            if "验证码" in sms_error or "captcha" in sms_error.lower():
                                continue  # 继续重试验证码
                            await browser.close()
                            return False, f"短信发送失败: {sms_error}"
                        
                        # 短信发送成功，等待用户输入
                        print("\n" + "=" * 50)
                        sms_code = input("请输入短信验证码: ").strip()
                        print("=" * 50)
                        
                        if not sms_code:
                            await browser.close()
                            return False, "未输入短信验证码"
                        
                        print_step(7, "验证身份...")
                        if len(inputs) >= 3:
                            await inputs[2].fill(sms_code)
                        else:
                            await inputs[-1].fill(sms_code)
                        
                        # 点击确认
                        confirm_btn = page.locator('button').filter(has_text="确认")
                        await confirm_btn.click()
                        await asyncio.sleep(3)
                        
                        # 检查是否验证成功
                        current_url = page.url
                        if 'device_verify' not in current_url:
                            break  # 验证成功，退出重试循环
                        
                        # 验证失败，检查是否是验证码错误
                        verify_error = ""
                        for r in api_responses:
                            if 'verify' in r['url'].lower():
                                try:
                                    data = json.loads(r['body'])
                                    verify_error = data.get('msg', '')
                                except:
                                    pass
                        
                        if "验证码" in verify_error or "code" in verify_error.lower():
                            print(f"    ✗ 验证码错误: {verify_error}")
                            continue  # 继续重试
                        
                        # 其他错误
                        await browser.close()
                        return False, f"验证失败: {verify_error}"
                    
                    else:
                        # 重试次数用尽
                        await browser.close()
                        return False, f"验证码重试 {CAPTCHA_RETRY} 次后仍失败"
                
                # 检查登录结果
                await asyncio.sleep(2)
                current_url = page.url
                
                if 'device_verify' in current_url or 'login' in current_url:
                    await browser.close()
                    return False, "登录失败，请检查账号密码或验证码"
                
                # 保存状态
                print_step(8, "保存登录状态...")
                state = await context.storage_state()
                state_file = get_state_file(phone)
                state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
                
                # 保存账号
                add_account(phone, password)
                
                await browser.close()
                return True, "登录成功"
                
            except asyncio.TimeoutError:
                await browser.close()
                return False, "登录超时"
            except Exception as e:
                await browser.close()
                return False, f"登录出错: {e}"
    
    # 执行登录，带整体超时控制
    try:
        return await asyncio.wait_for(do_login(), timeout=LOGIN_TIMEOUT)
    except asyncio.TimeoutError:
        return False, f"登录超时 ({LOGIN_TIMEOUT}秒)"


# ============================================================================
# 保活模块
# ============================================================================

class KeepaliveManager:
    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.context = context
        self.ws_received = 0
        self.ws_endpoints: list[str] = []
        self._setup_handlers()
    
    def _setup_handlers(self):
        async def on_websocket(ws):
            endpoint = ws.url.split('/')[-1]
            self.ws_endpoints.append(endpoint)
            
            def on_frame(payload):
                if isinstance(payload, bytes):
                    self.ws_received += len(payload)
            
            ws.on('framereceived', on_frame)
        
        self.page.on('websocket', on_websocket)
    
    def reset(self):
        self.ws_received = 0
        self.ws_endpoints = []
    
    async def wait_for_websocket(self, timeout: int = 8):
        for _ in range(timeout):
            await asyncio.sleep(1)
            if self.ws_endpoints:
                return True
        return False


class DeviceKeepalive:
    def __init__(self, manager: KeepaliveManager, device: DeviceInfo, index: int):
        self.manager = manager
        self.device = device
        self.index = index
        self.reconnect_count = 0
    
    async def enter_device(self) -> bool:
        if self.index == 0:
            return await self.manager.page.evaluate('''
                () => {
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        if (el.textContent?.trim() === '进入') {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }
            ''')
        else:
            return await self.manager.page.evaluate(f'''
                () => {{
                    const items = document.querySelectorAll('.van-swipe-item');
                    if (items.length <= {self.index}) return false;
                    
                    const btn = Array.from(items[{self.index}].querySelectorAll('*'))
                        .find(el => el.textContent?.trim() === '进入');
                    
                    btn?.click();
                    return !!btn;
                }}
            ''')
    
    async def reconnect(self) -> bool:
        print("        │  ⚠ 检测到连接异常，尝试重连...")
        self.reconnect_count += 1
        
        try:
            await self.manager.page.goto('https://pm.ctyun.cn/#/home', timeout=30000)
            await asyncio.sleep(2)
            
            self.manager.reset()
            
            if await self.enter_device():
                await asyncio.sleep(10)
                if self.manager.ws_endpoints:
                    print(f"        │  ✓ 重连成功")
                    return True
            
            print("        │  ✗ 重连失败")
            return False
            
        except Exception as e:
            print(f"        │  ✗ 重连出错: {e}")
            return False
    
    async def run(self, duration: int) -> KeepaliveResult:
        result = KeepaliveResult(
            device_name=self.device.name,
            initial_status=self.device.use_status
        )
        
        print(f"        │  进入设备...")
        if not await self.enter_device():
            result.action = "未找到按钮"
            return result
        
        wait_time = 25 if self.device.is_powered_off else 8
        if not await self.manager.wait_for_websocket(wait_time):
            result.action = "连接失败"
            return result
        
        print(f"        │  WebSocket: {', '.join(self.manager.ws_endpoints[:5])}")
        print(f"        │  保活 {duration}s...")
        
        last_received = 0
        zero_count = 0
        start_time = time.time()
        
        while time.time() - start_time < duration:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
            elapsed = int(time.time() - start_time)
            current = self.manager.ws_received
            rate = (current - last_received) / HEALTH_CHECK_INTERVAL / 1024
            
            if rate < MIN_DATA_RATE:
                zero_count += 1
                status = "warning" if zero_count < MAX_ZERO_RATE_COUNT else "error"
            else:
                zero_count = 0
                status = "good"
            
            print_progress(elapsed, current / 1024, rate, status)
            last_received = current
            
            if zero_count >= MAX_ZERO_RATE_COUNT and self.reconnect_count < MAX_RECONNECT_ATTEMPTS:
                if await self.reconnect():
                    zero_count = 0
                    last_received = 0
                else:
                    zero_count = 0
        
        result.action = "保活成功" + (f"(重连{self.reconnect_count}次)" if self.reconnect_count else "")
        result.data_received = self.manager.ws_received
        result.final_status = "保活完成"
        result.reconnect_count = self.reconnect_count
        
        data_kb = self.manager.ws_received / 1024
        if data_kb > 1024:
            print(f"        └─ ✓ 完成: {data_kb:.1f} KB")
        elif data_kb > 100:
            print(f"        └─ ⚠ 完成: {data_kb:.1f} KB (数据较少)")
        else:
            print(f"        └─ ✗ 完成: {data_kb:.1f} KB (可能异常)")
        
        return result


async def process_account(account: dict, index: int = 0, total: int = 1) -> AccountResult:
    """处理单个账号的保活，支持重试机制"""
    phone = account["phone"]
    result = AccountResult(phone=phone)
    
    # 进度前缀
    prefix = f"[{index+1}/{total}]" if total > 1 else ""
    
    print_header(f"{prefix} 账号: {phone}")
    
    state_file = get_state_file(phone)
    if not state_file.exists():
        result.error = f"未找到登录状态文件，请先登录"
        return result
    
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception as e:
        result.error = f"状态文件读取失败: {e}"
        return result
    
    async def do_keepalive() -> AccountResult:
        """执行保活的内部函数"""
        inner_result = AccountResult(phone=phone)
        browser = None
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                await context.add_cookies(state.get('cookies', []))
                
                page = await context.new_page()
                
                devices_data = []
                devices_ready = asyncio.Event()
                device_states = {}  # State API 返回的设备状态（仅用于显示，不用于跳过保活）
                
                async def capture_api(response):
                    """捕获 API 响应"""
                    url = response.url
                    try:
                        if 'desktop/client/list' in url:
                            data = json.loads(await response.text())
                            if data.get('code') == 0:
                                devices_data.extend(data.get('data', {}).get('desktopList', []))
                                print(f"        [+] 捕获设备列表: {len(devices_data)} 台")
                                devices_ready.set()
                        elif 'desktop/client/state' in url:
                            # 设备状态 API，返回设备是否正常运行（运行中/已关机）
                            # 注意：这里不能用来判断是否跳过保活
                            data = json.loads(await response.text())
                            if data.get('code') == 0:
                                state_data = data.get('data', {})
                                desktop_id = str(state_data.get('desktopId') or state_data.get('objId', ''))
                                real_status = state_data.get('status') or state_data.get('useStatus', '')
                                if desktop_id:
                                    device_states[desktop_id] = real_status
                    except (json.JSONDecodeError, Exception):
                        pass
                
                page.on('response', lambda r: asyncio.create_task(capture_api(r)))
                
                manager = KeepaliveManager(page, context)
                
                print_step(1, "访问控制台...")
                try:
                    await page.goto('https://pm.ctyun.cn/', timeout=60000)
                except Exception as e:
                    inner_result.error = f"访问失败: {e}"
                    return inner_result
                
                print_step(2, "加载登录状态...")
                for origin in state.get('origins', []):
                    if origin.get('origin') == 'https://pm.ctyun.cn':
                        for item in origin.get('localStorage', []):
                            try:
                                name = item.get('name', '').replace("'", "\\'")
                                value = item.get('value', '').replace("'", "\\'")
                                await page.evaluate(f"localStorage.setItem('{name}', '{value}')")
                            except Exception:
                                pass
                
                await page.reload()
                await asyncio.sleep(5)
                
                if 'device_verify' in page.url or 'login' in page.url:
                    inner_result.error = "登录状态已过期，请重新登录"
                    return inner_result
                
                if not devices_data:
                    try:
                        await asyncio.wait_for(devices_ready.wait(), timeout=10)
                    except asyncio.TimeoutError:
                        pass
                
                if not devices_data:
                    inner_result.error = "未获取到设备列表"
                    return inner_result
                
                print(f"✓ 获取到 {len(devices_data)} 台设备")
                if device_states:
                    print(f"  设备状态: {len(device_states)} 台已获取")
                
                for i, dev in enumerate(devices_data):
                    obj_id = str(dev.get('desktopId') or dev.get('objId'))
                    device = DeviceInfo(
                        name=dev.get('desktopName') or dev.get('objName', '未命名'),
                        obj_id=obj_id,
                        use_status=dev.get('useStatus', '未知'),
                        status=dev.get('status', '未知'),
                        real_status=device_states.get(obj_id, '')
                    )
                    
                    print_device(device, i)
                    if device.real_status:
                        print(f"        │  设备状态: {device.real_status}")
                    
                    # 设备筛选检查
                    allowed, filter_reason = check_device_allowed(account, device.name, device.obj_id)
                    if not allowed:
                        print(f"        │  ⊘ 跳过: {filter_reason}")
                        inner_result.devices.append({
                            "name": device.name,
                            "action": f"跳过({filter_reason})",
                            "initial_status": device.use_status,
                            "data_kb": 0
                        })
                        continue
                    
                    # 检查用户是否正在操作（在线运行=用户在用，跳过保活）
                    if device.is_online:
                        print(f"        │  ✓ 在线运行（用户操作中），跳过保活")
                        inner_result.devices.append({
                            "name": device.name,
                            "action": "跳过(用户操作中)",
                            "initial_status": device.use_status,
                            "real_status": device.real_status,
                            "data_kb": 0
                        })
                        continue
                    
                    if i > 0:
                        try:
                            await page.close()
                        except Exception:
                            pass
                        
                        page = await context.new_page()
                        devices_data.clear()
                        devices_ready.clear()
                        device_states.clear()
                        page.on('response', lambda r: asyncio.create_task(capture_api(r)))
                        manager = KeepaliveManager(page, context)
                        
                        print("        │  创建新页面...")
                        await page.goto('https://pm.ctyun.cn/#/home', timeout=30000)
                        await asyncio.sleep(3)
                    
                    keeper = DeviceKeepalive(manager, device, i)
                    duration = KEEPALIVE_DURATION_POWERON if device.is_powered_off else KEEPALIVE_DURATION
                    
                    keep_result = await keeper.run(duration)
                    
                    # 保活完成后检查精确状态
                    await asyncio.sleep(3)
                    final_real_status = device_states.get(device.obj_id, '')
                    
                    if "成功" in keep_result.action:
                        inner_result.keepalive_count += 1
                        if device.is_powered_off:
                            inner_result.power_on_count += 1
                        
                        # 显示保活后状态
                        if final_real_status:
                            print(f"        │  ✓ 保活完成，设备状态: {final_real_status}")
                    
                    inner_result.devices.append({
                        "name": keep_result.device_name,
                        "action": keep_result.action,
                        "initial_status": keep_result.initial_status,
                        "real_status": final_real_status,
                        "data_kb": keep_result.data_received / 1024
                    })
                
                return inner_result
        finally:
            if browser:
                await browser.close()
    
    # 执行保活，支持重试
    max_retries = max(0, RETRY_ON_FAILURE)
    last_error = None
    
    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"\n        ⟳ 第 {attempt + 1} 次重试...")
        
        try:
            result = await do_keepalive()
            if not result.error:
                return result
            last_error = result.error
            
            # 如果是登录过期，不需要重试
            if "过期" in result.error or "未登录" in result.error:
                break
                
        except asyncio.TimeoutError:
            last_error = "账号处理超时"
        except Exception as e:
            last_error = str(e)
    
    result.error = last_error
    return result


async def run_once(accounts: list[dict] = None):
    """执行一次保活，支持并发控制和超时"""
    if accounts is None:
        accounts = load_accounts()
    
    if not accounts:
        print("没有可用的账号，请先添加账号")
        return 0, 0
    
    total_accounts = len(accounts)
    
    # 并发控制信号量
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_ACCOUNTS)
    
    async def process_with_semaphore(account: dict, index: int, total: int) -> AccountResult:
        """带信号量控制的账号处理"""
        async with semaphore:
            try:
                # 添加超时控制
                return await asyncio.wait_for(
                    process_account(account, index, total),
                    timeout=ACCOUNT_TIMEOUT
                )
            except asyncio.TimeoutError:
                result = AccountResult(phone=account["phone"])
                result.error = f"账号处理超时 ({ACCOUNT_TIMEOUT}秒)"
                return result
    
    # 多账号并行或顺序执行
    if PARALLEL_ENABLED and total_accounts > 1:
        print(f"并行模式: 并发数 {MAX_CONCURRENT_ACCOUNTS}, 共 {total_accounts} 个账号")
        
        # 并行执行，带进度显示
        tasks = [
            process_with_semaphore(acc, i, total_accounts)
            for i, acc in enumerate(accounts)
        ]
        
        # 使用 as_completed 显示进度
        results = []
        completed = 0
        
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            
            # 进度显示
            status = "✓" if not result.error else "✗"
            print(f"\n  [{completed}/{total_accounts}] {status} {result.phone}" + 
                  (f" - {result.error}" if result.error else ""))
        
        # 按原始顺序排序结果
        phone_order = {acc["phone"]: i for i, acc in enumerate(accounts)}
        results.sort(key=lambda r: phone_order.get(r.phone, 999))
    else:
        # 顺序执行
        print(f"顺序模式: 共 {total_accounts} 个账号")
        results = []
        for i, account in enumerate(accounts):
            print(f"\n  处理进度: [{i+1}/{total_accounts}]")
            result = await process_with_semaphore(account, i, total_accounts)
            results.append(result)
    
    print_header("执行汇总")
    
    notify_parts = []
    total_power = 0
    total_keep = 0
    success_count = 0
    error_count = 0
    
    for r in results:
        print(f"\n账号: {r.phone}")
        
        if r.error:
            print(f"  ✗ 错误: {r.error}")
            notify_parts.append(f"**{r.phone}**\n错误: {r.error}")
            error_count += 1
            continue
        
        success_count += 1
        
        if r.power_on_count:
            print(f"  开机: {r.power_on_count} 台")
            total_power += r.power_on_count
        
        if r.keepalive_count:
            print(f"  保活: {r.keepalive_count} 台")
            total_keep += r.keepalive_count
        
        device_lines = []
        for d in r.devices:
            line = f"  - {d['name']}: {d['action']}"
            if d['data_kb'] > 0:
                line += f" ({d['data_kb']:.0f}KB)"
            print(line)
            device_lines.append(line)
        
        notify_parts.append(f"**{r.phone}**\n开机: {r.power_on_count} 台\n保活: {r.keepalive_count} 台\n" + "\n".join(device_lines))
    
    print(f"\n{'─' * 40}")
    print(f"统计: 成功 {success_count}/{total_accounts}, 开机 {total_power} 台, 保活 {total_keep} 台")
    
    # 发送通知（有结果时才发送）
    if total_power > 0 or total_keep > 0 or error_count > 0:
        content = f"成功: {success_count}/{total_accounts}\n开机: {total_power} 台\n保活: {total_keep} 台\n"
        if error_count > 0:
            content += f"异常: {error_count} 个账号\n"
        content += "\n" + "\n\n".join(notify_parts)
        content += f"\n\n执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        send_notification("天翼云手机保活", content)
    
    return total_power, total_keep


async def run_daemon(interval: int):
    """守护进程模式"""
    accounts = load_accounts()
    if not accounts:
        print("没有可用的账号，请先添加账号")
        return
    
    print(f"守护进程模式: 每 {interval} 秒执行一次")
    print(f"按 Ctrl+C 停止\n")
    
    round_num = 1
    while True:
        print_header(f"第 {round_num} 轮 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            await run_once(accounts)
        except Exception as e:
            print(f"执行出错: {e}")
        
        round_num += 1
        
        next_time = (datetime.now() + timedelta(seconds=interval)).strftime('%H:%M:%S')
        print(f"\n⏰ 下次执行: {interval} 秒后 (约 {next_time})")
        
        await asyncio.sleep(interval)


# ============================================================================
# 依赖管理模块
# ============================================================================

REQUIRED_PACKAGES = [
    ("playwright", "playwright"),
    ("ddddocr", "ddddocr"),
    ("requests", "requests"),
]

PID_FILE = DATA_DIR / "ctyun_daemon.pid"
LOG_FILE = DATA_DIR / "ctyun_keepalive.log"


def check_dependencies() -> tuple[list[str], list[str]]:
    """检查依赖，返回 (已安装列表, 缺失列表)"""
    installed = []
    missing = []
    
    for module_name, package_name in REQUIRED_PACKAGES:
        try:
            __import__(module_name)
            installed.append(package_name)
        except ImportError:
            missing.append(package_name)
    
    return installed, missing


def install_dependencies() -> bool:
    """安装缺失的依赖"""
    installed, missing = check_dependencies()
    
    if not missing:
        print("所有依赖已安装!")
        return True
    
    print(f"缺失依赖: {', '.join(missing)}")
    print("正在安装...")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q"
        ] + missing)
        print("✓ 依赖安装完成")
        
        # 检查 playwright 浏览器
        try:
            subprocess.check_call([
                sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✓ Playwright 浏览器已安装")
        except:
            print("⚠ Playwright 浏览器安装失败，请手动运行: playwright install chromium")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 安装失败: {e}")
        return False


def menu_dependencies():
    """菜单：检测/安装依赖"""
    print_header("依赖管理")
    
    installed, missing = check_dependencies()
    
    print("  已安装:", ", ".join(installed) if installed else "无")
    print("  未安装:", ", ".join(missing) if missing else "无")
    
    if missing:
        print()
        choice = input("安装缺失依赖? (y/n): ").strip().lower()
        if choice == 'y':
            install_dependencies()
    else:
        print("\n  所有依赖已满足!")


# ============================================================================
# 后台运行模块
# ============================================================================

def get_daemon_info() -> dict:
    """获取守护进程详细信息"""
    info = {
        "running": False,
        "pid": None,
        "uptime": None,
        "log_size": 0,
        "log_file": str(LOG_FILE),
        "interval": DAEMON_INTERVAL
    }
    
    if not PID_FILE.exists():
        return info
    
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # 检查进程是否存在
        info["running"] = True
        info["pid"] = pid
        
        # 获取进程运行时间
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "etime="],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                info["uptime"] = result.stdout.strip()
        except Exception:
            pass
        
    except (ValueError, ProcessLookupError, PermissionError):
        # 进程不存在，清理 PID 文件
        PID_FILE.unlink(missing_ok=True)
    
    # 获取日志文件大小
    if LOG_FILE.exists():
        info["log_size"] = LOG_FILE.stat().st_size
    
    return info
    
    # 获取日志文件大小
    if LOG_FILE.exists():
        info["log_size"] = LOG_FILE.stat().st_size
    
    return info


def is_daemon_running() -> bool:
    """检查守护进程是否在运行"""
    return get_daemon_info()["running"]


def start_daemon_background(interval: int = None) -> tuple[bool, str]:
    """后台启动守护进程，返回 (成功, 消息)"""
    if is_daemon_running():
        return False, "守护进程已在运行中"
    
    if interval is None:
        interval = DAEMON_INTERVAL
    
    cmd = [
        sys.executable, __file__,
        "-d", "-i", str(interval)
    ]
    
    # 使用 nohup 后台运行，日志保存到脚本目录
    with open(LOG_FILE, 'a') as log:
        log.write(f"\n{'='*50}\n")
        log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 守护进程启动\n")
        log.write(f"间隔: {interval} 秒\n")
        log.write(f"{'='*50}\n\n")
        log.flush()
        
        process = subprocess.Popen(
            f"nohup {' '.join(cmd)} >> {LOG_FILE} 2>&1 &",
            shell=True,
            start_new_session=True
        )
    
    # 等待进程启动
    time.sleep(1.5)
    
    # 验证进程是否真正启动
    for _ in range(3):
        info = get_daemon_info()
        if info["running"]:
            return True, f"守护进程已启动 (PID: {info['pid']})"
        time.sleep(0.5)
    
    return False, "守护进程启动失败，请检查日志"


def stop_daemon() -> tuple[bool, str]:
    """停止守护进程，返回 (成功, 消息)"""
    info = get_daemon_info()
    
    if not info["running"]:
        if PID_FILE.exists():
            PID_FILE.unlink()
        return False, "守护进程未运行"
    
    pid = info["pid"]
    
    try:
        # 先发送 SIGTERM
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        
        # 检查是否已停止
        try:
            os.kill(pid, 0)  # 还在运行
            # 强制杀死
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
        except ProcessLookupError:
            pass  # 已停止
        
        if PID_FILE.exists():
            PID_FILE.unlink()
        
        # 记录停止日志
        with open(LOG_FILE, 'a') as log:
            log.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 守护进程已停止\n")
        
        return True, f"守护进程已停止 (PID: {pid})"
        
    except ProcessLookupError:
        if PID_FILE.exists():
            PID_FILE.unlink()
        return True, "守护进程已停止"
    except Exception as e:
        return False, f"停止失败: {e}"


def restart_daemon(interval: int = None) -> tuple[bool, str]:
    """重启守护进程"""
    # 先停止
    if is_daemon_running():
        stop_ok, stop_msg = stop_daemon()
        if not stop_ok:
            return False, f"重启失败(停止阶段): {stop_msg}"
        time.sleep(1)
    
    # 再启动
    if interval is None:
        interval = DAEMON_INTERVAL
    
    return start_daemon_background(interval)


def print_daemon_status():
    """打印守护进程状态"""
    info = get_daemon_info()
    print("-" * 40)
    print(f"  状态: {'运行中' if info['running'] else '未运行'}")
    if info["running"]:
        print(f"  PID: {info['pid']}")
        if info["uptime"]:
            print(f"  运行时间: {info['uptime']}")
    log_size = info["log_size"]
    if log_size > 1024 * 1024:
        log_size_str = f"{log_size / 1024 / 1024:.1f}MB"
    elif log_size > 1024:
        log_size_str = f"{log_size / 1024:.0f}KB"
    else:
        log_size_str = f"{log_size}B"
    print(f"  日志大小: {log_size_str}")
    print("-" * 40)


def view_log(lines: int = 30):
    """查看日志"""
    if not LOG_FILE.exists():
        print("日志文件不存在")
        return
    print(f"\n--- 最近 {lines} 行日志 ---.\n")
    subprocess.run(["tail", "-n", str(lines), str(LOG_FILE)])


def clear_log():
    """清空日志"""
    if LOG_FILE.exists():
        LOG_FILE.unlink()
        print("日志已清空")


def menu_daemon_background():
    """菜单：后台运行管理"""
    while True:
        info = get_daemon_info()
        print_header("后台运行管理")
        
        if info["running"]:
            print(f"  状态: 运行中 (PID: {info['pid']})")
            print("-" * 40)
            print("  [1] 查看状态  [2] 查看日志  [3] 重启")
            print("  [4] 停止      [5] 清空日志  [0] 返回")
        else:
            print("  状态: 未运行")
            print("-" * 40)
            print("  [1] 启动      [2] 查看日志  [0] 返回")
        
        choice = input("\n请选择: ").strip()
        
        if choice == '0':
            break
        
        if info["running"]:
            if choice == '1':
                print_daemon_status()
            elif choice == '2':
                view_log()
            elif choice == '3':
                interval = input(f"间隔秒数 [{DAEMON_INTERVAL}]: ").strip()
                interval = int(interval) if interval else DAEMON_INTERVAL
                if input("确认重启? (y/n): ").strip().lower() == 'y':
                    ok, msg = restart_daemon(interval)
                    print(f"{'✓' if ok else '✗'} {msg}")
            elif choice == '4':
                if input("确认停止? (y/n): ").strip().lower() == 'y':
                    ok, msg = stop_daemon()
                    print(f"{'✓' if ok else '✗'} {msg}")
            elif choice == '5':
                if input("确认清空日志? (y/n): ").strip().lower() == 'y':
                    clear_log()
        else:
            if choice == '1':
                interval = input(f"间隔秒数 [{DAEMON_INTERVAL}]: ").strip()
                interval = int(interval) if interval else DAEMON_INTERVAL
                ok, msg = start_daemon_background(interval)
                print(f"{'✓' if ok else '✗'} {msg}")
            elif choice == '2':
                view_log()
        
        if choice != '0':
            input("\n按回车继续...")


# ============================================================================
# 菜单模块
# ============================================================================

def show_menu():
    """显示主菜单"""
    print("\n" + "=" * 50)
    print(f"  天翼云手机保活脚本 {VERSION}")
    print("=" * 50)
    print("  [1] 执行一次保活")
    print("  [2] 添加/更新账号")
    print("  [3] 查看账号列表")
    print("  [4] 删除账号")
    print("  [5] 设备筛选配置")
    print("  [6] 查看配置")
    print("  [7] 依赖管理")
    print("  [0] 退出")
    print("=" * 50)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="天翼云手机保活脚本")
    parser.add_argument("-v", "--version", action="store_true", help="显示版本信息")
    parser.add_argument("-d", "--daemon", action="store_true", help="守护进程模式")
    parser.add_argument("-i", "--interval", type=int, help="守护进程间隔(秒)")
    parser.add_argument("-a", "--account", type=str, help="指定账号")
    parser.add_argument("-p", "--password", type=str, help="账号密码")
    args = parser.parse_args()
    
    if args.version:
        print(f"天翼云手机保活脚本 {VERSION}")
        return
    
    if args.daemon:
        interval = args.interval or DAEMON_INTERVAL
        asyncio.run(run_daemon(interval))
        return
    
    if args.account and args.password:
        # 命令行模式：直接登录
        success, msg = asyncio.run(login_account(args.account, args.password))
        print(f"{'✓' if success else '✗'} {msg}")
        return
    
    # 菜单模式
    while True:
        show_menu()
        choice = input("请选择: ").strip()
        
        if choice == '0':
            break
        
        elif choice == '1':
            asyncio.run(run_once())
            input("\n按回车继续...")
        
        elif choice == '2':
            phone = input("请输入手机号: ").strip()
            if not phone:
                print("手机号不能为空")
                continue
            password = input("请输入密码: ").strip()
            if not password:
                print("密码不能为空")
                continue
            success, msg = asyncio.run(login_account(phone, password))
            print(f"{'✓' if success else '✗'} {msg}")
            input("\n按回车继续...")
        
        elif choice == '3':
            accounts = load_accounts()
            if not accounts:
                print("没有账号")
            else:
                print("\n账号列表:")
                for i, acc in enumerate(accounts, 1):
                    print(f"{i}. 手机号: {acc.get('phone')}")
                    if acc.get('device_filter'):
                        mode = acc['device_filter'].get('mode', 'none')
                        devices = acc['device_filter'].get('devices', [])
                        print(f"   设备筛选: {mode} ({len(devices)}个设备)")
            input("\n按回车继续...")
        
        elif choice == '4':
            phone = input("请输入要删除的手机号: ").strip()
            if not phone:
                print("手机号不能为空")
                continue
            if delete_account(phone):
                print("删除成功")
            else:
                print("账号不存在")
            input("\n按回车继续...")
        
        elif choice == '5':
            phone = input("请输入手机号: ").strip()
            if not phone:
                print("手机号不能为空")
                continue
            account = find_account(phone)
            if not account:
                print("账号不存在")
                input("\n按回车继续...")
                continue
            
            print("\n设备筛选模式:")
            print("1. 无筛选 (默认)")
            print("2. 白名单 (只保活指定设备)")
            print("3. 黑名单 (跳过指定设备)")
            mode_choice = input("请选择: ").strip()
            
            mode_map = {"1": "none", "2": "whitelist", "3": "blacklist"}
            mode = mode_map.get(mode_choice, "none")
            
            devices = []
            if mode != "none":
                print("\n请输入设备名称或ID（每行一个，空行结束）:")
                while True:
                    device = input().strip()
                    if not device:
                        break
                    devices.append(device)
            
            if update_device_filter(phone, mode, devices):
                print("配置成功")
            else:
                print("配置失败")
            input("\n按回车继续...")
        
        elif choice == '6':
            print_header("查看配置")
            config = load_config()
            for key, value in config.items():
                label = CONFIG_LABELS.get(key, key)
                print(f"  {label}: {value}")
            input("\n按回车继续...")
        
        elif choice == '7':
            menu_dependencies()
            input("\n按回车继续...")
        
        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    main()
