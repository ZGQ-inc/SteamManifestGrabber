# Steam Manifest Grabber v1.10
# Author: ZGQ Inc. https://t.me/ZGQinc

import os
import subprocess
import json
import re
import shutil
import getpass
import sys
import argparse
from pathlib import Path
import urllib.request
import http.cookiejar
import time

DEPOTDOWNLOADER_DIR = "DepotDownloader"
LOGIN_FILE = "login.txt"
DEPOTS_DIR = "depots"
MANIFEST_DIR = "manifest"
DECRYPTION_KEY_FILE = "DecryptionKey.json"
COOKIES_FILE = "cookies.txt"
BATCH = "task.txt"
PROGRESS_FILE = "progress.json"
EXECUTABLE_NAME = "DepotDownloader.exe" if sys.platform == "win32" else "DepotDownloader"

def get_depotdownloader_path():
    path = Path(DEPOTDOWNLOADER_DIR) / EXECUTABLE_NAME
    if not path.exists():
        raise FileNotFoundError(f"错误: 未在 '{DEPOTDOWNLOADER_DIR}' 文件夹中找到 '{EXECUTABLE_NAME}'。")
    return path

def update_login_file(username_to_set_default):
    login_path = Path(LOGIN_FILE)
    accounts = []
    if login_path.exists():
        accounts = [line for line in login_path.read_text(encoding='utf-8').strip().splitlines() if line]
    
    if username_to_set_default in accounts:
        accounts.remove(username_to_set_default)
    
    accounts.insert(0, username_to_set_default)
    
    login_path.write_text('\n'.join(accounts) + '\n', encoding='utf-8')

def load_progress():
    progress_path = Path(PROGRESS_FILE)
    if progress_path.exists():
        try:
            with open(progress_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get("completed_appids", []))
        except json.JSONDecodeError:
            print(f"警告: {PROGRESS_FILE} 格式错误，将重新创建进度记录。")
    return set()

def save_progress(completed_appids_set):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"completed_appids": list(completed_appids_set)}, f, indent=4)

def perform_login(username):
    password = getpass.getpass(f"请输入账号 '{username}' 的 Steam 密码 (不可见): ")
    depotdownloader_exe = get_depotdownloader_path()

    login_cmd = [
        str(depotdownloader_exe),
        "-app", "1007",
        "-username", username,
        "-password", password,
        "-remember-password",
        "-manifest-only"
    ]

    print("\n正在尝试登录 Steam，请稍候...")
    print("如果需要，系统将提示输入 Steam Guard 验证码。")

    try:
        process = subprocess.Popen(
            login_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, encoding='utf-8', errors='ignore', bufsize=1
        )

        line_buffer = ""
        seen_logging_message = False

        while process.poll() is None:
            char = process.stdout.read(1)
            if not char:
                break
            sys.stdout.write(char)
            sys.stdout.flush()
            line_buffer += char

            if "STEAM GUARD!" in line_buffer.upper() and line_buffer.rstrip().endswith(':'):
                auth_code = input() 
                process.stdin.write(auth_code + '\n')
                process.stdin.flush()
                line_buffer = ""

            if char == '\n':
                if "Unable to login to Steam3: RateLimitExceeded" in line_buffer:
                    print("\n\n[错误] 登录触发了 Steam 的 RateLimitExceeded 限制！")
                    print("请完全停止操作脚本，等待 30 分钟至 1 小时后再试。")
                    process.terminate()
                    sys.exit(1)

                if "Logging" in line_buffer and "into Steam3" in line_buffer:
                    seen_logging_message = True
                if "Done!" in line_buffer and seen_logging_message:
                    print(f"\n账号 '{username}' 登录成功！")
                    update_login_file(username)
                    process.terminate()
                    return True
                line_buffer = ""
        
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        print("\n登录失败。请检查用户名、密码和验证码。")
        return False

    except FileNotFoundError as e:
        print(f"\n错误: {e}")
        return False
    except Exception as e:
        print(f"登录过程中发生意外错误: {e}")
        return False

def handle_login(selected_account=None):
    login_path = Path(LOGIN_FILE)
    accounts = []
    if login_path.exists():
        accounts = [line for line in login_path.read_text(encoding='utf-8').strip().splitlines() if line]

    if selected_account:
        if selected_account in accounts:
            print(f"选择已保存的账号: '{selected_account}'")
            update_login_file(selected_account)
            return selected_account
        else:
            print(f"账号 '{selected_account}' 是一个新账号，需要登录。")
            if perform_login(selected_account):
                return selected_account
            else:
                return None
    
    else:
        if accounts:
            default_user = accounts[0]
            print(f"使用默认账号: '{default_user}' ，如需切换账号，请使用 -a 或 --account 参数。")
            return default_user
        else:
            print("未找到任何已保存的账号，需要进行首次登录。")
            new_user = input("请输入 Steam 用户名: ")
            if perform_login(new_user):
                return new_user
            else:
                return None

