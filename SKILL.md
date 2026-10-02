---
name: fuji86-gzh-dual-cover
description: 生成微信公众号双封面：先制作2.35比1横版，再参考横版重排1比1方版，精确左右拼合为一张PNG。支持多风格模板、本地记录上次成功使用的模板，并在每次制作时只确认一次是否替换风格。
---

# 公众号双封面

输入主题或文章、标题、副标题和可选风格参考，输出横版、方版与合并图。优先使用内置 imagegen，并遵循可用的 imagegen skill。AI负责插画与构图；本地脚本负责精确尺寸检查和拼合。不打开在线拼接工具，不上传或发布到公众号。

## 输入与一次风格确认

先运行 `scripts/dual_cover.py styles`，读取模板和本地 `state/last-used.json`。状态文件是跨聊天的依据，不能仅靠对话上下文记忆。

每次新制作只确认一次风格，问题为：`是否替换上次风格「<名称>」？`；选项可用「不替换，沿用上次」「换成已有模板」「使用新风格」。用户已经明确说沿用、指定模板或给出新风格时，视为已回答，不再重复确认。等待答复期间可以提取文案，不能默默把未答复当成同意。风格问过后不再发起第二轮风格确认；在同一个问题中说明替换时填写模板名/描述，或另行附参考图。

- 不替换：加载上次成功使用的模板。
- 已有模板：按ID或名称匹配。缺失状态时使用 `mono-sci-fi`，明确这是默认模板，不伪称历史记录。
- 新风格：整理用户描述为风格规则；可使用附件作为参考。运行 `add-style` 留存新模板及参考图，保留所有已有模板。成品验收前不改变上次记录。
- 用户提供的标题、副标题逐字保留，允许换行。仅给主题时可提炼简短封面文案，不能补编事实；已有明确文案不再次确认。

## 固定几何

| 输出 | 尺寸 | 区域 |
|---|---|---|
| 横版 | 1504 × 640 px，2.35:1 | 合并图 x=0至1503 |
| 方版 | 640 × 640 px，1:1 | 合并图 x=1504至2143 |
| 合并图 | 2144 × 640 px，3.35:1 | 横版在左，方版在右 |

两份内容相同，各自包含完整主标题、副标题与同主题插画。两区等高、无额外间隔。带边框模板默认各自外框距上下左右约30px；两份上边框和下边框对齐。其他模板使用自身留白规则，当次指定优先。

## 三步制作

1. **生成横版。** 读取选定模板的 `style.json` 和参考图；本地图像先用 view_image 看图。内置 imagegen 生成横版，提示词列出尺寸、完整文案、排版和当前风格。默认左文右图，主标题醒目；副标题在缩略图中也要可读。参考图只约束风格，替换旧主题、旧文字和旧插画。黑白科幻模板中的AI侧脸、问号仅示范旧选题，不固定到每个主题。
2. **参考横版生成方版。** 验收横版后，以这张横版为参考调用 imagegen 生成单独1:1方版。保持标题、副标题、配色、插画主体和笔触一致，重新排版而不是简单裁切。默认上方标题、中间插画、下方副标题，必要时换行。不要把两个版本一次生成在一张大图上。
3. **精确拼合。** 保存到当前项目 `output/imagegen/<主题或日期>/`。生成尺寸不符时，用 `normalize` 等比缩放和补边，检查新增留白，禁止非等比拉伸。该操作无法解决布局错误或精确边框错误；此时针对失败的版本用 imagegen 调整再检查。两份成图精确达标后运行 `compose`，左右拼合并导出裁切预览和几何报告。

不要每次再把副标题增加20%；此前20%是示例图的一次修正，模板保存最终字号层级。用户改一份时只重做对应版本再合成；横版若改变核心风格或主题，方版同步。

## 验收与状态

- 用 view_image 分别检查横版、方版、合并图：文字无错漏、两版文案一致，无越界或裁切缺损；缩略图文字清楚。
- `compose` 检查尺寸并实际导出PNG。检查两张裁切预览，保证对应区域完整；几何报告不证明视觉合格。
- 不仅凭提示词承诺精确30px。白底黑白版可用 `inspect --ink-bounds` 辅助测量；星点与纹理可能影响检测，结合看图判断。外框不齐时先修复独立版本再合成。
- 三张图验收后运行 `remember` 原子更新上次模板及交付路径。失败、取消、仅添加或浏览模板不更新状态。记录写入失败时交付图片并明确说明未保存，不能宣称已记住。
- 正常调用中的模板与上次选择记录属于本地制作流程，不再额外询问是否记忆；仍遵守用户的实际授权和文件系统权限。
- 展示合并图，提供横版、方版、合并图下载链接，说明模板名称与尺寸。仅在 `remember` 成功后说明已记录。初次交付提醒后台横版选左区、方版选右区；本地检查不代表后台预览验证。

## 本地工具

相对路径以实际skill目录解析。脚本依赖Pillow；优先现有Python。Codex桌面用 `load_workspace_dependencies` 查找带Pillow的Python，不默认安装包或要求API密钥。shell遵循当前环境的命令执行规则。

```bash
python3 <skill>/scripts/dual_cover.py styles
python3 <skill>/scripts/dual_cover.py add-style --id new-style --name 风格名称 --rules-file /path/rules.txt --reference /path/reference.png
python3 <skill>/scripts/dual_cover.py normalize --input /path/generated.png --output /path/horizontal.png --kind horizontal
python3 <skill>/scripts/dual_cover.py normalize --input /path/generated-square.png --output /path/square.png --kind square
python3 <skill>/scripts/dual_cover.py compose --horizontal /path/horizontal.png --square /path/square.png --output /path/dual-cover.png
python3 <skill>/scripts/dual_cover.py inspect --input /path/dual-cover.png --ink-bounds
python3 <skill>/scripts/dual_cover.py remember --style mono-sci-fi --horizontal /path/horizontal.png --square /path/square.png --output /path/dual-cover.png
```

默认状态在skill内 `state/last-used.json`；全局参数 `--state /absolute/path/state.json` 必须放在子命令前，支持显式迁移记录位置。稳定使用同一个路径才能跨聊天延续。命令拒绝覆盖已有成品；默认用版本号，确需替换时显式加 `--overwrite`。保留生成原图。
