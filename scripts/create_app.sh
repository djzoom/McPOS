#!/bin/bash
# 创建 Kat Records 应用程序包

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_NAME="Kat Records"
APP_PATH="$PROJECT_ROOT/${APP_NAME}.app"

echo "📦 创建应用程序包: $APP_PATH"

# 创建目录结构
mkdir -p "${APP_PATH}/Contents/MacOS"
mkdir -p "${APP_PATH}/Contents/Resources"

# 复制启动脚本
# 创建可执行文件名（使用ASCII安全的名称）
EXECUTABLE_NAME="KatRecords"
cat > "${APP_PATH}/Contents/MacOS/${EXECUTABLE_NAME}" << 'EOFSCRIPT'
#!/bin/bash
# KAT Records Studio 终端启动脚本

# 获取.app包的位置
APP_BUNDLE="$(cd "$(dirname "$0")/../../.." && pwd)"
WORK_DIR="$(dirname "$APP_BUNDLE")"

# 查找项目目录
PROJECT_DIR=""
for dir in "$WORK_DIR/Kat_Rec" "$HOME/Downloads/Kat_Rec" "$HOME/Kat_Rec"; do
    if [ -d "$dir" ]; then
        PROJECT_DIR="$dir"
        break
    fi
done

if [ -z "$PROJECT_DIR" ]; then
    osascript -e 'display dialog "无法找到项目目录。\n\n请确保项目在以下位置之一：\n• ~/Downloads/Kat_Rec\n• ~/Kat_Rec\n• 与应用程序同一目录" buttons {"确定"} default button "确定" with icon stop'
    exit 1
fi

# 转义特殊字符以便在AppleScript中使用
PROJECT_DIR_ESC=$(echo "$PROJECT_DIR" | sed "s/'/'\''/g")

# 构建启动命令
LAUNCH_CMD="cd '$PROJECT_DIR_ESC' && if [ ! -d '.venv' ]; then echo '正在初始化环境...'; python3 -m venv .venv && .venv/bin/pip install -q -U pip && .venv/bin/pip install -q -r requirements.txt; fi && .venv/bin/python3 scripts/kat_terminal.py"

# 在Terminal.app中打开新窗口并执行，同时设置等宽字体
osascript << APPLESCRIPT
tell application "Terminal"
    activate
    set newWindow to do script "$LAUNCH_CMD"
    set custom title of newWindow to "Kat Records"
    
    -- 设置字体为等宽字体（SF Mono优先，fallback到Menlo）
    try
        set font name of current settings of newWindow to "SF Mono"
        set font size of current settings of newWindow to 12
    on error
        try
            set font name of current settings of newWindow to "Menlo"
            set font size of current settings of newWindow to 12
        on error
            try
                set font name of current settings of newWindow to "Monaco"
                set font size of current settings of newWindow to 12
            end try
        end try
    end try
end tell
APPLESCRIPT
EOFSCRIPT

chmod +x "${APP_PATH}/Contents/MacOS/${EXECUTABLE_NAME}"

# 创建 Info.plist
cat > "${APP_PATH}/Contents/Info.plist" << 'EOFPLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>zh_CN</string>
    <key>CFBundleExecutable</key>
    <string>KatRecords</string>
    <key>CFBundleIdentifier</key>
    <string>com.katrecords.terminal</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Kat Records</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2025 Kat Records</string>
</dict>
</plist>
EOFPLIST

echo "✅ 应用程序包创建完成！"
echo ""
echo "📁 位置: $APP_PATH"
echo ""
echo "💡 使用方法："
echo "   1. 双击 '$APP_NAME.app' 即可启动"
echo "   2. 可以拖拽到应用程序文件夹"
echo "   3. 可以添加到 Dock"