def fetch_data(appid, username):
    print(f"\n开始为 AppID: {appid} 获取数据...")
    depot_keys = {}
    unavailable_depots = []
    last_depot_id = None
    depotdownloader_exe = get_depotdownloader_path()

    fetch_cmd = [
        str(depotdownloader_exe),
        "-app", appid,
        "-username", username,
        "-remember-password",
        "-manifest-only",
        "-os", "windows",
        "-all-archs",
        "-all-languages"
    ]

    try:
        process = subprocess.Popen(
            fetch_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True, encoding='utf-8', errors='ignore', bufsize=1
        )

        for line in iter(process.stdout.readline, ''):
            print(line, end='')
            sys.stdout.flush()

            if "A task was canceled." in line:
                print("\n\n警告: 与 Steam 服务器的连接超时或意外中断 (A task was canceled)")
                process.terminate()
                return "TIMEOUT", None

            if "Unable to login to Steam3: RateLimitExceeded" in line:
                print("\n\n[错误] 获取数据时触发 Steam 的 RateLimitExceeded 限制！")
                print("请完全停止操作脚本，等待 30 分钟至 1 小时冷却后再试。")
                process.terminate()
                return "RATELIMIT", None

            if "Unable to login to Steam3:" in line and "RateLimitExceeded" not in line:
                error_reason = line.split("Unable to login to Steam3:")[1].strip()
                print(f"\n\n警告: 登录凭据已失效或异常 (原因: {error_reason})")
                process.terminate()
                return "RELOGIN", None
                
            if "Unable to get steam3 credentials." in line or "Error: InitializeSteam failed" in line:
                print("\n\n警告: 无法获取 Steam 凭据，本地会话可能已过期")
                process.terminate()
                return "RELOGIN", None

            depot_id_match = re.search(r"Depot ID:\s*(\d+)", line, re.IGNORECASE)
            if depot_id_match:
                last_depot_id = depot_id_match.group(1)

            key_match = re.search(r"DecryptionKey:\s*([0-9a-fA-F]+)", line, re.IGNORECASE)
            if key_match and last_depot_id:
                depot_keys[last_depot_id] = key_match.group(1)
                last_depot_id = None

            unavailable_match = re.search(r"Depot\s+(\d+)\s+is not available", line, re.IGNORECASE)
            if unavailable_match:
                unavailable_depots.append(unavailable_match.group(1))

        process.wait()
        print("\n数据获取完成。")
        return depot_keys, unavailable_depots

    except FileNotFoundError as e:
        print(f"\n错误: {e}")
        return None, None
    except Exception as e:
        print(f"获取数据时发生错误: {e}")
        return None, None

def fetch_dlc_appids(appid, cookie_file=None):
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=en"
    print(f"\n正在从 Steam API 获取 AppID {appid} 的 DLC 列表...")

    opener = None
    if cookie_file and Path(cookie_file).exists():
        cookie_jar = http.cookiejar.MozillaCookieJar()
        cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    else:
        if cookie_file:
            print(f"警告: 指定的 Cookies 文件 '{cookie_file}' 不存在，将进行无 Cookie 访问。")
        opener = urllib.request.build_opener()

    opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/29.0 Chrome/136.0.0.0 Safari/537.36')]

    while True:
        try:
            with opener.open(url) as response:
                data = json.loads(response.read().decode('utf-8'))

            app_data = data.get(appid)
            if app_data and app_data.get('success'):
                dlc_list = app_data.get('data', {}).get('dlc', [])
                if dlc_list:
                    print(f"成功获取到 {len(dlc_list)} 个 DLC。")
                    return dlc_list
                else:
                    print("此 AppID 没有 DLC。")
                    return []
            else:
                print(f"警告: 从 Steam API 获取 DLC 列表失败，可能被锁区，请使用 -c 或 --cookies 参数提供 Cookies。返回信息: {app_data}")
                return []
        except Exception as e:
            print(f"警告: 调用 Steam API 时出错: {e}")
            print("5秒后重试...")
            time.sleep(5)
            continue

