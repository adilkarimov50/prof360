"""ИИ-консультант: чат с обязательной правовой привязкой и логированием."""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai.consultant import ask, ask_stream
from app.ai.llm import info, is_available
from app.core.audit import log_action
from app.core.db import SessionLocal, get_db
from app.core.deps import abac_district_filter, client_ip, get_current_user
from app.models.audit import AiChatLog
from app.models.user import User
from app.schemas import AiChatRequest
from app.core.rbac import allow_pii as rbac_allow_pii

router = APIRouter(prefix="/ai", tags=["ai"])


def _allow_pii(user: User) -> bool:
    return rbac_allow_pii(user)


@router.get("/status")
def status(user: User = Depends(get_current_user)):
    return {"llm_available": is_available(), **info()}


@router.post("/chat")
def chat(data: AiChatRequest, request: Request,
         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # ИИ получает данные только в пределах прав пользователя
    allow_pii = _allow_pii(user)
    history = [{"role": t.role, "content": t.content} for t in (data.history or [])]
    district = abac_district_filter(user)
    result = ask(
        db, data.question,
        context_type=data.context_type, context_id=data.context_id,
        allow_pii=allow_pii, history=history, abac_district=district,
    )

    # логирование каждого ответа ИИ
    db.add(AiChatLog(
        user_id=user.id, username=user.username, question=data.question,
        answer=result["answer"], used_norm_ids=[s["norm_id"] for s in result["sources"]],
        context_type=data.context_type, context_id=data.context_id,
        confidence=result["confidence"],
    ))
    db.commit()
    log_action(db, action="ai_chat", user=user, ip=client_ip(request),
               details={"context": data.context_type, "confidence": result["confidence"]})
    return result


@router.post("/chat/stream")
def chat_stream(data: AiChatRequest, request: Request,
                user: User = Depends(get_current_user)):
    """Потоковый ответ ИИ (SSE). Текст печатается в реальном времени, в конце — источники."""
    allow_pii = _allow_pii(user)
    history = [{"role": t.role, "content": t.content} for t in (data.history or [])]
    ip = client_ip(request)
    district = abac_district_filter(user)

    def event_source():
        # Отдельная сессия БД: генератор живёт дольше, чем зависимость запроса.
        db = SessionLocal()
        final: dict | None = None
        try:
            for event in ask_stream(
                db, data.question,
                context_type=data.context_type, context_id=data.context_id,
                allow_pii=allow_pii, history=history, abac_district=district,
            ):
                if event.get("type") == "done":
                    final = event
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            if final is not None:
                db.add(AiChatLog(
                    user_id=user.id, username=user.username, question=data.question,
                    answer=final["answer"],
                    used_norm_ids=[s["norm_id"] for s in final["sources"]],
                    context_type=data.context_type, context_id=data.context_id,
                    confidence=final["confidence"],
                ))
                db.commit()
                log_action(db, action="ai_chat", user=user, ip=ip,
                           details={"context": data.context_type,
                                    "confidence": final["confidence"], "stream": True})
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Ошибка генерации'}, ensure_ascii=False)}\n\n"
        finally:
            db.close()

    return StreamingResponse(event_source(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
