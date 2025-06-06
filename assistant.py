import subprocess
import requests
import os
import re
from dotenv import load_dotenv


MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

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
    system_prompt = """
You are a helpful Windows AI assistant that translates natural language into valid Windows shell commands.
You must ONLY respond with the exact command to execute. 

Examples:
- "open the camera" -> start microsoft.windows.camera:
- "open calculator" -> start calc
- "launch Notion" -> start notion
- "open vscode" -> start code
- "show my pictures folder" -> start "" "%USERPROFILE%\\Pictures"
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    response = requests.post(
        "https://win-dos-proxy.vercel.app/api/chat",
        json={
            "model": MODEL,
            "messages": messages,
            "temperature": 0.2
        }
    )

    if response.status_code == 200:
        cmd = response.json()["choices"][0]["message"]["content"].strip()
        return cmd
    else:
        print("[Error from Groq API]:", response.text)
        return None

def run_command_safely(command):
    try:
        # dangerous
        if is_blocked(command):
            print(f"❌ BLOCKED: {command}")
            print("This command is not allowed for security reasons.")
            return
        
        # Safe
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