# 社区软件注册表设计调研

调研日期：2026-10-14。仅依据 Scoop、Microsoft WinGet 与 Homebrew 的官方文档、官方源码仓库；未运行其安装器或审核完整基础设施。下文“观察”描述已查到的公开机制，“建议”是面向社区目录的原创设计选择。链接指向可核查的一手资料，默认分支和政策今后可能变化。

## 结论

适合小型社区目录的起点是：**一软件一份 JSON，统一 Schema，声明上游发现规则与平台资产；首次人工审核，后续自动生成更新提案；既有网站通过私有发布适配器消费已审核版本。** 公共注册表负责软件事实和社区协作，发布凭据、部署参数、镜像对象映射及执行状态由消费方保管。

这是一项建议，并非三个项目共有的现成标准。Scoop 的 JSON manifest 最接近目标布局；WinGet 展示了结构化安装器、多版本和多语言的扩展方式；Homebrew 展示了上游发现、自动提案与人工维护之间的分工。无需为了“成熟”而同时复制三个包管理器的安装执行能力。

## 观察：目录与校验

| 项目 | 维护单位与文件布局 | 校验方式 | 对“一软件一 JSON”的启示 |
| --- | --- | --- | --- |
| Scoop | bucket 中以 app manifest JSON 描述软件，文件名作为软件名；Main 将目录数据与工具目录分开。[Manifest 文档](https://github.com/ScoopInstaller/Scoop/wiki/App-Manifests)、[Main 仓库](https://github.com/ScoopInstaller/Main) | 官方维护 JSON Schema，PR 工具另检查格式、描述与许可证、下载哈希、发现及自动更新功能。[Schema](https://github.com/ScoopInstaller/Scoop/blob/master/schema.json)、[官方 Actions](https://github.com/ScoopInstaller/GithubActions) | 可借鉴独立文件、固定字段与自动维护规则；其安装脚本能力不必进入纯目录合同。 |
| WinGet | 使用 YAML；按标识及版本组织目录，常将 version、installer、defaultLocale 和其他 locale 分文件。singleton 仅适用于一个安装器及一个 locale。[Manifest 文档](https://learn.microsoft.com/en-us/windows/package-manager/package/manifest) | YAML 对应 JSON Schema；`winget validate` 检查 manifest，提交后还有安装器及二进制验证。[提交文档](https://learn.microsoft.com/en-us/windows/package-manager/package/repository) | 一软件一文件并非 WinGet 的真实模型；其多文件设计服务安装和本地化需求，简单网站目录不必照搬。 |
| Homebrew Casks | 每个 cask 是 Ruby DSL，token 应与文件名对应，声明版本、URL、校验和、元数据与安装产物。[Cask Cookbook](https://docs.brew.sh/Cask-Cookbook) | 官方 CI 运行语法及 cask audit，并按测试矩阵处理获取和安装检查；不是 JSON Schema 校验 Ruby。[CI 源码](https://github.com/Homebrew/homebrew-cask/blob/main/.github/workflows/ci.yml) | 可借鉴一份定义的审查粒度；Ruby DSL 及执行语义会扩大维护与安全边界。 |

这些项目验证的不只是 JSON/YAML 能否解析。字段格式、软件收录条件、URL 与文件哈希、实际安装行为属于不同层次；Schema 通过不能替代来源审核和功能验证。这里对层次的归纳是对上述机制的推断。

## 观察：发现版本与平台资产

**Scoop。** `checkver` 支持网页正则、JSONPath、XPath，以及 GitHub Releases 等入口；`autoupdate` 用版本变量生成新下载地址和哈希。GitHub 的特殊规则忽略预发布。manifest 使用 `32bit`、`64bit`、`arm64` 架构分支，分别配置 URL、hash 等内容。官方文档建议生成更新后再实际安装确认。[自动更新文档](https://github.com/ScoopInstaller/Scoop/wiki/App-Manifest-Autoupdate)、[架构字段](https://github.com/ScoopInstaller/Scoop/wiki/App-Manifests)

**WinGet。** installer manifest 对每个安装器声明 Architecture、InstallerUrl、InstallerSha256，也能表达平台、最低系统版本、安装器类型及安装模式。软件版本不一定是 SemVer。`wingetcreate update` 由调用者提供新版本、安装器 URL 等信息，工具帮助下载、解析、更新与提交；官方支持把它接到发布流水线。本次查阅资料没有证明 manifest 本身提供了 Scoop 式通用网页发现 DSL，不能把“能自动提交”理解为“能自行发现任意上游新版本”。[Manifest 文档](https://learn.microsoft.com/en-us/windows/package-manager/package/manifest)、[Update 命令](https://github.com/microsoft/winget-create/blob/main/doc/update.md)、[WinGetCreate](https://github.com/microsoft/winget-create)

**Homebrew。** `livecheck` 从发行说明、appcast 等官方入口识别更新；`arch`、`os`、`on_<system>` 能为不同系统与架构选择 URL、版本及 SHA-256。当前官方收录政策允许支持 macOS、Linux 或两者，要求覆盖声明的平台；不能继续套用“Casks 只支持 macOS”的旧概括。[Cask Cookbook](https://docs.brew.sh/Cask-Cookbook)、[Acceptable Casks](https://docs.brew.sh/Acceptable-Casks)

**推断。** 上游发布位置、版本识别、资产选择与目标平台是四个不同概念。GitHub 仓库标识只是某一种发现入口；同一个 release 可能含源码包、签名、校验文件及多个平台安装包，不能默认下载全部附件，也不能靠列表顺序识别正确文件。

## 观察：贡献与首次审核

- **Scoop：** Main 的收录规则偏向稳定版本、较标准的安装过程和开发者命令行工具，并非任意桌面软件目录。当前组织级贡献指南要求新 package 先提出 issue，获得维护者认可后提交 PR；bucket 贡献还要求安装、卸载、持久化与自动更新验证，并等待代码审查。[Main 收录规则](https://github.com/ScoopInstaller/Scoop/wiki/Criteria-for-including-apps-in-the-main-bucket)、[贡献指南](https://github.com/ScoopInstaller/.github/blob/main/.github/CONTRIBUTING.md)
- **WinGet：** 贡献者可手写 manifest，或使用生成工具。提交 PR 后自动检查结构、安装器及安全性，再由 moderator 人工审核；官方强调安装器来自发布者网站、信息准确、支持非交互安装。公开 GitHub manifest 仓库与客户端实际访问的公开目录是两个概念。[创建 manifest](https://learn.microsoft.com/en-us/windows/package-manager/package/manifest)、[提交与验证](https://learn.microsoft.com/en-us/windows/package-manager/package/repository)
- **Homebrew：** 新 cask 先核对收录政策，贡献者提交 PR，并安装、卸载、运行相关在线检查后等待维护者反馈；现有 cask 的版本更新可使用专门的 bump 工具。维护者指南对新增、发现规则修改、正常版本更新及同版本哈希变化分别判断。[贡献流程](https://docs.brew.sh/How-To-Open-a-Homebrew-Pull-Request)、[维护者指南](https://docs.brew.sh/Homebrew-homebrew-cask-Maintainer-Guide)

**推断。** 自动检查可统一基础质量，但第一次收录涉及软件身份、来源和更新规则，不能仅靠“当前 URL 可下载”确定。三个项目的具体收录门槛不同，不应把 Main 的知名度或非 GUI 条件当作所有社区目录的共同要求。

## 观察：常规更新自动化

Scoop Main 的 Excavator 工作流当前每四小时运行，赋予内容写权限，调用官方 Actions；相应工具支持定期更新 manifest。它与 PR 校验工作流分别配置，PR CI 使用读取权限。这说明“检测、验证、写入”可以拆成不同执行角色；不能把这一具体工作流描述成“所有 Scoop 更新都必须先开 PR”。[Excavator 源码](https://github.com/ScoopInstaller/Main/blob/master/.github/workflows/excavator.yml)、[CI 源码](https://github.com/ScoopInstaller/Main/blob/master/.github/workflows/ci.yml)、[Actions 说明](https://github.com/ScoopInstaller/GithubActions)

WinGetCreate 官方文档支持在软件发布 CI/CD 中更新并提交 manifest，并明确要求提交令牌放在流水线秘密变量或仓库 Secrets，避免硬编码。它是工具和接入方式；本次调研不推断整个 WinGet 社区所有软件都有中央轮询器。[WinGetCreate README](https://github.com/microsoft/winget-create)

Homebrew 的 Autobump 默认覆盖符合条件的新 formula/cask，约每三小时检查并在需要时开更新 PR；可使用 `no_autobump!`、禁用或 skip 声明排除，排除理由需记录。官方工作流调用带开 PR 参数的 bump，并从 Secrets 读取 API token 和签名材料。[Autobump](https://docs.brew.sh/Autobump)、[工作流源码](https://github.com/Homebrew/homebrew-cask/blob/main/.github/workflows/autobump.yml)

维护者指南特别指出：SHA-256 能揭示固定下载内容被替换，但不能独立证明专有二进制的真实性；同版本校验和变化应作为异常调查，不能直接当作日常更新处理。[校验和与重新打标政策](https://docs.brew.sh/Homebrew-homebrew-cask-Maintainer-Guide)

## 观察：公共目录与运行系统的边界

官方实现提供了几项可以核实的分离事实：

1. Scoop 的软件 manifest 与安装器核心分别在 bucket、Scoop 仓库，自动化读取运行期 token。[Main](https://github.com/ScoopInstaller/Main)、[Actions 说明](https://github.com/ScoopInstaller/GithubActions)
2. WinGet 区分 GitHub 投稿仓库与面向客户端的实际目录；WinGetCreate 将 token、settings、cache 作为工具管理事项。[投稿目录说明](https://learn.microsoft.com/en-us/windows/package-manager/package/repository)、[工具说明](https://github.com/microsoft/winget-create)
3. Homebrew 以 cask 源定义提供元数据，并另提供整体或单 cask 的 JSON API；工作流引用秘密存储中的值，而非把令牌写入 cask。[JSON API](https://formulae.brew.sh/docs/api/)、[Autobump 工作流](https://github.com/Homebrew/homebrew-cask/blob/main/.github/workflows/autobump.yml)

这些事实支持“贡献源定义与消费发布系统分开”的设计，但**不能证明三个项目所有部署代码和执行状态都存放在私有仓库**。公开 workflow 是正常的；秘密值、部署连接信息和本次执行记录不属于每软件 manifest，这才是可采纳的边界。无需引入聚合注册表作为第四个依赖来完成此设计。

## 建议：最小、独立于供应商的公共注册表

以下均为设计建议，不是上游标准或对任何现有站点的实现描述。

### 文件与数据合同

公共仓库维护 `catalog/<id>.json`，每个软件一份；另有一个版本化 JSON Schema、简短贡献说明、收录政策和 PR 模板。小规模先用平铺目录，数量导致浏览困难时再按标识首字母分片；不以操作系统拆散同一个软件，也不维护第二份手写全量索引。

**最新版本分发目录应优先采用稳定的上游发现规则，而非 WinGet 式每版本新增 manifest 目录。** 同一 JSON 长期保存软件身份、发现入口和资产选择规则，同时只保存当前已审核发行；机器人修改当前发行形成可审查 diff。Git 历史足以保留目录修改过程，私有发布回执保留实际交付证据。固定 URL 和哈希仍然必要，它们描述“本次审核的发行”，并不要求把每个旧版本作为长期公开维护单位。需要旧版本选择和安装升级语义时，再考虑专门的版本索引。

| 字段组 | 最小内容 | 约束 |
| --- | --- | --- |
| 身份 | `schemaVersion`、稳定 `id`、`name`、`summary`、`homepage`、`license` | id 与文件名一致；显示名称变化不改变 id；许可证能表明专有/免费使用与再分发的区别。 |
| 上游 | 可选源码地址；官方 release 页或更新入口 | 首页、源码仓库、发行来源各有含义，不相互推导。 |
| 发现 | `type`、`locator`、`channel`，必要的版本提取规则 | 首期只实现少量确定性类型，例如 GitHub Releases、官方 JSON feed、manual；其他入口未支持时明确转人工。 |
| 目标资产 | 每项声明 `platform`、`architecture`、`format`、资产匹配规则 | 使用规范枚举；支持 universal/独立架构；匹配必须恰好一项，零项或多项均停止提案。 |
| 已审核发行 | `version`、发行证据 URL、每项资产的固定 URL 与 `sha256` | 更新机器人修改这一组并开 PR；网站消费合并后的固定记录，不能把实时上游“latest”直接当作已审核版本。 |

Schema 验证字段、枚举、必填关系和未知字段；语义检查另验证 id 唯一、平台组合唯一、官方来源关系、发现规则及资产匹配结果。不要要求所有上游都使用 SemVer，也不要允许贡献者嵌入任意 shell/PowerShell/Ruby 脚本。发现接口可有供应商专用实现，但输出统一为版本、发行证据、平台资产、URL 与校验和。

对实际分发的固定发行资产要求 SHA-256；只有无法获得固定二进制的软件，才采用明确标识的“仅链接展示”模式，并记录人工原因。下载哈希不代表获得镜像或再分发许可；私有适配器仍需依据许可证及站点政策决定是否镜像。

### 贡献与初审

允许贡献者直接提交单软件 PR；需要讨论例外时再先开 issue，不必给每次小更新增加双重流程。PR 模板只要求官方软件主页、发行来源、许可信息、平台资产映射和一次发现结果。Schema/静态检查不使用发布秘密。

首次人工审核检查身份和重名、发布者与下载域名的关系、许可证及分发边界、稳定/预发布通道、平台资产选择、安装包与源码包的区别。新增来源域名、发现算法或资产选择规则变化也走人工审核。纯描述修订和版本更新可以分配更轻的检查；审核通过后才能进入消费目录。

### 更新自动化

推荐先采用“定时发现 → 生成固定版本与资产记录 → 校验 → 开 PR → 合并后消费”的流程。初期不自动合并；积累证据后，可只对来源和选择规则未改变的普通更新开放自动合并。第一次收录、同版本哈希变化、目标架构缺失、跳到预发布、域名改变均停止并请求维护者处理。

机器人每软件只保留一个待处理更新提案；上游无更新时不产生提交。给请求设置超时、下载大小和重试上限，支持手动重查与暂停，并在私有执行状态保存 ETag、上次检查时间与失败退避。失败不能删除已审核发行，也不能悄悄减少软件声明支持的平台。

### 既有网站的私有发布适配器

公共注册表合并并不等于网站发布成功。适配器读取指定公开提交的已审核 JSON，转换成站点自己的目录/发布 API 输入，预览差异，再执行发布。网站不要求社区贡献者提供站点账号、云盘目录、存储 key 或部署命令。

私有消费侧保管站点软件 ID 对照、分类映射、发布/存储凭据、镜像与 CDN 配置、上游下载缓存、导入时间、发布任务、重试游标和实际结果。公开文件中不写这些值，也不回填某个消费站点的临时签名下载 URL。多个站点可以读取同一公开合同，各自维护适配器。

公共 core 的最小职责是加载与验证 JSON、调用受限发现器、选择资产及生成标准化更新提案；这些逻辑可公开并在无网站权限的环境运行。私有 adapter 只负责把已审核快照发布到既有站点并产出回执。回执记录公开提交、软件/版本/平台、输入摘要、上游资产摘要、目标发行标识、执行时间和结果；回执、缓存和部署状态不写回注册表，也不让 core 依赖某个站点的数据模型。

发布以公开提交标识、软件 id、版本、目标平台和文件摘要构成幂等依据，记录“读取、解析、获取、发布”各步结果，并允许按单软件失败重试。批次失败不冒充全批成功；凭据只在可信发布执行环境读取，不暴露给 fork PR 或运行贡献者代码的校验阶段。

### 首期完成标准

1. 新软件只需增加一份 JSON，校验能指出具体字段与问题。
2. 没有秘密或网站部署环境也能完成格式和语义验证。
3. 自动发现可正确区分通道及平台资产，歧义或缺失会停止更新。
4. 更新先形成可读 diff 和证据，首次收录及异常修改经过人工审核。
5. 发布适配器消费固定、可追溯的已审核快照；重复运行不会重复创建软件或发行。
6. 发布失败保留已有可用版本，状态和缓存有期限及容量上限，公共目录保持供应商独立。

这些标准足以验证核心边界。多站点发布编排、任意脚本更新器、包安装引擎、庞大版本历史仓库和复杂依赖求解均可在确有需求后再考虑。
