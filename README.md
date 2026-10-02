# fuji86-gzh-dual-cover

面向 Codex 的微信公众号双封面 Skill。输入文章主题或封面文案，先生成横版，再参考横版重新构图生成方版，最后在本地拼合为一张可上传的 PNG。

本项目将视觉生成与图像处理分开：生成工具负责插画、文字与构图，Python 脚本负责尺寸检查、无拉伸缩放、左右拼接和风格状态保存。

![双封面示例](docs/dual-cover-example.png)

## 为什么要制作双封面

公众号封面编辑器提供横版与方版两种裁切区域。直接把横版裁成方版，容易丢失标题、副标题或主体。

本项目在同一张图片中保留两份独立构图：左侧用于横版裁切，右侧用于方版裁切。两份内容一致，但分别排版，使每种裁切都能包含完整信息。

| 输出 | 尺寸 | 比例 | 在合并图中的位置 |
| --- | --- | --- | --- |
| 横版封面 | 1504 × 640 px | 2.35:1 | 左侧，`x ∈ [0, 1504)` |
| 方版封面 | 640 × 640 px | 1:1 | 右侧，`x ∈ [1504, 2144)` |
| 合并封面 | 2144 × 640 px | 3.35:1 | 完整画布 |

```text
┌────────────────────────────────────┬────────────────┐
│                                    │                │
│       横版：1504 × 640              │ 方版：640 × 640 │
│                                    │                │
└────────────────────────────────────┴────────────────┘
                合并图：2144 × 640
```

## 工作流程

1. **生成横版。** 根据主题、完整文案和选定风格制作 2.35:1 封面，检查标题、插画和信息层级。
2. **生成方版。** 以已验收的横版为参考，保持视觉语言与文案一致，重新安排 1:1 构图。方版独立生成，不通过截取横版获得。
3. **拼合导出。** 两份成图达到目标尺寸后，本地脚本将其无间隔拼合，导出 PNG、两个裁切预览和几何报告。

风格在一次制作中只确认一次。明确指定模板或说“沿用上次”时，直接执行；未指定时，询问是否替换上次风格。新风格可以保存为模板，成功交付后更新最近使用记录。

## 环境要求

- Codex 或能够读取 `SKILL.md` 的 Agent 环境。
- 可用的图像生成与参考图编辑工具。默认流程使用 Codex 内置 imagegen；Python 脚本本身不调用生成模型。
- Python 3.10 或更高版本，以及 Pillow。

默认使用内置生成工具时，本项目不要求配置额外的图像 API Key。生成服务的可用性和使用额度取决于所在环境。

## 安装

将仓库放入 Codex 的用户 Skill 目录：

```bash
git clone https://github.com/fuji-robot86/fuji86-gzh-dual-cover.git \
  ~/.codex/skills/fuji86-gzh-dual-cover
```

私有仓库需要先登录具有访问权限的 GitHub 账号。目标目录已存在时，应先检查现有文件及本地模板，避免覆盖个人配置。

如果当前 Python 尚未提供 Pillow，可以创建隔离环境：

```bash
cd ~/.codex/skills/fuji86-gzh-dual-cover
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

在 Codex 中调用时，Agent 应选择已经包含 Pillow 的 Python。Codex 桌面环境也可通过 `load_workspace_dependencies` 查找已有运行时，无需重复安装。

## 调用示例

仅提供主题：

```text
使用 $fuji86-gzh-dual-cover，主题：AI也有自己的怪癖，
一个符号就能改变AI的理解方式。
```

沿用上次风格，并固定文案：

```text
使用 $fuji86-gzh-dual-cover，沿用上次风格。
主标题：AI也有自己的怪癖
副标题：一个符号，改变 AI 的理解方式
```

指定新风格：

```text
使用 $fuji86-gzh-dual-cover，按我附上的参考图替换风格，
并保存为“极简几何”。保持标题和副标题原文不变。
```

正常交付包含横版、方版和合并图。上传合并图后，在公众号封面编辑器中分别将横版裁切框对准左区、方版裁切框对准右区，以后台实际预览为准。

## 风格模板

每个模板独立存放在 `templates/<style-id>/`，由风格描述和可选参考图组成。内置 `mono-sci-fi` 模板使用白底、统一黑色文字、切角双线边框与科幻线稿。

该模板带边框时，默认四周约 30px 留白，上下边框对齐。参考图中的 AI 侧脸、问号和轨道属于示例主题；生成新选题时应替换对应主体。

模板描述只约束风格，不冻结文案或插画内容。新增模板不覆盖已有模板，也不会立即改变最近使用记录。

```bash
python3 scripts/dual_cover.py add-style \
  --id minimal-geometric \
  --name 极简几何 \
  --rules-file ./style-rules.txt \
  --reference ./reference.png
