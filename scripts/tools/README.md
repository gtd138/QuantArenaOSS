# 工具脚本说明

本目录包含项目的辅助工具脚本。

## 📁 文件列表

### 数据检查工具

#### `check_data.py`
检查数据库中的数据完整性和连续性。

**用法：**
```powershell
python scripts\tools\check_data.py
```

**功能：**
- 查看每个AI的每日资产记录数量
- 检查是否有缺失的日期
- 显示数据统计信息

---

#### `check_session.py`
检查当前session状态和历史session列表。

**用法：**
```powershell
python scripts\tools\check_session.py
```

**功能：**
- 显示当前运行的session ID
- 列出最近5个session
- 检查是否有未完成的session

---

### 数据修复工具

#### `fix_missing_data.py`
修复缺失的每日资产数据（使用前一天的数据填补）。

**用法：**
```powershell
python scripts\tools\fix_missing_data.py
```

**功能：**
- 自动检测缺失的日期
- 使用前一天的资产数据填补
- 验证修复结果

**⚠️  注意：** 
- 仅填补缺失日期，不修改已有数据
- 建议在数据库备份后使用

---

#### `restore_session.py`
恢复session状态，用于断点续跑失效时。

**用法：**
```powershell
python scripts\tools\restore_session.py
```

**功能：**
- 将completed状态的session改为running
- 修正current_date为实际最新日期
- 停止其他运行中的session

**使用场景：**
- 强制停止后重启，发现数据回到初始状态
- session状态被错误标记为completed
- 需要继续之前的运行

**⚠️  注意：**
- 脚本中需要修改`TARGET_SESSION`为要恢复的session ID
- 恢复后需要重启服务才能生效

---

## 🎯 常见场景

### 场景1：检查数据是否完整

```powershell
# 1. 查看session状态
python scripts\tools\check_session.py

# 2. 检查数据完整性
python scripts\tools\check_data.py

# 3. 如果发现缺失，修复数据
python scripts\tools\fix_missing_data.py
```

### 场景2：重启后数据丢失

```powershell
# 1. 检查session状态
python scripts\tools\check_session.py
# 发现创建了新session，旧session是completed状态

# 2. 恢复旧session
python scripts\tools\restore_session.py

# 3. 重启服务
.\start.ps1
```

### 场景3：定期数据检查

```powershell
# 每天运行一次，确保数据连续
python scripts\tools\check_data.py
```

---

## 💡 提示

- 所有工具脚本都在项目根目录运行：`python scripts\tools\xxx.py`
- 建议在操作数据前先查看 `data/backups/` 目录的备份
- 如有疑问，查看 `te_docs/` 目录下的相关文档

---

**最后更新：** 2025-10-28
