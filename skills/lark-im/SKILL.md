---
name: lark-im
version: 1.0.0
description: "飞书即时通讯：收发消息和管理群聊。发送和回复消息、搜索聊天记录、管理群聊成员、上传下载图片和文件（支持大文件分片下载）、管理表情回复、发送应用内/短信/电话加急。当用户需要发消息、查看或搜索聊天记录、下载聊天中的文件、查看群成员、搜索群、创建群聊或话题群、管理标记数据时使用。"
metadata:
  requires:
    bins: ["lark-cli"]
  cliHelp: "lark-cli im --help"
---

# im (v1)

## Core Concepts

- **Message**: A single message in a chat, identified by `message_id` (om_xxx). Supports types: text, post, image, file, audio, video, sticker, interactive (card), share_chat, share_user, merge_forward, etc.
- **Chat**: A group chat or P2P conversation, identified by `chat_id` (oc_xxx).
- **Thread**: A reply thread under a message, identified by `thread_id` (om_xxx or omt_xxx).
- **Reaction**: An emoji reaction on a message.
- **Flag**: A bookmark on a message or thread.

## Resource Relationships

```
Chat (oc_xxx)
├── Message (om_xxx)
│   ├── Thread (reply thread)
│   ├── Reaction (emoji)
│   └── Resource (image / file / video / audio)
└── Member (user)
```

## Important Notes

### Identity and Token

All IM operations run as **user identity** with a `user_access_token`. Calls run as the authorized end user, so permissions depend on both the app scopes and that user's own access to the target chat/message/resource.

### Default message enrichment (reactions / update_time)

The four message-pulling shortcuts (`+messages-mget`, `+chat-messages-list`, `+messages-search`, `+threads-messages-list`) automatically attach a `reactions` block and (for edited messages) `update_time` to each returned message — no separate `im.reactions.batch_query` call is needed. Pass `--no-reactions` to opt out. For the full contract (output shape, the `im:message.reactions:read` scope requirement, and the "missing field ≠ fetch failure" data rules), read [`references/lark-im-message-enrichment.md`](references/lark-im-message-enrichment.md).

### Card Messages (Interactive)

Card messages (`interactive` type) are not yet supported for compact conversion in event subscriptions. The raw event data will be returned instead, with a hint printed to stderr.

### Flag Types

Flags support two layers:

- **Message-layer flag**: `(ItemTypeDefault, FlagTypeMessage)` — regular message bookmark
- **Feed-layer flag**: `(ItemTypeThread/ItemTypeMsgThread, FlagTypeFeed)` — thread as feed-layer bookmark

Item types for feed-layer flags:
- **ItemTypeThread** (4) = thread in a topic-style chat
- **ItemTypeMsgThread** (11) = thread in a regular chat

## Shortcuts（推荐优先使用）

Shortcut 是对常用操作的高级封装（`lark-cli im +<verb> [flags]`）。有 Shortcut 的操作优先使用。

| Shortcut | 说明 |
|----------|------|
| [`+chat-create`](references/lark-im-chat-create.md) | Create a group chat or topic chat; user; --chat-mode group|topic; private/public; invites users/bots; optionally sets bot manager |
| [`+chat-list`](references/lark-im-chat-list.md) | List chats the current user is a member of; defaults to groups; pass --types=p2p,group to include p2p single chats (user-only); user; supports sorting, pagination, --exclude-muted (user-only) |
| [`+chat-messages-list`](references/lark-im-chat-messages-list.md) | List messages in a chat or P2P conversation; user; accepts --chat-id or --user-id, resolves P2P chat_id, supports time range/sort/pagination |
| [`+chat-search`](references/lark-im-chat-search.md) | Search visible group chats by --query keyword and/or --member-ids; user; e.g. look up chat_id by group name; supports type filters, sorting, pagination, and --exclude-muted (user identity only) |
| [`+chat-update`](references/lark-im-chat-update.md) | Update group chat name or description; user; updates a chat's name or description |
| [`+messages-mget`](references/lark-im-messages-mget.md) | Batch get messages by IDs; user; fetches up to 50 om_ message IDs, formats sender names, expands thread replies |
| [`+messages-reply`](references/lark-im-messages-reply.md) | Reply to a message (supports thread replies); user; supports text/markdown/post/media replies, reply-in-thread, idempotency key |
| [`+messages-resources-download`](references/lark-im-messages-resources-download.md) | Download images/files from a message; user; supports automatic chunked download for large files (8MB chunks), auto-detects file extension from Content-Type |
| [`+messages-search`](references/lark-im-messages-search.md) | Search messages across chats (supports keyword, sender, time range filters) with user identity; user-only; filters by chat/sender/attachment/time, supports auto-pagination via `--page-all` / `--page-limit`, enriches results via batched mget and chats batch_query |
| [`+messages-send`](references/lark-im-messages-send.md) | Send a message to a chat or direct message; user; sends to chat-id or user-id with text/markdown/post/media, supports idempotency key |
| [`+threads-messages-list`](references/lark-im-threads-messages-list.md) | List messages in a thread; user; accepts om_/omt_ input, resolves message IDs to thread_id, supports sort/pagination |
| [`+flag-create`](references/lark-im-flag-create.md) | Create a bookmark on a message or thread; user-only; defaults to message-layer flag; feed-layer flag requires explicit --item-type + --flag-type |
| [`+flag-cancel`](references/lark-im-flag-cancel.md) | Cancel (remove) a bookmark. When no --flag-type is given, checks if the message is a thread root message; if so, cancels both message and feed layers |
| [`+flag-list`](references/lark-im-flag-list.md) | List bookmarks; user-only; auto-enriches feed-type thread entries with message content; supports `--page-all` auto-pagination |

