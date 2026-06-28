"""API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.agent.agent_service import AgentService
from app.common.log_service import LogService
from app.common.permission_service import PermissionService
from app.common.response_schema import APIResponse
from app.database import get_db
from app.registration.doctor_service import DoctorService
from app.registration.registration_service import RegistrationService
from app.registration.schemas import AgentChatRequest
from app.seed_data import init_database, seed_database

router = APIRouter()


@router.post("/agent/chat", response_model=APIResponse)
def agent_chat(request: AgentChatRequest, db: Session = Depends(get_db)) -> APIResponse:
    return AgentService(db).chat(request)


@router.get("/appointments/{user_id}", response_model=APIResponse)
def get_appointments(user_id: int, db: Session = Depends(get_db)) -> APIResponse:
    service = RegistrationService(db)
    items = service.list_appointments(user_id)
    data = {
        "appointments": [
            {
                "id": item.id,
                "patient_name": item.patient.name,
                "doctor_name": item.doctor.name,
                "department_name": item.schedule.department.name,
                "appointment_time": item.appointment_time.strftime("%Y-%m-%d %H:%M"),
                "slot_type": item.slot_type,
                "status": item.status,
            }
            for item in items
        ]
    }
    return APIResponse(message="查询挂号记录成功。", data=data, trace=["已查询用户挂号记录。"])


@router.get("/doctors/{doctor_name}/schedules", response_model=APIResponse)
def get_doctor_schedules(
    doctor_name: str,
    user_id: int | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> APIResponse:
    permission_service = PermissionService(db)
    requester_role = None
    requester_doctor_name = None
    if user_id is not None:
        user = permission_service.get_user(user_id)
        requester_role = user.role
        requester_doctor_name = user.username if user.role == "doctor" else None
    from datetime import datetime

    parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    items = DoctorService(db).list_doctor_schedules(
        doctor_name=doctor_name,
        start_date=parsed_start,
        end_date=parsed_end,
        requester_role=requester_role,
        requester_doctor_name=requester_doctor_name,
    )
    data = {
        "schedules": [
            {
                "id": item.id,
                "doctor_name": item.doctor.name,
                "department_name": item.department.name,
                "work_date": item.work_date.isoformat(),
                "start_time": item.start_time.strftime("%H:%M"),
                "end_time": item.end_time.strftime("%H:%M"),
                "slot_type": item.slot_type,
                "remain_count": item.remain_count,
                "status": item.status,
            }
            for item in items
        ]
    }
    return APIResponse(message="查询医生坐诊时间成功。", data=data, trace=["已查询医生排班。"])


@router.get("/logs/{session_id}", response_model=APIResponse)
def get_logs(session_id: str, db: Session = Depends(get_db)) -> APIResponse:
    logs = LogService(db).get_logs(session_id)
    data = {
        "logs": [
            {
                "id": log.id,
                "step_name": log.step_name,
                "tool_name": log.tool_name,
                "tool_input": log.tool_input,
                "tool_output": log.tool_output,
                "status": log.status,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(sep=" ", timespec="seconds"),
            }
            for log in logs
        ]
    }
    return APIResponse(message="查询 Agent 日志成功。", data=data, trace=["已查询指定 session 的执行日志。"])


@router.post("/init-db", response_model=APIResponse)
def init_db(db: Session = Depends(get_db)) -> APIResponse:
    init_database()
    counts = seed_database(db)
    return APIResponse(message="数据库初始化完成。", data=counts, trace=["已重建数据库并写入测试数据。"])
