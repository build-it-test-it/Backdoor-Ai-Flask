#!/bin/bash
# Script to properly set up code-server for Backdoor AI

set -e

echo "Setting up code-server for Backdoor AI..."

# Check if code-server is already installed
if command -v code-server &> /dev/null; then
    echo "✅ code-server is already installed at $(which code-server)"
    CODE_SERVER_PATH=$(which code-server)
else
    echo "Installing code-server..."
    
    # Install code-server using the official install script
    curl -fsSL https://code-server.dev/install.sh | sh
    
    # Get the installed path
    CODE_SERVER_PATH=$(which code-server)
    
    if [ -z "$CODE_SERVER_PATH" ]; then
        echo "❌ Failed to install code-server"
        exit 1
    else
        echo "✅ code-server installed at $CODE_SERVER_PATH"
    fi
fi

# Set environment variable for the application to find code-server
export VSCODE_SERVER_PATH="$CODE_SERVER_PATH"
echo "VSCODE_SERVER_PATH=$CODE_SERVER_PATH" >> ~/.bashrc

# Create VS Code directories
VSCODE_BASE_DIR="/tmp/backdoor/vscode"
mkdir -p "$VSCODE_BASE_DIR/workspaces"
mkdir -p "$VSCODE_BASE_DIR/sessions"
mkdir -p "$VSCODE_BASE_DIR/logs"
mkdir -p "$VSCODE_BASE_DIR/extensions"
mkdir -p "$VSCODE_BASE_DIR/user-data"

# Install essential VS Code extensions
echo "Installing essential VS Code extensions..."
EXTENSIONS=(
    "ms-python.python"
    "ms-vscode.cpptools"
    "ms-azuretools.vscode-docker"
    "esbenp.prettier-vscode"
    "dbaeumer.vscode-eslint"
)

for extension in "${EXTENSIONS[@]}"; do
    echo "  - Installing $extension..."
    $CODE_SERVER_PATH --install-extension "$extension" --force &> /dev/null || echo "    Could not install $extension, continuing..."
done

# Configure code-server settings
CONFIG_DIR="$VSCODE_BASE_DIR/user-data/User"
mkdir -p "$CONFIG_DIR"

# Create settings.json with optimal settings
cat > "$CONFIG_DIR/settings.json" << EOL
{
    "workbench.colorTheme": "Default Dark+",
    "workbench.startupEditor": "none",
    "files.autoSave": "afterDelay",
    "files.autoSaveDelay": 1000,
    "editor.formatOnSave": true,
    "editor.formatOnPaste": true,
    "editor.detectIndentation": true,
    "editor.tabSize": 4,
    "editor.rulers": [80, 120],
    "editor.minimap.enabled": true,
    "editor.wordWrap": "on",
    "editor.suggestSelection": "first",
    "explorer.confirmDelete": false,
    "explorer.confirmDragAndDrop": false,
    "terminal.integrated.shell.linux": "/bin/bash",
    "telemetry.telemetryLevel": "off",
    "security.workspace.trust.enabled": false,
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "git.autofetch": true,
    "git.confirmSync": false
}
EOL

# Create keybindings.json
cat > "$CONFIG_DIR/keybindings.json" << EOL
[
    {
        "key": "ctrl+shift+b",
        "command": "workbench.action.tasks.build"
    },
    {
        "key": "ctrl+shift+t",
        "command": "workbench.action.terminal.toggleTerminal"
    }
]
EOL

echo "Testing code-server..."
$CODE_SERVER_PATH --version

echo "✅ code-server setup complete!"
echo "   - binary location: $CODE_SERVER_PATH"
echo "   - data directory: $VSCODE_BASE_DIR"
echo "   - extensions installed: ${#EXTENSIONS[@]}"

# Create a marker file to indicate code-server is installed
echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" > "$VSCODE_BASE_DIR/code-server-initialized"
