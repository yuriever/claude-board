# Codex Desktop IPC 调查报告

这份报告解释 Codex Desktop live-thread 监控路线的调查结果。目标不是控制 Codex Desktop，而是让 Claude Fleet 能看到 Desktop 内正在运行或已加载的 Codex thread 状态，并把它们显示成只读卡片。

## 目标

需要解决的问题是：Codex TUI 可以被现有 live-card 机制监控，但 Codex Desktop 不行。

TUI 是一个普通终端进程。Phase 1 和 Phase 2 已经通过平台 adapter 读取它的打开文件、进程 cwd 和启动时间，从而找到 live rollout 和 runtime 状态。

Desktop 不同。一个 Desktop app 进程里可以同时加载多个 thread，不能用“一个进程等于一个卡片”的模型。它也没有 TUI 那种稳定 tty，因此继续扩展 TUI adapter 不能得到正确结果。

## 做过的尝试

* TUI 路线

    TUI 监控已经可用。它适合终端里的 `codex` 进程，但 Desktop 没有 per-thread tty，也不会把每个 thread 暴露成独立进程。

* App Server sidecar 路线

    这条路线尝试用独立的 app-server 或 sidecar 查询 thread 状态。问题是 sidecar 有自己的 loaded-thread 视图，不能直接看到 Desktop app 内存里的已加载 thread。它可以提供历史或 metadata，但不能稳定代表 Desktop 当前正在忙、空闲或等待。

* daemon 路线

    这条路线尝试启动 app-server daemon，再让 TUI 通过 remote socket 连接。实验结果是 daemon 可以看到通过它启动或连接的 remote TUI thread，但 Desktop 不会自动挂到这个 daemon 上。因此 daemon 不能直接解决 Desktop live status。

* Desktop 和 VS Code 共享状态线索

    观察到 Codex Desktop 和 VS Code Codex extension 可以近实时共享 thread 状态。这说明 Desktop 内部确实存在某种本地同步通道，比 sidecar metadata 更接近真实 runtime 状态。

* Desktop IPC 路线

    进一步检查 Desktop 进程和 app bundle 后，发现本地 IPC router socket。非 Windows 平台上的 socket 位置模式是 `codex-ipc/ipc-<uid>.sock`，位于用户临时目录下。它不是 WebSocket，而是四字节 little-endian 长度前缀加 JSON payload。

    以 monitor client 初始化后，router 会广播 `thread-stream-state-changed` 消息。短时间探测已经确认可以收到多个已加载 Desktop thread 的状态变化，其中包含 active 和 idle 状态。

## Desktop IPC 路线是什么

可以把 Desktop IPC 理解成 Desktop app 内部的本地消息总线。

Desktop 主进程持有一个本地 socket。Desktop 窗口、VS Code extension 或其他 Codex 客户端可以作为 client 接入这个 router。router 负责转发 thread 状态、stream 更新和 discovery 请求。

Claude Fleet 的 Phase 3 adapter 应该作为一个只读 monitor client 接入：

* 连接本地 socket
* 发送 initialize 请求，声明自己是 monitor
* 收到 client discovery 请求时始终回答 `canHandle: false`
* 只监听 `thread-stream-state-changed`
* 只提取状态白名单字段
* 立刻丢弃 prompts、命令文本、输出、diff、token usage 和 turn items

这条路线不需要给 thread 发送 resume，也不需要周期性订阅每个 thread。它监听的是 Desktop router 已经在广播的 thread stream 状态。

## 收到的数据长什么样

IPC 消息有两类重要形态：

* snapshot

    snapshot 是某个 thread 的完整运行状态。它可能包含 `conversationId`、runtime status、cwd、source、revision、rollout path，以及大量敏感内容。adapter 只能抽取白名单字段。

* patch

    patch 是后续增量更新。它可能只改变 status，也可能涉及 turn item、命令输出或 diff。adapter 只能接受白名单路径上的状态更新，其他路径必须忽略。

Phase 3 的核心不是保存这些原始消息，而是把它们折叠成很小的内存状态：

* 哪个 Desktop thread
* 当前是 busy、waiting、idle 还是 unknown
* cwd 和来源等安全元数据
* 更新时间

## 为什么这条路线比 sidecar 更有价值

sidecar 能看到的是它自己管理的 loaded-thread 状态。Desktop thread 如果没有通过这个 sidecar 加载，sidecar 就只能给出 history 或 not-loaded 这类间接信息。

Desktop IPC 看到的是 Desktop app 自己正在广播的 runtime stream。因此它更接近 Owner 想要的实时监控语义：当前 Desktop 里哪些 thread loaded，哪些正在 active，哪些 idle，哪些可能 waiting。

## 安全边界

Desktop IPC payload 是高敏感输入。实现时要把它当作“只可瞬时解析，不可原样保存”的数据源。

必须遵守：

* 不记录原始 frame
* 不记录 prompts、命令、输出、diff、token usage
* 限制 frame 最大长度
* socket 路径只从系统 temp dir 和 uid 推导，不从 web API 接收
* 只作为 monitor client，不声明处理能力
* discovery 请求始终回答 `canHandle: false`
* malformed frame、权限失败、socket 不存在、版本不兼容时返回空列表
* Desktop 卡片只读，不提供 prompt、close、fork、review、tmux 或 background-task action

## 对 Phase 3 实现的直接结论

Phase 3 可以交给新 thread 实现，但必须按只读 adapter 做。

推荐实现位置是 `core/codex_desktop.py`。它应该维护一个内存 cache，把 IPC snapshot 和 patch 转成 sanitized card dict，然后由 `app.py` 在 `_enriched_snapshot()` 里合并到现有窗口列表。

当前 dashboard 用 numeric `pid` 作为卡片 key。Desktop 不能使用真实 app process pid，因为一个 app process 可能有多个 thread。实现应为每个 `conversationId` 生成稳定的负数 synthetic pid，同时保留真实 `thread_id` 字段。所有把 pid 当操作系统进程使用的地方都必须忽略这些负数 synthetic pid。

完成后，Claude Fleet 应该能显示 Codex TUI live cards 和 Codex Desktop read-only live cards，但 Desktop card 不应该拥有任何控制能力。
