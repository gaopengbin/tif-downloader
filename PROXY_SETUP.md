# 代理配置说明

## 问题

如果下载时一直卡住不动，通常是因为无法访问国外地图服务器（Google、OSM 等）。

## 解决方案

### 方法1：配置代理（推荐）

如果你有 VPN 或代理工具（如 Clash、V2Ray 等）：

1. 确保代理工具正在运行
2. 查看代理端口（通常是 7890 或 10809）
3. 编辑 `app/config.py`：
   ```python
   # 修改这一行
   HTTP_PROXY = "http://127.0.0.1:7890"  # 替换为你的代理端口
   ```
4. 重启服务

### 方法2：使用国内镜像图源

添加国内可访问的地图服务：

#### 天地图（推荐）
- 需要申请 Key：https://console.tianditu.gov.cn/
- 免费额度：每日100万次

#### 高德地图
- 需要申请 Key：https://lbs.amap.com/
- 免费额度：每日配额

### 方法3：使用本地瓦片服务器

如果有离线瓦片数据，可以搭建本地 TileServer。

## 测试连接

运行测试脚本检查连接：

```bash
python test_download.py
```

成功输出应该是：
```
Status: 200
Downloaded XXXXX bytes
Saved to test_tile.jpg
```

## 常见代理端口

- Clash: 7890
- V2Ray: 10809
- Shadowsocks: 1080
- HTTP代理: 8080

## 注意事项

⚠️ 使用 Google Maps 等服务需要遵守其服务条款
⚠️ 建议仅用于个人学习和研究
