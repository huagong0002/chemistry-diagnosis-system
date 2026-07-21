@echo off
chcp 65001 >nul
title 打包项目 - 生成分享压缩包

echo ============================================
echo   化学错题智能诊断系统 - 打包工具
echo ============================================
echo.

:: 检查是否安装了打包工具
python -c "import shutil" >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Python未安装
    pause
    exit
)

:: 设置打包目录名
set PACKAGE_NAME=化学错题智能诊断系统_v1.0
set PACKAGE_DIR=%TEMP%\%PACKAGE_NAME%

echo [1/3] 准备打包文件...
echo.

:: 创建临时目录
if exist "%PACKAGE_DIR%" rmdir /s /q "%PACKAGE_DIR%"
mkdir "%PACKAGE_DIR%"

:: 复制核心文件
echo 复制核心代码...
copy /y "app.py" "%PACKAGE_DIR%\" >nul
copy /y "ai_service.py" "%PACKAGE_DIR%\" >nul
copy /y "database.py" "%PACKAGE_DIR%\" >nul
copy /y "models.py" "%PACKAGE_DIR%\" >nul
copy /y "config.py" "%PACKAGE_DIR%\" >nul
copy /y "config_manager.py" "%PACKAGE_DIR%\" >nul
copy /y "init_data.py" "%PACKAGE_DIR%\" >nul
copy /y "requirements.txt" "%PACKAGE_DIR%\" >nul
copy /y "README.md" "%PACKAGE_DIR%\" >nul

:: 复制启动脚本
echo 复制启动脚本...
copy /y "启动系统.bat" "%PACKAGE_DIR%\" >nul
copy /y "安装环境.bat" "%PACKAGE_DIR%\" >nul

:: 复制文档
echo 复制使用文档...
mkdir "%PACKAGE_DIR%\使用文档"
copy /y "部署指南.md" "%PACKAGE_DIR%\使用文档\" >nul
copy /y "使用手册.md" "%PACKAGE_DIR%\使用文档\" >nul

:: 复制参赛材料
if exist "参赛材料" (
    echo 复制参赛材料...
    xcopy "参赛材料" "%PACKAGE_DIR%\参赛材料\" /E /I /Y >nul
)

:: 创建data目录
mkdir "%PACKAGE_DIR%\data"

:: 创建空配置文件
echo {} > "%PACKAGE_DIR%\data\user_config.json"

echo.
echo [2/3] 创建压缩包...
echo.

:: 使用PowerShell压缩
powershell -Command "Compress-Archive -Path '%PACKAGE_DIR%\*' -DestinationPath '%USERPROFILE%\Desktop\%PACKAGE_NAME%.zip' -Force"

echo.
echo [3/3] 清理临时文件...
rmdir /s /q "%PACKAGE_DIR%"

echo.
echo ============================================
echo   打包完成！
echo.
echo   压缩包位置：
echo   %USERPROFILE%\Desktop\%PACKAGE_NAME%.zip
echo.
echo   请将此压缩包发送给其他教师
echo ============================================
echo.
pause
