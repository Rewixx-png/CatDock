import os
import re
import sys
import argparse
from typing import Tuple, List, Pattern

# --- CONFIGURATION ---

IGNORE_DIRS = {
    '.git', '.idea', '.vscode', '__pycache__', 'venv', 'env', 
    'node_modules', 'dist', 'build', 'migrations', 'alembic/versions',
    'web/dist', 'storage', 'logs', 'assets', 'public', '.pytest_cache'
}

IGNORE_FILES = {
    'requirements.txt', 'package-lock.json', 'yarn.lock', 'ALEMBIC_README',
    'README.md', 'LICENSE', 'VERSION', 'alembic.ini', 'Cleaner.py', 'smart_cleaner.py'
}

EXT_MAP = {
    '.py': 'python',
    '.sh': 'shell',
    '.yaml': 'shell', '.yml': 'shell', '.toml': 'shell', '.ini': 'shell', '.conf': 'shell',
    '.js': 'c_style', '.ts': 'c_style', '.json': 'c_style', '.css': 'c_style', '.scss': 'c_style',
    '.html': 'html', '.xml': 'html',
    '.vue': 'vue'
}

# --- REGEX PATTERNS (FIXED) ---

# Python: Исправлено экранирование решетки (\#) для режима VERBOSE
PAT_PYTHON = re.compile(
    r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(\#.*)',
    re.VERBOSE | re.MULTILINE
)

# C-Style
PAT_C_STYLE = re.compile(
    r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)|(//.*|/\*[\s\S]*?\*/)',
    re.VERBOSE | re.MULTILINE
)

# Shell: Исправлено экранирование решетки (\#)
PAT_SHELL = re.compile(
    r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(\#.*)',
    re.VERBOSE | re.MULTILINE
)

# HTML
PAT_HTML = re.compile(
    r'(<[^>]*>)|(<!--[\s\S]*?-->)',
    re.VERBOSE | re.MULTILINE
)

# Vue
PAT_VUE = re.compile(
    r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)|(<!--[\s\S]*?-->|/\*[\s\S]*?\*/|//.*)',
    re.VERBOSE | re.MULTILINE
)

# --- COLORS ---
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def get_cleaner_pattern(mode: str) -> Pattern:
    if mode == 'python': return PAT_PYTHON
    if mode == 'c_style': return PAT_C_STYLE
    if mode == 'shell': return PAT_SHELL
    if mode == 'html': return PAT_HTML
    if mode == 'vue': return PAT_VUE
    return None

def is_special_comment(comment: str) -> bool:
    if not comment: return False
    c = comment.strip()
    if c.startswith('#!') or c.startswith('// #!'): return True
    if 'coding:' in c or 'encoding:' in c: return True
    if 'vim:' in c: return True
    return False

def clean_text(text: str, mode: str) -> str:
    pattern = get_cleaner_pattern(mode)
    if not pattern:
        return text

    def replacer(match):
        if match.group(1):
            return match.group(1)
        
        if match.group(2):
            comment_content = match.group(2)
            if is_special_comment(comment_content):
                return comment_content
            return ""
        
        return match.group(0)

    cleaned = pattern.sub(replacer, text)
    return cleaned

def remove_excess_newlines(text: str) -> str:
    return re.sub(r'\n\s*\n\s*\n', '\n\n', text)

def process_file(file_path: str, dry_run: bool) -> Tuple[bool, int, int]:
    ext = os.path.splitext(file_path)[1].lower()
    mode = EXT_MAP.get(ext)
    
    if not mode:
        return False, 0, 0

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except UnicodeDecodeError:
        return False, 0, 0
    except Exception as e:
        print(f"{Colors.FAIL}❌ Error reading {file_path}: {e}{Colors.ENDC}")
        return False, 0, 0

    content_no_comments = clean_text(original_content, mode)
    final_content = remove_excess_newlines(content_no_comments).strip() + "\n"

    orig_size = len(original_content)
    new_size = len(final_content)
    
    if orig_size == new_size and original_content == final_content:
        return False, orig_size, new_size

    if new_size < 10 and orig_size > 100:
        print(f"{Colors.FAIL}🚨 SAFETY TRIGGER: File {file_path} became too small! Skipping.{Colors.ENDC}")
        return False, orig_size, orig_size

    if not dry_run:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
        except Exception as e:
            print(f"{Colors.FAIL}❌ Error writing {file_path}: {e}{Colors.ENDC}")
            return False, orig_size, new_size

    return True, orig_size, new_size

def main():
    parser = argparse.ArgumentParser(description="Smart Code Sanitizer")
    parser.add_argument("--apply", action="store_true", help="Apply changes (WRITE to disk)")
    parser.add_argument("--path", type=str, default=".", help="Root directory")
    
    args = parser.parse_args()
    root_dir = args.path
    dry_run = not args.apply

    print(f"{Colors.HEADER}{Colors.BOLD}🚀 STARTING SMART SANITIZER v2.1 (Fixed Regex){Colors.ENDC}")
    if dry_run:
        print(f"{Colors.WARNING}🔧 Mode: DRY RUN (No changes will be saved){Colors.ENDC}")
        print(f"ℹ️  To apply changes, run: python3 Cleaner.py --apply")
    else:
        print(f"{Colors.OKGREEN}🔧 Mode: APPLY (Writing changes to disk){Colors.ENDC}")
    
    print("-" * 50)

    total_files = 0
    cleaned_files = 0
    bytes_saved = 0

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
        
        for file in files:
            if file in IGNORE_FILES or file.startswith('.'):
                continue
            
            file_path = os.path.join(root, file)
            changed, o_len, n_len = process_file(file_path, dry_run)
            
            total_files += 1
            if changed:
                cleaned_files += 1
                saved = o_len - n_len
                bytes_saved += saved
                percent = ((o_len - n_len) / o_len) * 100 if o_len > 0 else 0
                
                print(f"{Colors.OKBLUE}CLEANED:{Colors.ENDC} {file_path} "
                      f"{Colors.DIM}({o_len} -> {n_len} bytes, -{percent:.1f}%){Colors.ENDC}")

    print("-" * 50)
    print(f"{Colors.BOLD}🏁 SCAN COMPLETE{Colors.ENDC}")
    print(f"📄 Files scanned: {total_files}")
    print(f"✨ Files to clean: {cleaned_files}")
    print(f"💾 Space saver:   {bytes_saved / 1024:.2f} KB")

if __name__ == "__main__":
    main()
