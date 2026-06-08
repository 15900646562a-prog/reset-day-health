# GSC 效果数据接入(Phase 2)— 一次性凭据设置(~10 分钟)

> 做完后系统就能拿到"每个词/每页的曝光·点击",自动喂 ideate 追赢家词 + 填考评效果维度。
> ⚠️ 数据要等 Google 爬:头 1–2 周可能很少,之后慢慢积累。先把凭据建好,数据来了自动点亮。

## 用拥有 GSC 资源的那个 Google 账号做:

1. **Google Cloud Console** → console.cloud.google.com → 新建(或选)一个项目。
2. **启用 API**:左侧「API 和服务」→「库」→ 搜 **"Search Console API"** → 点 **启用**。
3. **建服务账号**:「IAM 和管理」→「服务账号」→「创建服务账号」→ 名字填 `seo-gsc-reader` → 完成。
4. **下载密钥**:点进该服务账号 →「密钥」→「添加密钥」→「创建新密钥」→ 选 **JSON** → 下载那个 .json 文件。
5. **复制服务账号邮箱**(形如 `seo-gsc-reader@<项目>.iam.gserviceaccount.com`)。
6. **在 Search Console 授权它读**:打开 [GSC](https://search.google.com/search-console) → 选资源 `learn.resetday.health` →「设置」→「用户和权限」→「添加用户」→ 粘上面那个服务账号邮箱 → 权限选 **完全 / 受限(只读即可)** → 添加。
7. **把 JSON 给我**:存到
   - 本地:`~/Desktop/seo_factory/content/gsc_creds.json`
   - VPS:`/root/seo_factory/content/gsc_creds.json`
   (文件已 gitignore,不会上传 GitHub。)放好告诉我,我跑 `gsc_fetch` 验证拉通。

## 验证
```bash
python3 src/gsc_fetch.py   # 应打印 "N 词 / M 页 | 曝光 .. 点击 .."(数据少属正常,慢慢长)
```

## 接入后自动发生
- `run_cycle` 每轮先拉 GSC → `ideate` 据"已出曝光的词"扩量(追赢家)。
- 西西周报「效果」维度从 `content/gsc_summary.md` 读真数。
- COO 月度优化诊断有真数据(有曝光无点击→改标题;某词无量→砍)。
