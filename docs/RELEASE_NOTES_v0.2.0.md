# v0.2.0 Public Release Notes / v0.2.0 公开版本发布说明

This release focuses on bilingual user experience, local zero-dependency reporting dashboards, systematic domain routing skeletons, and clear safety boundary enforcement.
本版本专注于双语用户体验、本地零依赖报告看板、系统性的领域分流框架，以及明确的安全边界划分。

---

## English Release Notes

### Highlights
1. **Bilingual Onboarding Wizard (`wizard`)**:
   - Added interactive CLI guided setup supporting `--lang en` and `--lang zh`.
   - Explains default local-first boundaries and scans package folders dynamically for available review modules.
2. **Zero-Dependency Local Dashboard Viewer**:
   - Complete static interactive HTML dashboard framework for unified evidence reviews.
   - Built-in localized labels, offline-friendly (no external CSS/JS network calls), and optional `--view` local server runner using Python's standard library.
3. **Manual Review Priority Index (MRPI)**:
   - A heuristic priority scoring system designed to help reviewers triage case files by grading evidence volume, confidence, and severity weights.
   - **Important Safety Boundary**: MRPI is NOT a "misconduct probability" or a verdict on research integrity. It is solely an attention-prioritization score calculated from local rule-match weights.
4. **6-Domain Routing Skeleton**:
   - Implemented domain routing detectors across six disciplines: Clinical (`clinical`), Biomedical (`biomedical`), Chemistry (`chemistry`), Materials Characterization (`materials_characterization`), AI/ML (`ai_ml`), and Psychology/Social Science (`psychology_social_science`).
   - **Domain Detector Boundary**: The routing logs output `status: "routing_only"` and `not_implemented: true` for the active placeholders. They indicate that the data columns match a specific domain's routing target, but do *not* run actual domain-specific anomaly detection logic.

### Safety and Policy Adherence
- **Strictly Offline by Default**: Avoids network calls unless explicitly opted in via `--allow-network`.
- **No MISCONDUCT Verdicts**: Outputs do not claim, prove, or suggest research fraud or misconduct. They present candidates, risk signals, and verification questions for manual review.

---

## 中文发布说明

### 主要更新
1. **双语交互式配置向导 (`wizard`)**:
   - 新增支持 `--lang en` 和 `--lang zh` 的交互式命令行配置向导。
   - 介绍默认的本地优先边界，并动态扫描包目录以确定可用的证据复核模块。
2. **零依赖本地看板查看器**:
   - 针对统一证据包的静态交互式 HTML 看板框架。
   - 内置本地化语言标签，完全离线友好（无外部 CSS/JS 网络请求），并支持通过 Python 标准库实现的 `--view` 本地服务启动器。
3. **人工复核优先指数 (MRPI)**:
   - 一套启发式优先级评分系统，旨在通过对证据量、置信度和严重性权重进行评分，帮助评审员对案例文件进行分类和筛选。
   - **重要安全边界说明**：MRPI **不是**“学术不端概率”，也不是对学术诚信的最终裁决。它仅仅是根据本地规则匹配权重计算出的注意力优先级分数。
4. **6 大领域分流框架 (Routing Skeleton)**:
   - 实现了跨 6 个学科的领域分流检测器：临床医学 (`clinical`)、生物医学 (`biomedical`)、化学 (`chemistry`)、材料表征 (`materials_characterization`)、人工智能/机器学习 (`ai_ml`) 以及心理学/社会科学 (`psychology_social_science`)。
   - **领域检测器边界说明**：对于目前处于骨架状态的检测器，分流日志会输出 `status: "routing_only"` 且 `not_implemented: true`。这仅表示数据列与特定领域的匹配，而**非**运行了实际的领域内异常检测逻辑。

### 安全与规范遵循
- **默认完全离线运行**：除非明确使用 `--allow-network`，否则绝不发起网络调用。
- **不判定学术不端**：输出结果不声称、不证实、也不暗示任何科研欺诈或学术不端行为，仅提供候选风险信号、替代性良性解释与人工复核问题清单。
