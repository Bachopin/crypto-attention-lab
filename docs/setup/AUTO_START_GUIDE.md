# macOS 开机自动启动指南

## 方法一：使用 launchd (推荐)

launchd 是 macOS 的官方服务管理系统，稳定可靠。

### 安装步骤

1. **复制 plist 文件到 LaunchAgents 目录**
   ```bash
   cp scripts/com.bachopin.crypto-attention-lab.plist ~/Library/LaunchAgents/
   ```

2. **加载服务**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.bachopin.crypto-attention-lab.plist
   ```

3. **验证服务已加载**
   ```bash
   launchctl list | grep crypto-attention-lab
   ```

### 管理命令

- **启动服务**：`launchctl start com.bachopin.crypto-attention-lab`
- **停止服务**：`launchctl stop com.bachopin.crypto-attention-lab`
- **卸载服务**：`launchctl unload ~/Library/LaunchAgents/com.bachopin.crypto-attention-lab.plist`
- **查看状态**：`launchctl list | grep crypto-attention-lab`
- **查看日志**：`cat logs/launchd.log` 或 `cat logs/launchd-error.log`

### 注意事项

- plist 文件中的路径必须是**绝对路径**
- 如果项目目录移动了，需要更新 plist 文件中的路径
- 服务会在用户登录后自动启动（不是开机立即启动）
- 如果需要在用户未登录时运行，将 plist 放到 `/Library/LaunchDaemons/`（需要 sudo）

---

## 方法二：使用 crontab @reboot

这是一个更简单的替代方案，但不如 launchd 可靠。

### 安装步骤

1. **编辑 crontab**
   ```bash
   crontab -e
   ```

2. **添加以下行**（按 `i` 进入编辑模式，粘贴后按 `ESC` 然后输入 `:wq` 保存）
   ```cron
   @reboot sleep 30 && cd /Users/mextrel/VSCode/crypto-attention-lab && ./scripts/daemon.sh start
   ```

3. **验证**
   ```bash
   crontab -l
   ```

### 说明
- `sleep 30`：等待 30 秒让系统完全启动
- 开机后会在后台自动执行

---

## 方法三：登录项 (Login Items)

最简单但功能有限的方法。

### 安装步骤

1. 打开 **系统设置** > **通用** > **登录项**
2. 点击 `+` 添加，选择 `scripts/daemon.sh`
3. 如果不显示 .sh 文件，可以创建一个 AppleScript：

   创建 `StartCryptoLab.app`：
   ```applescript
   -- 打开"脚本编辑器" (Script Editor)
   -- 粘贴以下内容：
   do shell script "cd /Users/mextrel/VSCode/crypto-attention-lab && ./scripts/daemon.sh start"
   
   -- 导出为应用程序 (File > Export > File Format: Application)
   ```

4. 将这个 .app 添加到登录项

---

## 推荐配置

**推荐使用方法一 (launchd)**，原因：
- ✅ 官方支持，稳定性最好
- ✅ 可以配置日志输出
- ✅ 支持自动重启（如果进程崩溃）
- ✅ 易于管理和调试

### 完整安装命令（一键执行）

```bash
# 复制 plist
cp /Users/mextrel/VSCode/crypto-attention-lab/scripts/com.bachopin.crypto-attention-lab.plist ~/Library/LaunchAgents/

# 加载服务
launchctl load ~/Library/LaunchAgents/com.bachopin.crypto-attention-lab.plist

# 验证
launchctl list | grep crypto-attention-lab
```

### 测试自动启动

重启电脑后，等待约 1 分钟，然后检查：

```bash
cd /Users/mextrel/VSCode/crypto-attention-lab
./scripts/daemon.sh status
```

应该看到所有服务都在运行。

---

## 故障排查

### 服务没有自动启动

1. **检查 plist 是否加载**
   ```bash
   launchctl list | grep crypto-attention-lab
   ```

2. **查看日志**
   ```bash
   cat logs/launchd-error.log
   ```

3. **手动测试命令**
   ```bash
   /bin/bash -c "cd /Users/mextrel/VSCode/crypto-attention-lab && ./scripts/daemon.sh start"
   ```

4. **检查权限**
   ```bash
   ls -la ~/Library/LaunchAgents/com.bachopin.crypto-attention-lab.plist
   chmod 644 ~/Library/LaunchAgents/com.bachopin.crypto-attention-lab.plist
   ```

### 卸载自动启动

```bash
# 卸载 launchd 服务
launchctl unload ~/Library/LaunchAgents/com.bachopin.crypto-attention-lab.plist
rm ~/Library/LaunchAgents/com.bachopin.crypto-attention-lab.plist

# 或者移除 crontab
crontab -e  # 删除对应的行
```
