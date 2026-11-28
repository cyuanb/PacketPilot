"""Reconstruct completed conversational turns without assistant tool-call fragments."""

from sqlalchemy import select

from .models import Message, Run


def conversation_history(db, case_id, exclude_run_id, budget=32000):
    runs = list(
        db.scalars(
            select(Run)
            .where(
                Run.case_id == case_id,
                Run.id != exclude_run_id,
                Run.status.in_(["completed", "waiting_for_input"]),
                Run.kind.in_(["chat", "extract", "check"]),
            )
            .order_by(Run.created_at.desc(), Run.id.desc())
            .limit(12)
        )
    )
    turns = []
    truncated = False
    for run in runs:
        messages = list(
            db.scalars(
                select(Message)
                .where(Message.run_id == run.id, Message.case_id == case_id)
                .order_by(Message.created_at, Message.id)
            )
        )
        users = [m.content for m in messages if m.role == "user" and m.content]
        answer = run.result.get("answer")
        if not answer:
            answers = [
                m.content
                for m in messages
                if m.role == "assistant" and m.content and not (m.data or {}).get("tool_calls")
            ]
            answer = answers[-1] if answers else ""
        turn = [{"role": "user", "content": text} for text in users]
        if answer:
            # Non-chat runs still need an explicit user request to form a complete context turn.
            if not turn:
                turn = [
                    {
                        "role": "user",
                        "content": "请提取当前通知要求" if run.kind == "extract" else "请预检当前申请材料",
                    }
                ]
            turn.append({"role": "assistant", "content": answer})
        cost = sum(len(m["content"]) for m in turn)
        if cost > budget:
            truncated = True
            break
        budget -= cost
        turns.append(turn)
    return [m for turn in reversed(turns) for m in turn], {
        "turns": len(turns),
        "window_limited": truncated or len(runs) == 12,
        "policy": "最近已完成会话轮次，最多12轮/32000字符；较早信息可按关键词回查。用户陈述不自动成为已确认背景。",
    }
