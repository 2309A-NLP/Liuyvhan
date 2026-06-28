"""医生与排班查询。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.common.error_handler import DepartmentNotFoundError, DoctorNotFoundError, PermissionDeniedError
from app.registration.models import Department, Doctor, DoctorSchedule, UserRole


class DoctorService:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_department_names(self) -> list[str]:
        return list(self.db.scalars(select(Department.name).order_by(Department.id.asc())))

    def get_department_by_name(self, name: str) -> Department:
        department = self.db.scalar(
            select(Department).where(
                or_(
                    Department.name == name,
                    Department.alias.like(f"%{name}%"),
                )
            )
        )
        if not department:
            raise DepartmentNotFoundError(
                "未找到该科室，并返回当前可选科室列表。",
                code="DEPARTMENT_NOT_FOUND",
                data={"available_departments": self.list_department_names()},
            )
        return department

    def get_doctor_by_name(self, doctor_name: str) -> Doctor:
        doctor = self.db.scalar(select(Doctor).where(Doctor.name == doctor_name))
        if not doctor:
            raise DoctorNotFoundError(
                "未找到该医生，并提示用户更换医生或查询科室号源。",
                code="DOCTOR_NOT_FOUND",
            )
        return doctor

    def list_doctor_schedules(
        self,
        *,
        doctor_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
        requester_role: str | None = None,
        requester_doctor_name: str | None = None,
    ) -> list[DoctorSchedule]:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        doctor = self.get_doctor_by_name(doctor_name)
        if requester_role == UserRole.DOCTOR.value and requester_doctor_name and requester_doctor_name != doctor_name:
            raise PermissionDeniedError("当前用户无权操作该患者或该挂号记录。", code="DOCTOR_SCHEDULE_DENIED")

        conditions = [DoctorSchedule.doctor_id == doctor.id]
        if start_date:
            conditions.append(DoctorSchedule.work_date >= start_date)
        if end_date:
            conditions.append(DoctorSchedule.work_date <= end_date)

        return list(
            self.db.scalars(
                select(DoctorSchedule)
                .options(joinedload(DoctorSchedule.doctor), joinedload(DoctorSchedule.department))
                .where(and_(*conditions))
                .order_by(DoctorSchedule.work_date.asc(), DoctorSchedule.start_time.asc())
            )
        )