```

`--reference` 可重复传入；没有参考图时也可以只保存文字规则。`style-rules.txt` 是用户提供的 UTF-8 风格描述文件。

## 最近使用记录

默认状态文件为 `state/last-used.json`，保存最近成功使用的模板和交付路径。该文件不进入版本控制，第一次使用时回退到内置模板。

- 只有成品完成视觉检查后才执行 `remember`。
- 生成失败、取消制作或只添加模板时，保留上次记录。
- `remember` 会检查尺寸、PNG 格式及合并图是否与两份输入一致，再原子写入状态。
- 换聊天后读取同一个状态文件即可恢复模板选择，无需依赖聊天上下文。

如需将记录放到独立位置，使用全局参数；它必须出现在子命令之前：

```bash
python3 scripts/dual_cover.py --state /path/to/last-used.json styles
```

多个进程共用状态时，以最后一次成功写入为准。建议同一条制作流程串行执行，不并发修改同一份记录。

## 本地 CLI

以下命令处理已经生成的图片；它们不负责模型推理。示例路径需替换为实际文件位置。

查看模板和最近使用记录：

```bash
python3 scripts/dual_cover.py styles
```

将非标准尺寸图片等比缩放并补边到目标画布：

```bash
python3 scripts/dual_cover.py normalize \
  --input ./generated-landscape.png \
  --output ./horizontal.png \
  --kind horizontal

python3 scripts/dual_cover.py normalize \
  --input ./generated-square.png \
  --output ./square.png \
  --kind square
```

拼合两份标准尺寸封面：

```bash
python3 scripts/dual_cover.py compose \
  --horizontal ./horizontal.png \
  --square ./square.png \
  --output ./dual-cover.png
```

输出文件：

```text
dual-cover.png                  合并封面
dual-cover-horizontal.png       左侧裁切预览
dual-cover-square.png           右侧裁切预览
dual-cover-geometry.json        尺寸与区域报告
```

检查图片，并在人工验收通过后记录风格：

```bash
python3 scripts/dual_cover.py inspect --input ./dual-cover.png --ink-bounds

python3 scripts/dual_cover.py remember \
  --style mono-sci-fi \
  --horizontal ./horizontal.png \
  --square ./square.png \
  --output ./dual-cover.png
```

输出默认拒绝覆盖；修改时使用带版本号的文件名，或者明确传入 `--overwrite`。透明输入会合成到背景色上，默认白色，可通过 `--background` 指定其他颜色。

## 验收与边界

脚本能够保证画布尺寸、拼合边界和输出格式，不能判断文字是否有错字、风格是否一致或视觉是否好看。这些检查由 Agent 看图完成，上传后的显示效果仍需在公众号后台确认。

`normalize` 只执行等比缩放和补边，不拉伸、不自动裁掉内容。因此，当生成图比例偏差较大时，会出现额外留白；应重新调整构图，而不是直接认定结果符合边框要求。

`inspect --ink-bounds` 测量的是深色像素外接范围，适用于白底黑白图。星点、纹理和游离装饰会影响结果，它不能替代边框与视觉检查。30px 边距是模板目标，并非生成模型的像素级承诺。

本项目不提供公众号登录、上传或发布功能。

## 开发与测试

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s tests -v
```

测试覆盖拼合边界、错误尺寸拒绝、已有输出保护、等比补边、模板保存和状态更新失败时的行为，不调用生成服务。GitHub Actions 使用 Python 3.10 与 3.12 运行这些检查。

```text
.
├── SKILL.md                      Agent 制作规则
├── agents/openai.yaml            Codex 展示与调用信息
├── scripts/dual_cover.py          图像处理与模板状态 CLI
├── templates/mono-sci-fi/         内置风格与参考图
├── docs/dual-cover-example.png    双封面示例
├── tests/test_dual_cover.py       CLI 回归测试
├── requirements.txt              Python 依赖
└── state/                        运行时创建，不进入 Git
```
