"""初始化测试数据。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.registration.models import (
    AgentLog,
    AgentTaskState,
    Appointment,
    AppointmentStatus,
    Department,
    Doctor,
    DoctorSchedule,
    Patient,
    ScheduleStatus,
    SlotType,
    User,
    UserRole,
)


def init_database() -> None:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_database(db: Session) -> dict[str, int]:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    db.query(AgentLog).delete()
    db.query(AgentTaskState).delete()
    db.query(Appointment).delete()
    db.query(DoctorSchedule).delete()
    db.query(Doctor).delete()
    db.query(Department).delete()
    db.query(Patient).delete()
    db.query(User).delete()
    db.commit()

    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()) or 7)
    current_week_wednesday = today - timedelta(days=today.weekday() - 2)
    last_wednesday = current_week_wednesday - timedelta(days=7)

    users = [
        User(id=1, username="李明", phone="13800000001", role=UserRole.PATIENT_USER.value),
        User(id=2, username="张建国", phone="13800000002", role=UserRole.DOCTOR.value),
        User(id=3, username="管理员", phone="13800000003", role=UserRole.ADMIN.value),
    ]
    db.add_all(users)
    db.flush()

    patients = [
        Patient(user_id=1, name="本人", relation="self", age=32, gender="男", id_card_no="ID001"),
        Patient(user_id=1, name="大宝", relation="child", age=7, gender="男", id_card_no="ID002"),
        Patient(user_id=1, name="二宝", relation="child", age=4, gender="女", id_card_no="ID003"),
    ]
    db.add_all(patients)
    db.flush()

    departments = {
        "儿科": Department(name="儿科", alias="小儿科", description="儿童常见病"),
        "牙科": Department(name="牙科", alias="口腔科", description="口腔与牙齿"),
        "眼科": Department(name="眼科", alias="视光科", description="眼部诊疗"),
        "皮肤科": Department(name="皮肤科", alias="皮肤门诊", description="皮肤问题"),
        "消化内科": Department(name="消化内科", alias="消化科", description="胃肠疾病"),
    }
    db.add_all(departments.values())
    db.flush()

    doctors = {
        "张建国": Doctor(
            name="张建国",
            department_id=departments["儿科"].id,
            title="主任医师",
            specialty="儿科疑难杂症",
            is_expert=True,
        ),
        "儿科专家医生": Doctor(
            name="儿科专家医生",
            department_id=departments["儿科"].id,
            title="副主任医师",
            specialty="儿童发热与呼吸道",
            is_expert=True,
        ),
        "牙科医生": Doctor(
            name="牙科医生",
            department_id=departments["牙科"].id,
            title="主治医师",
            specialty="龋齿与洁牙",
            is_expert=False,
        ),
        "眼科专家医生": Doctor(
            name="眼科专家医生",
            department_id=departments["眼科"].id,
            title="主任医师",
            specialty="眼科专家门诊",
            is_expert=True,
        ),
        "皮肤科医生": Doctor(
            name="皮肤科医生",
            department_id=departments["皮肤科"].id,
            title="主治医师",
            specialty="湿疹过敏",
            is_expert=False,
        ),
        "消化内科普通医生": Doctor(
            name="消化内科普通医生",
            department_id=departments["消化内科"].id,
            title="住院医师",
            specialty="腹痛腹泻",
            is_expert=False,
        ),
    }
    db.add_all(doctors.values())
    db.flush()

    schedules = [
        DoctorSchedule(
            doctor_id=doctors["儿科专家医生"].id,
            department_id=departments["儿科"].id,
            work_date=today,
            start_time=time(14, 0),
            end_time=time(14, 30),
            slot_type=SlotType.EXPERT.value,
            total_count=5,
            remain_count=3,
            status=ScheduleStatus.OPEN.value,
        ),
        DoctorSchedule(
            doctor_id=doctors["皮肤科医生"].id,
            department_id=departments["皮肤科"].id,
            work_date=today + timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(9, 30),
            slot_type=SlotType.NORMAL.value,
            total_count=5,
            remain_count=2,
            status=ScheduleStatus.OPEN.value,
        ),
        DoctorSchedule(
            doctor_id=doctors["牙科医生"].id,
            department_id=departments["牙科"].id,
            work_date=today + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(10, 30),
            slot_type=SlotType.NORMAL.value,
            total_count=4,
            remain_count=1,
            status=ScheduleStatus.OPEN.value,
        ),
        DoctorSchedule(
            doctor_id=doctors["牙科医生"].id,
            department_id=departments["牙科"].id,
            work_date=today + timedelta(days=3),
            start_time=time(15, 0),
            end_time=time(15, 30),
            slot_type=SlotType.NORMAL.value,
            total_count=4,
            remain_count=2,
            status=ScheduleStatus.OPEN.value,
        ),
        DoctorSchedule(
            doctor_id=doctors["张建国"].id,
            department_id=departments["儿科"].id,
            work_date=next_monday,
            start_time=time(9, 0),
            end_time=time(11, 0),
            slot_type=SlotType.EXPERT.value,
            total_count=6,
            remain_count=4,
            status=ScheduleStatus.OPEN.value,
        ),
        DoctorSchedule(
            doctor_id=doctors["张建国"].id,
            department_id=departments["儿科"].id,
            work_date=next_monday + timedelta(days=2),
            start_time=time(14, 0),
            end_time=time(16, 0),
            slot_type=SlotType.EXPERT.value,
            total_count=6,
            remain_count=4,
            status=ScheduleStatus.OPEN.value,
        ),
        DoctorSchedule(
            doctor_id=doctors["消化内科普通医生"].id,
            department_id=departments["消化内科"].id,
            work_date=last_wednesday,
            start_time=time(10, 0),
            end_time=time(10, 30),
            slot_type=SlotType.NORMAL.value,
            total_count=5,
            remain_count=4,
            status=ScheduleStatus.OPEN.value,
        ),
        DoctorSchedule(
            doctor_id=doctors["眼科专家医生"].id,
            department_id=departments["眼科"].id,
            work_date=today - timedelta(days=14),
            start_time=time(11, 0),
            end_time=time(11, 30),
            slot_type=SlotType.EXPERT.value,
            total_count=5,
            remain_count=4,
            status=ScheduleStatus.OPEN.value,
        ),
        DoctorSchedule(
            doctor_id=doctors["眼科专家医生"].id,
            department_id=departments["眼科"].id,
            work_date=today + timedelta(days=2),
            start_time=time(10, 0),
            end_time=time(10, 30),
            slot_type=SlotType.EXPERT.value,
            total_count=5,
            remain_count=3,
            status=ScheduleStatus.OPEN.value,
        ),
        DoctorSchedule(
            doctor_id=doctors["牙科医生"].id,
            department_id=departments["牙科"].id,
            work_date=today + timedelta(days=2),
            start_time=time(8, 0),
            end_time=time(8, 30),
            slot_type=SlotType.NORMAL.value,
            total_count=1,
            remain_count=0,
            status=ScheduleStatus.OPEN.value,
        ),
    ]
    db.add_all(schedules)
    db.flush()

    patient_self = next(item for item in patients if item.name == "本人")
    past_digestive = next(
        item for item in schedules if item.department_id == departments["消化内科"].id and item.work_date == last_wednesday
    )
    past_eye = next(item for item in schedules if item.doctor_id == doctors["眼科专家医生"].id and item.work_date < today)
    past_digestive.remain_count -= 1
    past_eye.remain_count -= 1

    db.add_all(
        [
            Appointment(
                user_id=1,
                patient_id=patient_self.id,
                doctor_id=doctors["消化内科普通医生"].id,
                department_id=departments["消化内科"].id,
                schedule_id=past_digestive.id,
                appointment_time=datetime.combine(past_digestive.work_date, past_digestive.start_time),
                slot_type=SlotType.NORMAL.value,
                status=AppointmentStatus.BOOKED.value,
            ),
            Appointment(
                user_id=1,
                patient_id=patient_self.id,
                doctor_id=doctors["眼科专家医生"].id,
                department_id=departments["眼科"].id,
                schedule_id=past_eye.id,
                appointment_time=datetime.combine(past_eye.work_date, past_eye.start_time),
                slot_type=SlotType.EXPERT.value,
                status=AppointmentStatus.BOOKED.value,
            ),
        ]
    )
    db.commit()

    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "patients": db.scalar(select(func.count()).select_from(Patient)) or 0,
        "departments": db.scalar(select(func.count()).select_from(Department)) or 0,
        "doctors": db.scalar(select(func.count()).select_from(Doctor)) or 0,
        "schedules": db.scalar(select(func.count()).select_from(DoctorSchedule)) or 0,
        "appointments": db.scalar(select(func.count()).select_from(Appointment)) or 0,
    }
