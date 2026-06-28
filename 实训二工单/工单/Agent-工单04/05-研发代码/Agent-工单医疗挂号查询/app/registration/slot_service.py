"""号源查询与库存处理。"""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.common.error_handler import SlotUnavailableError
from app.registration.doctor_service import DoctorService
from app.registration.models import DoctorSchedule, ScheduleStatus, SlotType


class SlotService:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.doctor_service = DoctorService(db)

    def query_slots(
        self,
        *,
        department_name: str | None = None,
        doctor_name: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        exact_date: date | None = None,
        exact_time: time | None = None,
        slot_type: str | None = None,
        only_available: bool = True,
    ) -> list[DoctorSchedule]:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        conditions = [DoctorSchedule.status == ScheduleStatus.OPEN.value]
        if only_available:
            conditions.append(DoctorSchedule.remain_count > 0)
        if department_name:
            department = self.doctor_service.get_department_by_name(department_name)
            conditions.append(DoctorSchedule.department_id == department.id)
        if doctor_name:
            doctor = self.doctor_service.get_doctor_by_name(doctor_name)
            conditions.append(DoctorSchedule.doctor_id == doctor.id)
        if exact_date:
            conditions.append(DoctorSchedule.work_date == exact_date)
        else:
            if start_date:
                conditions.append(DoctorSchedule.work_date >= start_date)
            if end_date:
                conditions.append(DoctorSchedule.work_date <= end_date)
        if exact_time:
            conditions.append(DoctorSchedule.start_time == exact_time)
        if slot_type:
            conditions.append(DoctorSchedule.slot_type == self.normalize_slot_type(slot_type))

        return list(
            self.db.scalars(
                select(DoctorSchedule)
                .options(joinedload(DoctorSchedule.doctor), joinedload(DoctorSchedule.department))
                .where(and_(*conditions))
                .order_by(DoctorSchedule.work_date.asc(), DoctorSchedule.start_time.asc())
            )
        )

    def find_schedule_or_raise(self, **kwargs: object) -> DoctorSchedule:
        schedules = self.query_slots(**kwargs)
        if schedules:
            return schedules[0]
        suggestions = self.query_slots(
            department_name=kwargs.get("department_name"),
            doctor_name=kwargs.get("doctor_name"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
            slot_type=kwargs.get("slot_type"),
            only_available=True,
        )
        suggestion_text = [
            f"{item.work_date.isoformat()} {item.start_time.strftime('%H:%M')} {item.doctor.name}"
            for item in suggestions[:3]
        ]
        raise SlotUnavailableError(
            "当前时间无可用号源，并推荐最近可用号源。",
            code="SLOT_UNAVAILABLE",
            data={"suggestions": suggestion_text},
        )

    @staticmethod
    def normalize_slot_type(slot_type: str | None) -> str | None:
        if not slot_type:
            return None
        if slot_type in {SlotType.EXPERT.value, "专家", "专家号"}:
            return SlotType.EXPERT.value
        return SlotType.NORMAL.value
