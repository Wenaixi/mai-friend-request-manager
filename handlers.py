"""好友申请处理插件 — 策略处理器。"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from .plugin import FriendRequestHandlerPlugin

LLM_PROMPT = (
    '你是QQ好友申请审核助手。审核原则：默认通过，只在最危险的情况下拒绝。\n'
    '\n'
    '【主人偏好】主人明确希望好友申请多通过、少拒绝。\n'
    '主人的社交风格是"宁可错加，不可错过"——相信大多数人是善意的陌生人。\n'
    '只要你不100%确定对方有恶意，就大胆回复"通过"。\n'
    '- 短验证消息 = 友好意图（通过）\n'
    '- 文学引用/古诗词/伤感内容 = 文艺青年（通过）\n'
    '- 简单的打招呼/求通过/想聊天 = 友好社交（通过）\n'
    '- 二次元/ACG/小红书风格/网络梗 = 当代网友正常表达（通过）\n'
    '\n'
    '【必须拒绝】以下任一情况直接回复"拒绝"：\n'
    '1. 验证消息含明显的可疑链接（http/https 开头且指向不常见域名）\n'
    '2. 明确的营销/引流话术（如"加群领福利""免费代理""代刷""兼职日结""低价出售"等）\n'
    '3. 明显的辱骂、人身攻击、色情、赌博或政治反动内容\n'
    '\n'
    '【应当通过】包括但不限于（不限于这些情况）：\n'
    '- 简短的打招呼（"你好""想认识一下""加个好友"）\n'
    '- 含社交意图的词（"扩列""想聊天""求通过""扩个列"）\n'
    '- 含暧昧/表白用语（"喜欢你""想和学姐聊天""小哥哥/小姐姐"）\n'
    '- 套用主人设定的"问题+回答"模板（如"问题1:...回答:..."格式）\n'
    '- 资料字段缺失、签名空、昵称含符号/emoji/网络用语\n'
    '- 等级低、登录天数少、年龄偏小、性别未知\n'
    '- 文学/古诗/伤感/二次元/ACG/网络梗/小红书风格\n'
    '\n'
    '【特别注意】\n'
    '- 验证消息如果是套用问题模板（多个"问题:"开头的行），即使包含"喜欢你""扩列"等词，'
    '也属于正常社交，不要拒绝\n'
    '- 资料字段空/缺失不是拒绝理由\n'
    '- 信息不足时倾向通过而非拒绝\n'
    '- 不要把"简短"或"空洞"当作可疑信号\n'
    '- 不要把"伤感""诗意""二次元""小红书风格""古风"当作可疑信号——这些是当代网友正常表达\n'
    '\n'
    '【积极心态】大胆给陌生人一次机会。\n'
    '你的工作不是找出坏人，而是欢迎大多数善意的人。\n'
    '与人为善，世界会变得更开阔。\n'
    '\n'
    '只回复"通过"或"拒绝"两个汉字，不要附加任何其他内容、解释、引号或标点。'
)

REMARK_PROMPT = (
    '你是一个QQ好友备注生成助手。根据以下申请人信息（昵称、个性签名、验证消息等），'
    '为对方生成一个简短自然的好友备注，不超过8个字，可以参考对方昵称或验证消息中体现的身份/称呼。'
    '只回复备注本身，不要附加任何解释、引号或标点。'
)

def extract_remark_from_comment(comment: str) -> str:
    """从好友申请验证消息中智能提取对方回答的真名、代号或称呼。"""
    if not comment:
        return ""
    patterns = [
        # 问答型：问题含真名/代号/备注/称呼/你是谁/名字，下方紧跟 回答: xxx
        r"(?:真名|代号|备注|称呼|你是谁|名字)[^\n]*?(?:[:：]?\s*\n\s*|\s+)回答\s*[:：]?\s*([^\n\r]+)",
        # 单行型：真名: xxx 或 备注: xxx
        r"(?:真名|代号|备注|称呼|名字)\s*[:：]\s*([^\n\r]+)",
    ]
    for pat in patterns:
        m = re.search(pat, comment, re.IGNORECASE)
        if m:
            ans = m.group(1).strip().strip('"\'“”‘’「」()（）')
            bad_words = ["知道", "了解", "喜欢你", "没有", "好玩", "扩列", "聊天"]
            if ans and len(ans) <= 16 and not any(bad in ans for bad in bad_words):
                return ans
    return ""


async def set_friend_remark_with_retry(
    plugin: "FriendRequestHandlerPlugin",
    user_id: str,
    remark: str,
    delays: list[float] | None = None,
) -> bool:
    """带退避重试的好友备注设置器。

    NapCat 同意好友申请后，NTQQ 同步好友列表写入 SQLite 缓存需 1.5~4 秒。
    在 isBuddy 确认前直接调用会抛出“用户不是好友”。本函数通过多轮退避轮询，
    直到 NapCat 返回 status == 'ok'，彻底解决备注时序死锁问题。
    """
    if not remark:
        return False

    if delays is None:
        delays = [0.5, 1.5, 2.5, 4.0]

    for attempt, delay in enumerate(delays):
        await asyncio.sleep(delay)
        try:
            resp = await plugin._call_napcat(
                "set_friend_remark",
                {"user_id": int(user_id) if str(user_id).isdigit() else str(user_id), "remark": remark},
                raise_on_error=False,
            )
            is_ok = isinstance(resp, dict) and (resp.get("status") == "ok" or resp.get("retcode") == 0)
            if is_ok:
                plugin.ctx.logger.info(f"成功为好友 {user_id} 设置备注: {remark!r} (第 {attempt+1} 次重试生效)")
                return True
            err_msg = resp.get("wording") or resp.get("message") if isinstance(resp, dict) else str(resp)
            plugin.ctx.logger.debug(f"第 {attempt+1} 次设置备注未就绪: {err_msg}")
        except Exception as exc:
            plugin.ctx.logger.debug(f"第 {attempt+1} 次设置备注异常: {exc}")

    plugin.ctx.logger.warning(f"为好友 {user_id} 设置备注 {remark!r} 重试全耗尽，对方尚未完成好友握手")
    return False



async def handle_manual(plugin: "FriendRequestHandlerPlugin", user_id: str, flag: str, comment: str) -> None:
    admin_qqs = plugin._normalized_admin_qqs()
    if not admin_qqs:
        plugin.ctx.logger.warning("收到好友申请但未配置 admin_qqs，无法推送")
        return

    plugin._pending[user_id] = {"flag": flag, "comment": comment, "nickname": ""}

    notice_text = await build_notice_text(plugin, user_id, "", comment)
    for admin_qq in admin_qqs:
        await plugin._send_private_notice(admin_qq, user_id, notice_text)
    plugin.ctx.logger.info(f"已推送好友申请: user_id={user_id} flag={flag}")


async def handle_llm_decision(plugin: "FriendRequestHandlerPlugin", user_id: str, flag: str, comment: str) -> None:
    info_text = await _build_applicant_info_text(plugin, user_id, comment)
    full_prompt = f"{LLM_PROMPT}\n\n申请人信息：\n{info_text}"

    # 第 1 次 LLM：决策 通过/拒绝
    ok, reply = await _call_llm(plugin, full_prompt)
    if not ok:
        plugin.ctx.logger.warning(f"LLM 调用失败，回退到手动模式: user_id={user_id}")
        await handle_manual(plugin, user_id, flag, comment)
        return

    approved = "通过" in reply

    # 诊断日志：记录 LLM 看到的申请人信息 + 实际回复（便于 debug 是否仍误判）
    plugin.ctx.logger.info(
        f"[friend-request-debug] user_id={user_id} approved={approved} reply={reply!r} info={info_text!r}"
    )

    # 【核心修复】提前生成备注：通过时一并传给 set_friend_add_request。
    # 原因：NapCat 的 SetFriendAddRequest._handle 在 handleFriendRequest 之后立即
    # 调 setBuddyRemark（无 isBuddy 检查，原子生效）；而单独调 set_friend_remark
    # 会先查 isBuddy，新建好友关系刚通过时 NapCat 本地缓存还没刷新成 buddy，
    # 必然 throw "用户 XX 不是好友" 被 raise_on_error=False 静默吞掉——这就是
    # 手动路径有备注、LLM 路径没备注的真凶。
    remark = ""
    if approved and plugin.config.strategy.auto_remark:
        # 1. 优先从验证问答中提取用户明确给出的真名/代号
        remark = extract_remark_from_comment(comment)
        # 2. 问答未提取到时，由 LLM 智能生成
        if not remark:
            remark = await _generate_remark(plugin, info_text)
        # 3. 仍未生成时，回退为对方 QQ 昵称
        if not remark:
            remark = await _get_nickname(plugin, user_id)

    params: Dict[str, Any] = {"flag": flag, "approve": approved}
    if approved and remark:
        params["remark"] = remark
    await plugin._call_napcat(
        "set_friend_add_request",
        params,
        raise_on_error=False,
    )

    if approved:
        plugin.ctx.logger.info(f"LLM 判定通过好友申请: user_id={user_id} 拟定备注={remark!r}")
        if remark:
            await set_friend_remark_with_retry(plugin, user_id, remark)
        await _send_welcome(plugin, user_id)
    else:
        plugin.ctx.logger.info(f"LLM 判定拒绝好友申请: user_id={user_id}")


async def handle_auto_approve(plugin: "FriendRequestHandlerPlugin", user_id: str, flag: str, comment: str) -> None:
    remark = ""
    if plugin.config.strategy.auto_remark:
        remark = extract_remark_from_comment(comment)
        if not remark:
            remark = await _get_nickname(plugin, user_id)

    params: Dict[str, Any] = {"flag": flag, "approve": True}
    if remark:
        params["remark"] = remark

    await plugin._call_napcat(
        "set_friend_add_request",
        params,
        raise_on_error=False,
    )
    plugin.ctx.logger.info(f"自动通过好友申请: user_id={user_id} 拟定备注={remark!r}")

    if remark:
        await set_friend_remark_with_retry(plugin, user_id, remark)

    admin_qqs = plugin._normalized_admin_qqs()
    if admin_qqs:
        info_text = await _build_info_only_text(plugin, user_id, comment)
        if remark:
            info_text += f"\n已设置备注: {remark}"
        for admin_qq in admin_qqs:
            await plugin._send_private_notice(admin_qq, user_id, info_text)

    await _send_welcome(plugin, user_id)


# ---- 内部辅助 ----


async def _call_llm(plugin: "FriendRequestHandlerPlugin", prompt: str) -> tuple[bool, str]:
    model_name = (plugin.config.strategy.model_name or "").strip()
    try:
        kwargs: Dict[str, Any] = {"prompt": prompt, "temperature": 0.3, "max_tokens": 64}
        if model_name:
            # MaiBot 1.2.5 起 model 会被宿主当作具体模型名解析，任务名必须走 task_name
            kwargs["task_name"] = model_name
        result = await plugin.ctx.llm.generate(**kwargs)
    except Exception as e:
        plugin.ctx.logger.error(f"LLM 调用异常: {e}", exc_info=True)
        return False, ""
    if not isinstance(result, dict) or not result.get("success"):
        plugin.ctx.logger.warning(f"LLM 返回失败: {result}")
        return False, ""
    return True, str(result.get("response", "")).strip()


async def _generate_remark(plugin: "FriendRequestHandlerPlugin", info_text: str) -> str:
    full_prompt = f"{REMARK_PROMPT}\n\n申请人信息：\n{info_text}"
    ok, reply = await _call_llm(plugin, full_prompt)
    if not ok:
        return ""
    remark = reply.strip().strip('"').strip("'").strip("「」").strip()
    if len(remark) > 16:
        remark = remark[:16]
    return remark


async def _get_nickname(plugin: "FriendRequestHandlerPlugin", user_id: str) -> str:
    info = await plugin._call_napcat(
        "get_stranger_info",
        {"user_id": int(user_id) if user_id.isdigit() else user_id, "no_cache": True},
    )
    info_data = info.get("data", info) if isinstance(info, dict) else {}
    if not isinstance(info_data, dict):
        return ""
    return str(info_data.get("nickname") or "").strip()


async def _send_welcome(plugin: "FriendRequestHandlerPlugin", user_id: str) -> None:
    await asyncio.sleep(1.0)
    messages = [m.strip() for m in (plugin.config.welcome.messages or []) if m.strip()]
    for i, msg in enumerate(messages):
        try:
            await plugin._send_private_text(user_id, msg)
        except Exception as exc:
            plugin.ctx.logger.warning(f"发送欢迎语失败: {exc}")
        if i < len(messages) - 1:
            await asyncio.sleep(0.5)


def _format_sex(value: Any) -> str:
    text = str(value or "").strip().lower()
    return {"male": "男", "female": "女", "0": "男", "1": "女"}.get(text, "")


async def _build_applicant_info_text(plugin: "FriendRequestHandlerPlugin", user_id: str, comment: str) -> str:
    # 故意只注入对判定有用的字段：验证消息 > 个性签名 > 昵称 > QQ 号。
    # 不注入性别/年龄/等级/登录天数——这些字段对"是否通过"判定无意义，
    # 反而会被 LLM 当成"风险评分"，导致 LLM 偏保守。
    info = await plugin._call_napcat(
        "get_stranger_info",
        {"user_id": int(user_id) if user_id.isdigit() else user_id, "no_cache": True},
    )
    info_data = info.get("data", info) if isinstance(info, dict) else {}
    if not isinstance(info_data, dict):
        info_data = {}

    lines: List[str] = []

    def add(label: str, value: Any) -> None:
        text = "" if value is None else str(value).strip()
        if not text or text in {"0", "0.0", "unknown"}:
            return
        lines.append(f"{label}: {text}")

    # 验证消息放最前面：最关键、且无论空否都应明确告诉 LLM 是否存在
    add("验证消息", comment)
    add("QQ号", user_id)
    add("昵称", info_data.get("nickname"))
    add("个性签名", info_data.get("long_nick") or info_data.get("longNick") or info_data.get("sign"))
    return "\n".join(lines)


async def _build_info_only_text(plugin: "FriendRequestHandlerPlugin", user_id: str, comment: str) -> str:
    info = await plugin._call_napcat(
        "get_stranger_info",
        {"user_id": int(user_id) if user_id.isdigit() else user_id, "no_cache": True},
    )
    info_data = info.get("data", info) if isinstance(info, dict) else {}
    if not isinstance(info_data, dict):
        info_data = {}

    lines: List[str] = ["✅ 已自动通过好友申请"]

    def add(label: str, value: Any) -> None:
        text = "" if value is None else str(value).strip()
        if not text or text in {"0", "0.0", "unknown"}:
            return
        lines.append(f"{label}: {text}")

    add("QQ号", user_id)
    add("昵称", info_data.get("nickname"))
    add("性别", _format_sex(info_data.get("sex")))
    add("年龄", info_data.get("age"))
    add("等级", info_data.get("level") or info_data.get("qqLevel"))
    add("个性签名", info_data.get("long_nick") or info_data.get("longNick") or info_data.get("sign"))
    if comment:
        lines.append(f"验证消息: {comment}")
    return "\n".join(lines)


async def build_notice_text(plugin: "FriendRequestHandlerPlugin", user_id: str, fallback_nickname: str, comment: str) -> str:
    info = await plugin._call_napcat(
        "get_stranger_info",
        {"user_id": int(user_id) if user_id.isdigit() else user_id, "no_cache": True},
    )
    info_data = info.get("data", info) if isinstance(info, dict) else info
    if not isinstance(info_data, dict):
        info_data = {}

    lines: List[str] = ["📩 收到新的好友申请"]

    def add(label: str, value: Any) -> None:
        text = "" if value is None else str(value).strip()
        if not text or text in {"0", "0.0", "unknown"}:
            return
        lines.append(f"{label}: {text}")

    nickname = str(info_data.get("nickname") or fallback_nickname or "").strip()
    add("QQ号", user_id)
    add("昵称", nickname)
    add("性别", _format_sex(info_data.get("sex")))
    add("年龄", info_data.get("age"))
    add("等级", info_data.get("level") or info_data.get("qqLevel"))
    add("生日", _format_birthday(info_data))
    add("所在地", _format_location(info_data))
    add("国家", info_data.get("country"))
    add("学校", info_data.get("school") or info_data.get("eduInfo"))
    add("个性签名", info_data.get("long_nick") or info_data.get("longNick") or info_data.get("sign"))
    add("邮箱", info_data.get("email"))
    add("电话", info_data.get("phoneNum") or info_data.get("phone"))
    add("vip等级", info_data.get("vip_level") or info_data.get("vipLevel"))
    add("登录天数", info_data.get("login_days") or info_data.get("loginDays"))
    if comment:
        lines.append(f"验证消息: {comment}")

    lines.append("")
    lines.append(f"通过申请请发送：/同意 {user_id} [备注]")
    lines.append(f"拒绝申请请发送：/拒绝 {user_id}")
    return "\n".join(lines)


def _format_birthday(info: Dict[str, Any]) -> str:
    year = info.get("birthday_year") or info.get("birthdayYear") or info.get("year")
    month = info.get("birthday_month") or info.get("birthdayMonth") or info.get("month")
    day = info.get("birthday_day") or info.get("birthdayDay") or info.get("day")
    parts = [str(p).strip() for p in (year, month, day) if p not in (None, "", 0, "0")]
    return "-".join(parts)


def _format_location(info: Dict[str, Any]) -> str:
    parts = [
        str(info.get(key) or "").strip()
        for key in ("country", "province", "city", "area")
    ]
    return " ".join([p for p in parts if p and p.lower() != "unknown"])