import os
import time
import random
import json
from datetime import datetime
from urllib.parse import parse_qs
import requests
from colorama import init, Fore, Style


init(autoreset=True)


SETTINGS = {
    "auth_url": "https://tgapi.zoop.com/api/oauth/telegram",
    "spin_url": "https://tgapi.zoop.com/api/users/spin",
    "task_url": "https://tgapi.zoop.com/api/tasks",
    "token_file": "token.txt",  
    "proxy_file": "proxies.txt",
    "retry_wait": 5,  
    "min_spin_delay": 2,  
    "max_spin_delay": 5,  
    "spin_check_time": 300,  
    "daily_check_time": 1800,  
    "switch_account_delay": 10,  
    "headers": {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "Referer": "https://tgapp.zoop.com/",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
}

def log(message, color=Fore.WHITE):
    """Menampilkan log ke console dengan warna."""
    print(f"{color}{message}{Style.RESET_ALL}")

def random_delay(min_time, max_time):
    return random.randint(min_time, max_time)

def read_tokens(file_path):
    """Membaca semua token dari file."""
    try:
        with open(file_path, "r") as file:
            return [line.strip() for line in file if line.strip()]
    except Exception as e:
        log(f"Error reading {file_path}: {e}", Fore.RED)
        raise

def extract_user_id(query):
    try:
        params = parse_qs(query)
        user_data = params.get("user", [None])[0]
        if not user_data:
            raise ValueError("No user data found in query")
        user = json.loads(user_data)
        if "id" not in user:
            raise ValueError("Invalid user data: 'id' not found")
        return user["id"]
    except json.JSONDecodeError as e:
        log(f"Error decoding user data: {e}", Fore.RED)
        raise ValueError("Invalid JSON format in user data")
    except Exception as e:
        log(f"Error extracting user ID: {e}", Fore.RED)
        raise

def get_proxy():
    if not os.path.exists(SETTINGS["proxy_file"]):
        log("Proxy file does not exist. Unable to retrieve proxies.", Fore.YELLOW)
        return None
    proxies = [line.strip() for line in open(SETTINGS["proxy_file"], "r") if line.strip()]
    if not proxies:
        log("Proxy file is empty. No proxies available for use.", Fore.YELLOW)
        return None
    selected_proxy = random.choice(proxies)
    log(f"Selected proxy: {selected_proxy}", Fore.CYAN)
    return selected_proxy

def create_session(proxy=None):
    session = requests.Session()
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
    return session

def fetch_token_and_info(session, query):
    try:
        response = session.post(
            SETTINGS["auth_url"],
            json={"initData": query},
            headers=SETTINGS["headers"]
        )
        response.raise_for_status()
        data = response.json()["data"]
        log("Access token retrieved successfully", Fore.GREEN)
        log(f"User Info: Username: {data['information']['username']} | Points: {data['information']['point']} | Spins: {data['information']['spin']} | IsCheat: {data['information']['isCheat']}", Fore.CYAN)
        return data["access_token"], data["information"]
    except Exception as e:
        log(f"Failed to fetch token: {e}", Fore.RED)
        raise

def check_daily_status(session, token, user_id):
    try:
        response = session.get(
            f"{SETTINGS['task_url']}/{user_id}",
            headers={**SETTINGS["headers"], "authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        task_data = response.json()["data"]
        log(f"Daily Task: Claim Status: {'Claimed' if task_data['claimed'] else 'Not Claimed'} | Claim Date: {task_data['dayClaim']} | Daily Index: {task_data['dailyIndex']}", Fore.CYAN)
        return task_data
    except Exception as e:
        log(f"Failed to check daily status: {e}", Fore.RED)
        raise

def claim_daily_reward(session, token, user_id, index):
    try:
        payload = {"index": index}
        log(f"Initiating daily task claim for Day {index}...", Fore.YELLOW)
        log(f"Payload: {json.dumps(payload)}", Fore.YELLOW)
        response = session.post(
            f"{SETTINGS['task_url']}/rewardDaily/{user_id}",
            json=payload,
            headers={**SETTINGS["headers"], "authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        log("Daily task claimed successfully", Fore.GREEN)
        log(f"Response: {response.json()}", Fore.CYAN)
        return response.json()
    except Exception as e:
        log(f"Failed to claim daily reward: {e}", Fore.RED)
        raise

def spin_wheel(session, token, user_id):
    try:
        delay = random_delay(SETTINGS["min_spin_delay"], SETTINGS["max_spin_delay"])
        log(f"Let the spins begin! | Cooldown: {delay} seconds before first spin", Fore.YELLOW)
        time.sleep(delay)
        response = session.post(
            SETTINGS["spin_url"],
            json={"userId": user_id, "date": datetime.now().isoformat()},
            headers={**SETTINGS["headers"], "authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        reward = response.json()["data"]["circle"]["name"]
        log(f"Spin successful! Reward: {reward}", Fore.GREEN)
        return response.json()
    except Exception as e:
        log(f"Failed to spin: {e}", Fore.RED)
        raise

def retry_operation(func, *args, retries=3, **kwargs):
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == retries - 1:
                log(f"Operation failed after {retries} attempts: {e}", Fore.RED)
                raise
            log(f"Attempt {attempt + 1} failed. Retrying in {SETTINGS['retry_wait']} seconds...", Fore.YELLOW)
            time.sleep(SETTINGS["retry_wait"])

def manage_daily_tasks(session, token, user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    daily_data = retry_operation(check_daily_status, session, token, user_id)
    if daily_data["claimed"]:
        log(f"Daily reward already claimed for {today}.", Fore.YELLOW)
        return
    if daily_data["dayClaim"] != today:
        log(f"Daily reward not available for {today}. Next claim on {daily_data['dayClaim']}.", Fore.YELLOW)
        return
    index = daily_data.get("dailyIndex", 1)
    retry_operation(claim_daily_reward, session, token, user_id, index)
    updated_daily_data = retry_operation(check_daily_status, session, token, user_id)
    if updated_daily_data["claimed"]:
        log("Daily Claim Successful for Day 1", Fore.GREEN)

def use_spins(session, token, user_id, spin_count):
    log(f"Initiating Spin Session: Initial Spins: {spin_count} | Spinning all available spins", Fore.YELLOW)
    for _ in range(spin_count):
        retry_operation(spin_wheel, session, token, user_id)
        spin_count -= 1
        log(f"Spins remaining: {spin_count}", Fore.CYAN)
    
    if spin_count <= 0:
        log("No spins remaining. Waiting for 30 minutes before trying again...", Fore.YELLOW)
        sleeptime = 1800
        for i in range(sleeptime):
            print(f"Menunggu... {sleeptime - i} detik tersisa", end='\r')
            time.sleep(1)
        print()
    log("All spins used.", Fore.GREEN)

def process_account(query):
    """Proses untuk satu akun."""
    log(f"Processing account with token: {query[:10]}...", Fore.CYAN)
    user_id = extract_user_id(query)
    log(f"User ID: {user_id}", Fore.CYAN)
    proxy = get_proxy()
    if proxy is None:
        log("No proxy available for use.", Fore.YELLOW)
    session = create_session(proxy)
    token, info = retry_operation(fetch_token_and_info, session, query)
    spin_count = info["spin"]
    manage_daily_tasks(session, token, user_id)
    token, info = retry_operation(fetch_token_and_info, session, query)
    log(f"Updated User Info: Username: {info['username']} | Points: {info['point']} | Spins: {info['spin']}", Fore.CYAN)
    if spin_count > 0:
        use_spins(session, token, user_id, spin_count)
    log(f"Finished processing account with token: {query[:10]}...", Fore.GREEN)

def start_bot():
    display_banner()  
    try:
        while True:  # Keep the bot running indefinitely
            tokens = read_tokens(SETTINGS["token_file"])  
            for query in tokens:
                process_account(query)
                log(f"Switching to next account in {SETTINGS['switch_account_delay']} seconds...", Fore.YELLOW)
                print()  
                time.sleep(SETTINGS["switch_account_delay"])
                
                # Check if spins are zero after processing the account
                user_id = extract_user_id(query)
                session = create_session(get_proxy())
                token, info = retry_operation(fetch_token_and_info, session, query)
                spin_count = info["spin"]
                if spin_count == 0:
                    log("No spins remaining for this account. Waiting for 30 minutes before trying again...", Fore.YELLOW)
                    sleeptime = 1800
                    for i in range(sleeptime):
                        print(f"Menunggu... {sleeptime - i} detik tersisa", end='\r')
                        time.sleep(1)
                    print()

            log("All accounts processed. Restarting...", Fore.GREEN)
    except KeyboardInterrupt:
        log("\nBot stopped by user. Exiting gracefully...", Fore.YELLOW)
        exit(0)
    except Exception as e:
        log(f"Bot crashed: {e}", Fore.RED)
        log("Restarting in 60 seconds...", Fore.YELLOW)
        time.sleep(60)
        start_bot()


def display_banner():
    """Menampilkan banner saat program dijalankan."""
    print(Fore.GREEN + "[+]===============================[+]")
    print(Fore.GREEN + "[+]      ZOOP BOT AUTOMATION      [+]")
    print(Fore.GREEN + "[+]       @AirdropFamilyIDN       [+]")
    print(Fore.GREEN + "[+]===============================[+]")
    print()

if __name__ == "__main__":
    start_bot()