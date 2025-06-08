import subprocess
import requests
import re

BACKEND_URL = "https://win-dos-proxy.vercel.app/api/chat"

BLOCKED_PATTERNS = [
    r'del\s+.*\\(Windows|System32)',
    r'format\s+[A-Za-z]:',
    r'shutdown\s+',
    r'reg\s+delete.*HKEY_LOCAL_MACHINE',
    r'bcdedit',
    r'diskpart'
]

SAFE_PATTERNS = [
    r'^start\s+',
    r'^explorer\s+',
    r'^dir\s',
    r'^cd\s',
    r'^type\s',
    r'^echo\s',
    r'^cls$',
    r'^ping\s',
    r'^ipconfig'
]

def is_blocked(command):
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command.lower()):
            return True
    return False

def is_safe(command):
    for pattern in SAFE_PATTERNS:
        if re.match(pattern, command.lower()):
            return True
    return False

def get_smart_command(user_input):
    try:
        response = requests.post(
            BACKEND_URL,
            json={"prompt": user_input},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            print("[❌ LLM Error]:", response.text)
            return None
    except requests.RequestException as e:
        print("[❌ Request failed]:", e)
        return None

def run_command_safely(command):
    try:
        if is_blocked(command):
            print(f"❌ BLOCKED: {command}")
            print("This command is not allowed for security reasons.")
            return

        if is_safe(command):
            print(f"✅ [EXECUTING]: {command}")
            subprocess.Popen(command, shell=True)
            return

        print(f"\n⚠️ Confirmation needed for: {command}")
        confirm = input("Continue? (y/n): ").lower()
        if confirm in ['y', 'yes']:
            print(f"[EXECUTING]: {command}")
            subprocess.Popen(command, shell=True)
        else:
            print("❌ Cancelled")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🤖 AI Windows Assistant (type 'exit' to quit)")

    while True:
        user_input = input("\nWhat can I help you with? ")
        if user_input.lower() == "exit":
            break

        command = get_smart_command(user_input)
        if command:
            run_command_safely(command)
