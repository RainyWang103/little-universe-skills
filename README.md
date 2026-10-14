# little-universe-skills
Little Universe Skill repository

## 内容与规则来源

这是团队共用的公开 ChatGPT Skills Monorepo。当前包含：

- [Travel Planner](skills/travel-planner/SKILL.md)：两人艺术、文化、美食旅行规划。
- [手绘海报](skills/hand-drawn-poster/SKILL.md)：一张照片生成 3:4 编辑海报，
  上半摄影、下半极简纸本手绘，各占 50%，默认无文字。
  触发词为“手绘”“极简手绘”“手绘图”“手绘海报”；明确调用后仅需上传图片。
  运行需宿主参考图生成工具及 Python/Pillow，拼接依赖见该 Skill 的 `requirements.txt`。
  照片和输出不提交到公开仓库；独立包不代表已注册或安装到 ChatGPT。
- [Travel Architecture Deep Guide](skills/travel-architecture-deep-guide/SKILL.md)：对建筑、历史街区、博物馆或人文遗产做
  资深建筑史／艺术史级深度讲解；强制六段结构；事实须核实。
  用于讲透一座建筑、结构与风格分析、参观动线与细看要点。

Travel Planner 的
入口按执行阶段导航至六份详细参考；参考逐段保留本次权威实施文件第 2–7 节，
不假设可以访问 Project Instructions、历史对话或未提供的私人材料。

公开仓库只保存通用规则和代码。真实订单、身份信息、凭证、私人行程及内部链接
不得提交；私人旅行文件优先保存到 ChatGPT Library 共享文件夹 `Our Travels`，
访问失败须说明并提供手动上传文件，不能假称保存成功或擅自换目的地。

## 本地验证与构建

需要 Python 3.12（CI 使用版本）和固定版本的 PyYAML：

```bash
python -m pip install -r requirements-dev.txt
python scripts/validate-skills.py
python -m unittest discover -s tests -v
python scripts/package-skills.py --sha "$(git rev-parse HEAD)" --output dist
```

验证器检查全部 Skill 目录、frontmatter（仅 `name` 和 `description`）、
目录与名称一致性、UI metadata、引用存在且不越界、明显占位、符号链接以及
仓库结构和 Actions YAML 可解析性。失败返回非零。脚本测试覆盖成功输入、
各种失败输入及退出码、多 Skill 独立打包、字节一致性、可复现性、SHA 和大小上限。
静态校验不能证明旅行动态事实已核实，也不能自动发现所有私人资料；PR 必须人工审查公开内容。

每个 Skill 构建一个 `dist/<name>-<full-commit-sha>.zip`，顶层只有对应 Skill 根目录：

```text
travel-planner/
  SKILL.md
  agents/openai.yaml
  references/*.md
```

不包含整个 monorepo。压缩及解压后内容均限制在 25 MB 内（上限 25,000,000 bytes），
逐项检查 ZIP 路径、CRC 和内容一致性。`build-<sha>.json` 记录完整 SHA、成员列表、
包大小和 SHA-256。ZIP 使用固定时间戳，可复现；构建输出不提交 Git。

## CI 与下载边界

- `validate.yml` 在 PR 和 push 上验证、执行正反测试并试构建；job 显示名为 `validate-skills`。
- `publish.yml` 仅在 main push 后运行，先验证和测试，再生成独立 ZIP 及 SHA 元数据，
  上传到 Actions Artifact `skills-<sha>`，保留 30 天。
- 从仓库 **Actions → Package Skills → 对应 main commit 的成功 run → Artifacts** 下载。
  Artifact 下载外层容器内包含可独立上传的 Skill ZIP 和构建元数据。
- Artifact 是下载包，不代表已安装 ChatGPT。仅在目标 ChatGPT 产品确实提供 Skill 导入能力时
  手动导入独立 ZIP；没有验证过的正式安装/发布 API，不声称自动部署。
- 不创建 Git Tag 或 Release，不自动合并。请通过 **Create a merge commit** 合并 PR，
  main 上该 merge commit 的完整 SHA 标识发布版本。

## main Ruleset：人工配置

首次 PR CI 运行后，在 PR Checks 或 Actions job 页面确认实际 check name。
`validate-skills` 是工作流声明的预期名称；未观察到首次远端 CI 前，不能称它为已验证的实际名称，
不要添加尚未出现或拼写不同的必需检查。

仓库 **Settings → Rules → Rulesets → New branch ruleset**：

1. 名称 `protect-main`，Enforcement status 设为 **Active**，目标分支为 `main`，不设置常规 bypass。
2. 开启 **Require a pull request before merging**；单人维护 required approvals 设为 **0**，
   不强制无法满足的外部或 Code Owner 审批。
3. 开启 **Require status checks to pass**；选择首次 CI 实际出现的验证 check，来源为 GitHub Actions。
   建议同时启用 **Require branches to be up to date before merging**。
4. 开启 **Require conversation resolution before merging**、**Block force pushes**、
   **Restrict deletions**。
5. 保存后复查 Active、main 匹配范围及必需检查。设置未实际保存成功前，不宣称保护已生效。

若连接没有 Ruleset administration 能力，由仓库管理员执行以上步骤；不要绕过保护。
本仓库不包含自动修改 Ruleset、推送 main、打 Tag、创建 Release 或安装 ChatGPT 的代码。

## 新增 Skill

在 `skills/<lowercase-hyphen-name>/` 放置简短 `SKILL.md`、`agents/openai.yaml`
及按需加载的详细 `references/`。名称必须与目录一致，默认提示需包含 `$<name>`。
通过全部验证、测试及公开信息审查后走 PR；打包器会自动为每个 Skill 生成独立包。