## API Resources

```bash
lark-cli schema im.<resource>.<method>   # 调用 API 前必须先查看参数结构
lark-cli im <resource> <method> [flags] # 调用 API
```

> **重要**：使用原生 API 时，必须先运行 `schema` 查看 `--data` / `--params` 参数结构，不要猜测字段格式。

### chats

  - `create` — 创建群。Prefer the [`+chat-create`](references/lark-im-chat-create.md) shortcut, which runs as the user.
  - `get` — 获取群信息。Identity: supports `user` only; the caller must be in the target chat to get full details, and must belong to the same tenant for internal chats.
  - `link` — 获取群分享链接。Identity: supports `user` only; the caller must be in the target chat, must be an owner or admin when chat sharing is restricted to owners/admins, and must belong to the same tenant for internal chats.
  - `update` — 更新群信息。Identity: supports `user` only.

### chat.members

  - `bots` — 获取群内机器人列表。Identity: supports `user` only; the caller must be in the target chat and must belong to the same tenant for internal chats.
  - `create` — 将用户或机器人拉入群聊。Identity: supports `user` only; the caller must be in the target chat; for internal chats the operator must belong to the same tenant; if only owners/admins can add members, the caller must be an owner/admin.
  - `delete` — 将用户或机器人移出群聊。Identity: supports `user` only; only the group owner or an admin can remove others; max 50 users or 5 bots per request.
  - `get` — 获取群成员列表。Identity: supports `user` only; the caller must be in the target chat and must belong to the same tenant for internal chats.

### messages

  - `delete` — 撤回消息。Identity: supports `user` only; you can revoke your own messages, and revoking another user's group message requires owner or admin privileges.
  - `forward` — 转发消息。Identity: supports `user` only.
  - `merge_forward` — 合并转发消息。Not available under user identity.
  - `read_users` — 查询消息已读信息。Not available under user identity.
  - `urgent_app` — 发送应用内加急。Not available under user identity.
  - `urgent_phone` — 发送电话加急。Not available under user identity.
  - `urgent_sms` — 发送短信加急。Not available under user identity.

### reactions

  - `batch_query` — 批量获取消息表情。Identity: supports `user` only.[Must-read](references/lark-im-reactions.md)
  - `create` — 添加消息表情回复。Identity: supports `user` only; the caller must be in the conversation that contains the message.[Must-read](references/lark-im-reactions.md)
  - `delete` — 删除消息表情回复。Identity: supports `user` only; the caller must be in the conversation that contains the message, and can only delete reactions added by itself.[Must-read](references/lark-im-reactions.md)
  - `list` — 获取消息表情回复。Identity: supports `user` only; the caller must be in the conversation that contains the message.[Must-read](references/lark-im-reactions.md)

### threads

  - `forward` — 转发话题。Identity: supports `user` only.

### images

  - `create` — 上传图片。Not available under user identity.

### pins

  - `create` — Pin 消息。Identity: supports `user` only.
  - `delete` — 移除 Pin 消息。Identity: supports `user` only.
  - `list` — 获取群内 Pin 消息。Identity: supports `user` only.

## 权限表

| 方法 | 所需 scope |
|------|-----------|
| `chats.create` | `im:chat:create` |
| `chats.get` | `im:chat:read` |
| `chats.link` | `im:chat:read` |
| `chats.update` | `im:chat:update` |
| `chat.members.bots` | `im:chat.members:read` |
| `chat.members.create` | `im:chat.members:write_only` |
| `chat.members.delete` | `im:chat.members:write_only` |
| `chat.members.get` | `im:chat.members:read` |
| `messages.delete` | `im:message:recall` |
| `messages.forward` | `im:message` |
| `messages.merge_forward` | `im:message` |
| `messages.read_users` | `im:message:readonly` |
| `messages.urgent_app` | `im:message.urgent` |
| `messages.urgent_phone` | `im:message.urgent:phone` |
| `messages.urgent_sms` | `im:message.urgent:sms` |
| `reactions.batch_query` | `im:message.reactions:read` |
| `reactions.create` | `im:message.reactions:write_only` |
| `reactions.delete` | `im:message.reactions:write_only` |
| `reactions.list` | `im:message.reactions:read` |
| `threads.forward` | `im:message` |
| `images.create` | `im:resource` |
| `pins.create` | `im:message.pins:write_only` |
| `pins.delete` | `im:message.pins:write_only` |
| `pins.list` | `im:message.pins:read` |