def save_json(appid, depot_keys):
    if not depot_keys:
        print("没有找到任何解密密钥，跳过生成 JSON 文件。")
        return

    json_path = Path(DECRYPTION_KEY_FILE)
    all_data = {}
    if json_path.exists():
        try:
            all_data = json.loads(json_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            print(f"警告: {DECRYPTION_KEY_FILE} 文件格式错误，将创建一个新的文件。")
    
    all_data[appid] = depot_keys
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
    print(f"解密密钥已保存到 {json_path}")

def organize_manifests(appid):
    source_dir = Path(DEPOTS_DIR)
    target_dir = Path(MANIFEST_DIR) / appid
    
    if not source_dir.exists():
        print(f"未找到 '{source_dir}' 目录，可能没有下载任何 manifest 文件。")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    
    manifest_files = list(source_dir.rglob("*.manifest"))
    
    if not manifest_files:
        print("未在 depots 目录中找到任何 .manifest 文件。")
        return

    for manifest_file in manifest_files:
        try:
            shutil.copy(manifest_file, target_dir)
            print(f"已复制: {manifest_file.name} -> {target_dir}")
        except Exception as e:
            print(f"复制文件 {manifest_file} 时出错: {e}")
            
    print(f"所有 .manifest 文件已整理到 {target_dir}")

def generate_lua(appid, depot_keys, unavailable_depots, manifest_less_dlcs):
    target_dir = Path(MANIFEST_DIR) / appid
    if not (depot_keys or unavailable_depots or manifest_less_dlcs):
        print("没有 Depot 或 DLC 数据，跳过生成 .lua 文件。")
        return
        
    target_dir.mkdir(parents=True, exist_ok=True)
    lua_path = target_dir / f"{appid}.lua"
    
    with open(lua_path, 'w', encoding='utf-8') as f:
        f.write(f'addappid("{appid}")\n')
        for depot_id, key in depot_keys.items():
            f.write(f'addappid("{depot_id}",1,"{key}")\n')
        for depot_id in unavailable_depots:
            f.write(f'addappid("{depot_id}")\n')
        if manifest_less_dlcs:
            print(f"正在将 {len(manifest_less_dlcs)} 个无清单的 DLC 添加到 .lua 文件...")
            for dlc_id in manifest_less_dlcs:
                f.write(f'addappid("{dlc_id}")\n')

    print(f"Lua 配置文件已生成: {lua_path}")

def main():
    parser = argparse.ArgumentParser(
        description="Steam Manifest Grabber by ZGQ Inc.",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False
    )
    parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='显示此帮助。')
    parser.add_argument("-a", "--account", help="指定要使用的 Steam 账号名。\n如果未提供，会使用上次登录的账号。")
    parser.add_argument("-c", "--cookies", help="指定用于访问 Steam API 的 Cookies 文件路径。", nargs='?', const=COOKIES_FILE, default=None)
    parser.add_argument("-b", "--batch", action="store_true", help="启用批处理模式。")
    args = parser.parse_args()

    print("--- Steam清单入库提取工具 ---")
    
    try:
        get_depotdownloader_path() 
    except FileNotFoundError as e:
        print(f"\n致命错误: {e}")
        sys.exit(1)

    username = handle_login(args.account)
    if not username:
        print("\n无法完成登录，脚本已退出。")
        sys.exit(1)
        
    if args.cookies:
        cookie_path = Path(args.cookies)
        if cookie_path.exists():
            print(f"已指定 Cookies 文件: '{cookie_path}'。")
        else:
            print(f"警告: 您指定的 Cookies 文件 '{cookie_path}' 不存在。")

    completed_appids = load_progress()
        
    if args.batch:
        task_file = Path(BATCH)
        if not task_file.exists():
            print(f"错误：批处理模式已启用，但未找到 '{task_file}' 文件。")
            sys.exit(1)

        with open(task_file, 'r', encoding='utf-8') as f:
            appids = [line.strip() for line in f if line.strip()]

        if not appids:
            print(f"'{task_file}' 文件为空或不包含任何 AppID。")
        else:
            print(f"在 '{task_file}' 中找到 {len(appids)} 个 AppID，开始批处理...")
            for appid in appids:
                if not appid.isdigit():
                    print(f"\n警告：跳过无效的 AppID '{appid}'。")
                    continue
                
                if appid in completed_appids:
                    print(f"[跳过] AppID: {appid}")
                    continue

                print(f"\n正在处理 AppID: {appid}")
                
                max_retries = 3
                retry_count = 0
                depot_keys, unavailable_depots = None, None

                while True:
                    depot_keys, unavailable_depots = fetch_data(appid, username)
                    
                    if depot_keys == "RATELIMIT":
                        sys.exit(1)
                    
                    elif depot_keys == "TIMEOUT":
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"\n等待 3 秒后进行第 {retry_count}/{max_retries} 次重试...")
                            time.sleep(3)
                            continue
                        else:
                            print(f"\n连续 {max_retries} 次连接超时/中断，任务已挂起。")
                            user_decision = ""
                            while user_decision not in ['r', 's', 'e']:
                                user_decision = input("等待干预 - [R]重置并重试当前任务 / [S]放弃并跳过该游戏 / [E]退出脚本: ").strip().lower()
                            
                            if user_decision == 'r':
                                retry_count = 0
                                print("\n已重置重试次数，正在重新获取...")
                                continue
                            elif user_decision == 's':
                                print(f"\n已跳过 AppID: {appid}")
                                depot_keys = None
                                break
                            elif user_decision == 'e':
                                print("\n用户终止操作。")
                                sys.exit(1)
                    
                    elif depot_keys == "RELOGIN":
                        print("\n检测到需要重新登录，正在唤起登录流程...")
                        if perform_login(username):
                            print("\n重新登录成功，正在自动重试获取数据...")
                            continue
                        else:
                            print("\n重新登录失败，终止批处理。")
                            sys.exit(1)
                    
                    else:
                        break

                if depot_keys is None:
                    continue 
                
                if isinstance(depot_keys, dict):
                    all_dlc_appids = fetch_dlc_appids(appid, args.cookies)
                    known_depot_ids = set(depot_keys.keys()) | set(unavailable_depots)
                    manifest_less_dlcs = [str(dlc) for dlc in all_dlc_appids if str(dlc) not in known_depot_ids]

                    save_json(appid, depot_keys)
                    organize_manifests(appid)
                    generate_lua(appid, depot_keys, unavailable_depots, manifest_less_dlcs)
                    
                    print(f"正在清理临时文件夹 '{DEPOTS_DIR}'...")
                    shutil.rmtree(DEPOTS_DIR, ignore_errors=True)
                    print(f"\nAppID {appid} 的所有操作已完成。")
                    
                    completed_appids.add(appid)
                    save_progress(completed_appids)

            print("\n所有批处理任务已完成。")
    else:
        while True:
            appid = input("\n请输入要获取的 AppID (输入 'exit' 退出): ").strip()
            if appid.lower() == 'exit':
                break
            if not appid.isdigit():
                print("无效的 AppID，请输入纯数字。")
                continue
            
            if appid in completed_appids:
                user_choice = input(f"AppID {appid} 之前已成功处理过。是否要强制重新处理？(y/n): ").strip().lower()
                if user_choice != 'y':
                    continue

            max_retries = 3
            retry_count = 0
            depot_keys, unavailable_depots = None, None

            while True:
                depot_keys, unavailable_depots = fetch_data(appid, username)
                
                if depot_keys == "RATELIMIT":
                    sys.exit(1)
                
                elif depot_keys == "TIMEOUT":
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"\n等待 3 秒后进行第 {retry_count}/{max_retries} 次重试...")
                        time.sleep(3)
                        continue
                    else:
                        print(f"\n连续 {max_retries} 次连接超时/中断，任务已挂起。")
                        user_decision = ""
                        while user_decision not in ['r', 's', 'e']:
                            user_decision = input(" [R]重置并重试 / [S]跳过该游戏 / [E]退出脚本: ").strip().lower()
                        
                        if user_decision == 'r':
                            retry_count = 0
                            print("\n已重置重试次数，正在重新获取...")
                            continue
                        elif user_decision == 's':
                            print(f"\n已跳过 AppID: {appid}")
                            depot_keys = None
                            break
                        elif user_decision == 'e':
                            print("\n用户终止操作。")
                            sys.exit(1)
                
                elif depot_keys == "RELOGIN":
                    print("\n检测到需要重新登录，正在唤起登录流程...")
                    if perform_login(username):
                        print("\n重新登录成功，正在自动重试获取数据...")
                        continue
                    else:
                        print("\n重新登录失败。")
                        break
                
                else:
                    break

            if depot_keys is None:
                continue
            
            if isinstance(depot_keys, dict):
                all_dlc_appids = fetch_dlc_appids(appid, args.cookies)
                known_depot_ids = set(depot_keys.keys()) | set(unavailable_depots)
                manifest_less_dlcs = [str(dlc) for dlc in all_dlc_appids if str(dlc) not in known_depot_ids]

                save_json(appid, depot_keys)
                organize_manifests(appid)
                generate_lua(appid, depot_keys, unavailable_depots, manifest_less_dlcs)
                
                print(f"正在清理临时文件夹 '{DEPOTS_DIR}'...")
                shutil.rmtree(DEPOTS_DIR, ignore_errors=True)
                print(f"\nAppID {appid} 的所有操作已完成。")
                
                completed_appids.add(appid)
                save_progress(completed_appids)

    print("\n退出。")

if __name__ == "__main__":
    main()