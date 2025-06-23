import subprocess
import requests
import re
import os
import chromadb
from chromadb.config import Settings
import hashlib
from pathlib import Path
from typing import List
import time

os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"

BACKEND_URL = "https://win-dos-proxy.vercel.app/api/chat"

INDEXED_EXTENSIONS = {
    '.txt', '.doc', '.docx', '.pdf', '.rtf', '.md',  
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',  
    '.mp4', '.avi', '.mov', '.wmv', '.mp3', '.wav',  
    '.xlsx', '.xls', '.csv', '.ppt', '.pptx'  
}

COMMON_FOLDERS = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Pictures"),
    os.path.expanduser("~/Videos"),
    os.path.expanduser("~/Music"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads")
]

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

def show_banner(): 
    banner = """
     __          ___ _   ____a_            
     \ \        / (_) | |  __ \           
      \ \  /\  / / _| |_| |  | | ___  ___ 
       \ \/  \/ / | | __| |  | |/ _ \/ __|
        \  /\  /  | | |_| |__| | (_) \__ \\
         \/  \/   |_|\__|_____/ \___/|___/
    """
    print(banner)


class FileIndexer:
    def __init__(self, db_path="./chroma_db"):
        self.client = chromadb.PersistentClient(path=db_path)
        
        try:
            self.collection = self.client.get_collection("file_index")
        except:
            self.collection = self.client.create_collection(
                name="file_index",
                metadata={"description": "Windows file system index"}
            )
    
    def generate_file_description(self, file_path: str) -> str:
        path_obj = Path(file_path)
        
        folder_name = path_obj.parent.name
        file_name = path_obj.stem
        extension = path_obj.suffix
        
        description_parts = []
        
        if folder_name.lower() in ['documents', 'pictures', 'videos', 'music', 'desktop', 'downloads']:
            description_parts.append(f"file in {folder_name} folder")
        
        file_type_map = {
            '.txt': 'text document',
            '.doc': 'word document', '.docx': 'word document',
            '.pdf': 'pdf document',
            '.jpg': 'image photo picture', '.jpeg': 'image photo picture', 
            '.png': 'image photo picture', '.gif': 'image photo picture',
            '.mp4': 'video', '.avi': 'video', '.mov': 'video',
            '.mp3': 'audio music', '.wav': 'audio music',
            '.xlsx': 'excel spreadsheet', '.xls': 'excel spreadsheet',
            '.ppt': 'powerpoint presentation', '.pptx': 'powerpoint presentation'
        }
        
        if extension.lower() in file_type_map:
            description_parts.append(file_type_map[extension.lower()])
        
        clean_name = file_name.replace('_', ' ').replace('-', ' ')
        description_parts.append(clean_name)
        
        description_parts.append(f"path: {file_path}")
        
        return " ".join(description_parts)
    
    def index_file(self, file_path: str) -> bool:
        try:
            file_id = hashlib.md5(file_path.encode()).hexdigest()
            
            try:
                existing = self.collection.get(ids=[file_id])
                if existing['ids']:
                    file_mtime = os.path.getmtime(file_path)
                    stored_mtime = existing['metadatas'][0].get('mtime', 0)
                    if file_mtime <= stored_mtime:
                        return True  
            except:
                pass
            
            description = self.generate_file_description(file_path)
            
            metadata = {
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "extension": Path(file_path).suffix.lower(),
                "mtime": os.path.getmtime(file_path),
                "size": os.path.getsize(file_path)
            }
            
            self.collection.upsert(
                documents=[description],
                metadatas=[metadata],
                ids=[file_id]
            )
            
            return True
            
        except Exception as e:
            print(f"Error indexing {file_path}: {e}")
            return False
    
    def index_directory(self, directory: str, max_files: int = 1000) -> int:
        indexed_count = 0
        
        try:
            for root, dirs, files in os.walk(directory):
                if any(skip in root.lower() for skip in ['system32', 'windows', 'program files', '$recycle']):
                    continue
                
                for file in files:
                    if indexed_count >= max_files:
                        break
                        
                    file_path = os.path.join(root, file)
                    
                    if Path(file_path).suffix.lower() in INDEXED_EXTENSIONS:
                        if self.index_file(file_path):
                            indexed_count += 1
                            
                        if indexed_count % 100 == 0:
                            print(f"Indexed {indexed_count} files...")
                            time.sleep(0.1)
                
                if indexed_count >= max_files:
                    break
                    
        except Exception as e:
            print(f"Error indexing directory {directory}: {e}")
        
        return indexed_count
    
    def search_files(self, query: str, n_results: int = 10) -> List[str]:
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            if results['metadatas'] and results['metadatas'][0]:
                file_paths = [metadata['file_path'] for metadata in results['metadatas'][0]]
                return [path for path in file_paths if os.path.exists(path)]
            
            return []
            
        except Exception as e:
            print(f"Error searching files: {e}")
            return []

file_indexer = FileIndexer()

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

def is_file_search_query(user_input: str) -> bool:
    search_indicators = [
        'open any', 'find', 'search for', 'show me', 'files about',
        'pictures of', 'documents about', 'videos of', 'music by'
    ]
    return any(indicator in user_input.lower() for indicator in search_indicators)

def handle_file_search(user_input: str) -> bool:
    print(f"🔍 Searching for files: {user_input}")
    
    matching_files = file_indexer.search_files(user_input, n_results=5)
    
    if not matching_files:
        print("❌ No matching files found.")
        return True
    
    print(f"✅ Found {len(matching_files)} matching files:")
    for i, file_path in enumerate(matching_files, 1):
        print(f"  {i}. {os.path.basename(file_path)}")
    
    try:
        choice = input("\nEnter file numbers to open (e.g., 1,3 or 'all'): ").lower().strip()
        
        if choice == 'all':
            files_to_open = matching_files
        else:
            indices = [int(x.strip()) - 1 for x in choice.split(',')]
            files_to_open = [matching_files[i] for i in indices if 0 <= i < len(matching_files)]
        
        for file_path in files_to_open:
            print(f"📂 Opening: {os.path.basename(file_path)}")
            subprocess.Popen(f'start "" "{file_path}"', shell=True)
        
        return True
        
    except (ValueError, IndexError):
        print("❌ Invalid selection.")
        return True

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

def initialize_index():
    """Initialize the file index on first run"""
    print("🔄 Initializing file index...")
    total_indexed = 0
    
    for folder in COMMON_FOLDERS:
        if os.path.exists(folder):
            print(f"📁 Indexing {folder}...")
            count = file_indexer.index_directory(folder, max_files=200)
            total_indexed += count
    
    print(f"✅ Indexed {total_indexed} files total.")

if __name__ == "__main__":
    show_banner()
    print("🤖 Wit-dos Windows Assistant with File Search (type 'exit' to quit)")
    print("💡 Try: 'open any files about my resume' ")
    
    try:
        collection_count = file_indexer.collection.count()
        if collection_count == 0:
            print("\n🆕 First time setup - building file index...just a moment")
            initialize_index()
    except:
        print("\n🆕 Building file index...")
        initialize_index()

    while True:
        user_input = input("\nWhat can I help you with? ")
        if user_input.lower() == "exit":
            break
        
        if is_file_search_query(user_input):
            handle_file_search(user_input)
        else:
            command = get_smart_command(user_input)
            if command:
                run_command_safely(command)