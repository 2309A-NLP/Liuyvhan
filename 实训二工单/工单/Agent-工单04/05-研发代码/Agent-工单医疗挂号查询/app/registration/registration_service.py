"""挂号、取消、查询业务逻辑。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, joinedload

from app.common.error_handler import DatabaseOperationError, SlotUnavailableError, TimeConflictError
from app.common.permission_service import PermissionService
from app.registration.models import Appointment, AppointmentStatus, Doctor, DoctorSchedule, Patient
from app.registration.slot_service import SlotService


class RegistrationService:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.permission_service = PermissionService(db)
        self.slot_service = SlotService(db)

    def list_appointments(self, user_id: int) -> list[Appointment]:
        self.permission_service.get_user(user_id)
        return list(
            self.db.scalars(
                select(Appointment)
                .options(
                    joinedload(Appointment.patient),
                    joinedload(Appointment.doctor),
                    joinedload(Appointment.schedule).joinedload(DoctorSchedule.department),
                )
                .where(Appointment.user_id == user_id)
                .order_by(Appointment.appointment_time.asc())
            )
        )

    def book_appointment(
        self,
        *,
        user_id: int,
        patient_name: str,
        department_name: str | None,
        doctor_name: str | None,
        exact_date,
        exact_time,
        start_date,
        end_date,
        slot_type: str | None,
    ) -> dict[str, object]:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        patient = self.permission_service.ensure_patient_access(user_id, patient_name)
        schedule = self.slot_service.find_schedule_or_raise(
            department_name=department_name,
            doctor_name=doctor_name,
            exact_date=exact_date,
            exact_time=exact_time,
            start_date=start_date,
            end_date=end_date,
            slot_type=slot_type,
            only_available=True,
        )
        appointment_time = datetime.combine(schedule.work_date, schedule.start_time)
        self._ensure_no_time_conflict(user_id=user_id, patient=patient, appointment_time=appointment_time)

        try:
            if schedule.remain_count <= 0:
                raise SlotUnavailableError("当前时间无可用号源，并推荐最近可用号源。", code="SLOT_UNAVAILABLE")
            schedule.remain_count -= 1
            appointment = Appointment(
                user_id=user_id,
                patient_id=patient.id,
                doctor_id=schedule.doctor_id,
                department_id=schedule.department_id,
                schedule_id=schedule.id,
                appointment_time=appointment_time,
                slot_type=schedule.slot_type,
                status=AppointmentStatus.BOOKED.value,
            )
            self.db.add(appointment)
            self.db.commit()
            self.db.refresh(appointment)
            self.db.refresh(schedule)
        except Exception as exc:
            self.db.rollback()
            if isinstance(exc, (SlotUnavailableError, TimeConflictError)):
                raise
            raise DatabaseOperationError("系统繁忙，请稍后重试。", code="DB_WRITE_FAILED") from exc

        return {
            "appointment_id": appointment.id,
            "patient_name": patient.name,
            "doctor_name": schedule.doctor.name,
            "department_name": schedule.department.name,
            "appointment_time": appointment_time.strftime("%Y-%m-%d %H:%M"),
            "slot_type": schedule.slot_type,
            "remain_count": schedule.remain_count,
        }

    def cancel_appointment(
        self,
        *,
        user_id: int,
        department_name: str | None,
        doctor_name: str | None,
        exact_date,
        slot_type: str | None,
        patient_name: str | None,
    ) -> dict[str, object]:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        appointment = self._find_appointment(
            user_id=user_id,
            department_name=department_name,
            doctor_name=doctor_name,
            exact_date=exact_date,
            slot_type=slot_type,
            patient_name=patient_name or "本人",
        )
        self.permission_service.ensure_appointment_access(user_id, appointment)

        try:
            appointment.status = AppointmentStatus.CANCELLED.value
            appointment.cancelled_at = datetime.now()
            appointment.schedule.remain_count += 1
            self.db.commit()
            self.db.refresh(appointment)
        except Exception as exc:
            self.db.rollback()
            raise DatabaseOperationError("系统繁忙，请稍后重试。", code="DB_CANCEL_FAILED") from exc

        return {
            "appointment_id": appointment.id,
            "patient_name": appointment.patient.name,
            "doctor_name": appointment.doctor.name,
            "department_name": appointment.schedule.department.name,
            "appointment_time": appointment.appointment_time.strftime("%Y-%m-%d %H:%M"),
            "status": appointment.status,
            "remain_count": appointment.schedule.remain_count,
        }

    def repeat_previous_doctor(
        self,
        *,
        user_id: int,
        patient_name: str,
        department_name: str | None,
        slot_type: str | None,
        start_date,
        end_date,
    ) -> dict[str, object]:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        patient = self.permission_service.ensure_patient_access(user_id, patient_name)
        history_items = list(
            self.db.scalars(
                select(Appointment)
                .options(
                    joinedload(Appointment.doctor).joinedload(Doctor.department),
                    joinedload(Appointment.patient),
                    joinedload(Appointment.schedule).joinedload(DoctorSchedule.department),
                )
                .where(Appointment.user_id == user_id)
                .order_by(Appointment.created_at.desc())
            )
        )
        selected = None
        for item in history_items:
            matches_department = True
            if department_name:
                matches_department = item.schedule.department.name == department_name
            if matches_department and item.doctor.is_expert:
                selected = item
                break
        if not selected:
            raise SlotUnavailableError("未找到可复用的历史专家挂号记录。", code="HISTORY_DOCTOR_NOT_FOUND")

        return self.book_appointment(
            user_id=user_id,
            patient_name=patient.name,
            department_name=selected.schedule.department.name,
            doctor_name=selected.doctor.name,
            exact_date=None,
            exact_time=None,
            start_date=start_date,
            end_date=end_date,
            slot_type=slot_type or selected.slot_type,
        )

    def _ensure_no_time_conflict(self, *, user_id: int, patient: Patient, appointment_time: datetime) -> None:
        existing = self.db.scalar(
            select(Appointment).where(
                Appointment.user_id == user_id,
                Appointment.patient_id == patient.id,
                Appointment.appointment_time == appointment_time,
                Appointment.status == AppointmentStatus.BOOKED.value,
            )
        )
        if existing:
            raise TimeConflictError("当前时间已有预约，不能重复挂号。", code="TIME_CONFLICT")

    def _find_appointment(
        self,
        *,
        user_id: int,
        department_name: str | None,
        doctor_name: str | None,
        exact_date,
        slot_type: str | None,
        patient_name: str | None,
    ) -> Appointment:
        appointments = list(
            self.db.scalars(
                select(Appointment)
                .options(
                    joinedload(Appointment.patient),
                    joinedload(Appointment.doctor),
                    joinedload(Appointment.schedule).joinedload(DoctorSchedule.department),
                )
                .where(and_(Appointment.user_id == user_id, Appointment.status == AppointmentStatus.BOOKED.value))
                .order_by(Appointment.appointment_time.desc())
            )
        )
        for item in appointments:
            if patient_name and item.patient.name != patient_name:
                continue
            if department_name and item.schedule.department.name != department_name:
                continue
            if doctor_name and item.doctor.name != doctor_name:
                continue
            if exact_date and item.appointment_time.date() != exact_date:
                continue
            if slot_type and item.slot_type != self.slot_service.normalize_slot_type(slot_type):
                continue
            return item
        raise SlotUnavailableError("未找到可取消的挂号记录。", code="APPOINTMENT_NOT_FOUND")
