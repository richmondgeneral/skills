#!/usr/bin/env python3
"""
Automated Hugging Face Spaces deployment for Gemini Chat
"""
import os
import sys
from pathlib import Path
from huggingface_hub import HfApi, create_repo

def load_env_file():
    """Load environment variables from ~/.env"""
    env_file = Path.home() / ".env"
    if not env_file.exists():
        return
    
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Handle export statements
            if line.startswith('export '):
                line = line[7:]  # Remove 'export '
            # Split on first =
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if value and not os.getenv(key):  # Don't override existing
                    os.environ[key] = value

def deploy_to_hf_spaces():
    """Deploy Gemini Chat to Hugging Face Spaces"""
    
    # Configuration
    SPACE_NAME = "gemini-chat"
    SPACE_SDK = "gradio"
    DEPLOY_DIR = Path(__file__).parent
    
    print("🚀 Deploying Gemini Chat to Hugging Face Spaces")
    print("=" * 60)
    
    # Load .env file
    load_env_file()
    
    # Step 1: Check for HF token
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("❌ Error: HF_TOKEN environment variable not set")
        print("\nTo get your token:")
        print("1. Go to https://huggingface.co/settings/tokens")
        print("2. Create a new token with 'write' access")
        print("3. Add to ~/.env: export HF_TOKEN='your_token_here'")
        print("\nThen run this script again.")
        return False
    
    # Step 2: Initialize HF API
    print("\n📡 Connecting to Hugging Face...")
    api = HfApi(token=hf_token)
    
    # Get username
    try:
        user_info = api.whoami()
        username = user_info['name']
        print(f"✓ Authenticated as: {username}")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        return False
    
    repo_id = f"{username}/{SPACE_NAME}"
    
    # Step 3: Create Space
    print(f"\n🏗️  Creating Space: {repo_id}...")
    try:
        create_repo(
            repo_id=repo_id,
            repo_type="space",
            space_sdk=SPACE_SDK,
            private=False,
            exist_ok=True,
            token=hf_token
        )
        print("✓ Space created (or already exists)")
    except Exception as e:
        print(f"❌ Failed to create Space: {e}")
        return False
    
    # Step 4: Upload files
    print(f"\n📦 Uploading files from {DEPLOY_DIR}...")
    
    files_to_upload = {
        "app.py": "app.py",
        "requirements.txt": "requirements.txt",
        "HF_README.md": "README.md",
        "router.py": "router.py",
    }
    
    try:
        # Upload individual files
        for local_name, remote_name in files_to_upload.items():
            local_path = DEPLOY_DIR / local_name
            if local_path.exists():
                print(f"  ↑ {local_name} → {remote_name}")
                api.upload_file(
                    path_or_fileobj=str(local_path),
                    path_in_repo=remote_name,
                    repo_id=repo_id,
                    repo_type="space",
                    token=hf_token
                )
            else:
                print(f"  ⚠️  {local_name} not found, skipping")
        
        # Upload models directory
        models_dir = DEPLOY_DIR / "models"
        if models_dir.exists():
            print(f"  ↑ models/ directory")
            api.upload_folder(
                folder_path=str(models_dir),
                path_in_repo="models",
                repo_id=repo_id,
                repo_type="space",
                token=hf_token
            )
        else:
            print(f"  ⚠️  models/ directory not found")
        
        print("✓ All files uploaded")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False
    
    # Step 5: Configure Space secrets
    print("\n🔐 Configuring Space secrets...")
    
    secrets_to_add = {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "REMOVE_BG_API_KEY": os.getenv("REMOVEBG_API_KEY"),
    }
    
    secrets_added = 0
    for secret_name, secret_value in secrets_to_add.items():
        if secret_value:
            try:
                api.add_space_secret(
                    repo_id=repo_id,
                    key=secret_name,
                    value=secret_value,
                    token=hf_token
                )
                print(f"  ✅ {secret_name} configured")
                secrets_added += 1
            except Exception as e:
                print(f"  ⚠️  {secret_name} failed: {e}")
        else:
            print(f"  ⏭️  {secret_name} not found in .env")
    
    # Step 6: Display results
    space_url = f"https://huggingface.co/spaces/{repo_id}"
    print("\n" + "=" * 60)
    print("✅ Deployment complete!")
    print(f"\n🌐 Your Space: {space_url}")
    print(f"\n🔐 Secrets configured: {secrets_added}/{len(secrets_to_add)}")
    print("\n⏳ Next steps:")
    print("1. Wait 2-3 minutes for Space to build")
    print(f"2. Visit {space_url} to test!")
    print("3. Check build logs if needed (click 'Logs' tab)")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = deploy_to_hf_spaces()
    sys.exit(0 if success else 1)
