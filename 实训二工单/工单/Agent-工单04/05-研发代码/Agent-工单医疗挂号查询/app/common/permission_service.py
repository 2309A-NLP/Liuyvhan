"""通用权限控制。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.error_handler import PermissionDeniedError, UserNotFoundError
from app.registration.models import Appointment, Patient, User, UserRole


class PermissionService:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user(self, user_id: int) -> User:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        user = self.db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise UserNotFoundError("未找到当前用户，请检查 user_id。", code="INVALID_USER_ID")
        return user

    def ensure_patient_access(self, user_id: int, patient_name: str) -> Patient:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        user = self.get_user(user_id)
        patient = self.db.scalar(
            select(Patient).where(Patient.user_id == user_id, Patient.name == patient_name)
        )
        if user.role == UserRole.ADMIN:
            patient = patient or self.db.scalar(select(Patient).where(Patient.name == patient_name))
        if not patient:
            raise PermissionDeniedError(
                "当前用户无权操作该患者或该挂号记录。",
                code="PATIENT_ACCESS_DENIED",
            )
        return patient

    def ensure_appointment_access(self, user_id: int, appointment: Appointment) -> None:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        user = self.get_user(user_id)
        if user.role == UserRole.ADMIN:
            return
        if appointment.user_id != user_id:
            raise PermissionDeniedError(
                "当前用户无权操作该患者或该挂号记录。",
                code="APPOINTMENT_ACCESS_DENIED",
            )
