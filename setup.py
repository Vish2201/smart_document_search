"""Setup script to initialize the Smart Document Q&A System."""

import os
import sys
from pathlib import Path

def print_step(step_num: int, title: str):
    """Print a formatted step."""
    print(f"\n{'='*70}")
    print(f"Step {step_num}: {title}")
    print(f"{'='*70}\n")

def check_python_version():
    """Check Python version."""
    print_step(1, "Checking Python Version")
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("❌ Error: Python 3.10 or higher is required")
        return False
    
    print("✅ Python version is compatible")
    return True

def check_env_file():
    """Check if .env file exists."""
    print_step(2, "Checking Environment Configuration")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("✅ .env file exists")
        
        # Check if OpenAI key is set
        with open(env_file, 'r') as f:
            content = f.read()
            if 'your_openai_api_key_here' in content or 'OPENAI_API_KEY=' not in content:
                print("⚠️  Warning: OpenAI API key not configured in .env")
                print("   Please edit .env and add your API key")
                return False
        
        print("✅ Environment variables configured")
        return True
    else:
        if env_example.exists():
            print("⚠️  .env file not found")
            print("   Creating .env from .env.example...")
            with open(env_example, 'r') as src:
                with open(env_file, 'w') as dst:
                    dst.write(src.read())
            print("✅ Created .env file")
            print("⚠️  Please edit .env and add your OpenAI API key before continuing")
            return False
        else:
            print("❌ Error: .env.example not found")
            return False

def install_dependencies():
    """Install Python dependencies."""
    print_step(3, "Installing Dependencies")
    
    requirements = Path("requirements.txt")
    if not requirements.exists():
        print("❌ Error: requirements.txt not found")
        return False
    
    print("Installing packages from requirements.txt...")
    print("This may take a few minutes...\n")
    
    result = os.system("pip install -r requirements.txt")
    
    if result == 0:
        print("\n✅ Dependencies installed successfully")
        return True
    else:
        print("\n❌ Error installing dependencies")
        return False

def initialize_database():
    """Initialize the database."""
    print_step(4, "Initializing Database")
    
    try:
        from app.database import init_db
        init_db()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

def check_typesense():
    """Check Typesense connection."""
    print_step(5, "Checking Typesense")
    
    try:
        import requests
        response = requests.get("http://localhost:8108/health", timeout=2)
        if response.json().get('ok'):
            print("✅ Typesense is running")
            return True
    except:
        pass
    
    print("⚠️  Typesense is not running")
    print("\nTo start Typesense with Docker:")
    print("docker run -d -p 8108:8108 -v ${PWD}/typesense-data:/data \\")
    print("  typesense/typesense:26.0 --data-dir /data --api-key=xyz --enable-cors")
    print("\nOr see SETUP.md for installation instructions")
    return False

def main():
    """Main setup function."""
    print("\n" + "="*70)
    print("  Smart Document Q&A System - Setup")
    print("="*70)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check environment file
    env_configured = check_env_file()
    
    # Install dependencies
    if not install_dependencies():
        sys.exit(1)
    
    # Initialize database
    if not initialize_database():
        sys.exit(1)
    
    # Check Typesense
    typesense_running = check_typesense()
    
    # Final summary
    print("\n" + "="*70)
    print("  Setup Summary")
    print("="*70 + "\n")
    
    print(f"✅ Python version: OK")
    print(f"{'✅' if env_configured else '⚠️ '} Environment: {'Configured' if env_configured else 'Needs API key'}")
    print(f"✅ Dependencies: Installed")
    print(f"✅ Database: Initialized")
    print(f"{'✅' if typesense_running else '⚠️ '} Typesense: {'Running' if typesense_running else 'Not running'}")
    
    if env_configured and typesense_running:
        print("\n🎉 Setup complete! You're ready to run the application.")
        print("\nTo start the server:")
        print("  uvicorn app.main:app --reload --port 8000")
        print("\nTo run the demo:")
        print("  python demo.py")
    else:
        print("\n⚠️  Setup incomplete. Please address the warnings above.")
        if not env_configured:
            print("   1. Edit .env and add your OpenAI API key")
        if not typesense_running:
            print("   2. Start Typesense (see instructions above)")
        print("\nThen run this setup script again.")

if __name__ == "__main__":
    main()
