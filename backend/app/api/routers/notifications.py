from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func

from ...api.deps import get_current_user, get_db_session
from ...db.models import User, Notification
from ...schemas import NotificationRead, NotificationCountResponse

router = APIRouter()


@router.get("/", response_model=List[NotificationRead])
def get_notifications(
    limit: int = 20,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Get notifications for the current user"""
    query = select(Notification).where(Notification.user_id == current_user.id)
    
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    
    notifications = session.exec(query).all()
    
    return [
        NotificationRead(
            id=n.id,
            user_id=n.user_id,
            type=n.type,
            title=n.title,
            message=n.message,
            team_id=n.team_id,
            decision_run_id=n.decision_run_id,
            is_read=n.is_read,
            created_at=n.created_at.isoformat(),
        )
        for n in notifications
    ]


@router.get("/unread-count", response_model=NotificationCountResponse)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Get count of unread notifications"""
    count = session.exec(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False)
    ).one()
    
    return NotificationCountResponse(unread_count=count)


@router.post("/{notification_id}/mark-read")
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Mark a notification as read"""
    notification = session.exec(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    
    notification.is_read = True
    session.add(notification)
    session.commit()
    
    return {"success": True}


@router.post("/mark-all-read")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """Mark all notifications as read for the current user"""
    notifications = session.exec(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    ).all()
    
    for notification in notifications:
        notification.is_read = True
        session.add(notification)
    
    session.commit()
    
    return {"success": True, "marked_count": len(notifications)}
