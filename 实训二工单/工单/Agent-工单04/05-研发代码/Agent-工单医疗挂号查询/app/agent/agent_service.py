"""主 Agent 编排流程。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.agent.intent_service import IntentService, resolve_date_filters, resolve_time_value
from app.common.error_handler import AgentError
from app.common.log_service import LogService
from app.common.permission_service import PermissionService
from app.common.response_schema import APIResponse
from app.common.state_service import StateService
from app.registration.doctor_service import DoctorService
from app.registration.models import TaskStateEnum
from app.registration.registration_service import RegistrationService
from app.registration.schemas import AgentChatRequest
from app.registration.slot_service import SlotService


@dataclass(slots=True)
class ToolDefinition:
    name: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    description: str


class ToolRegistry:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, name: str, handler: Callable[[dict[str, Any]], dict[str, Any]], description: str) -> None:
        self._tools[name] = ToolDefinition(name=name, handler=handler, description=description)

    def invoke(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._tools[name].handler(payload)


class AgentService:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.intent_service = IntentService()
        self.permission_service = PermissionService(db)
        self.state_service = StateService(db)
        self.log_service = LogService(db)
        self.registration_service = RegistrationService(db)
        self.slot_service = SlotService(db)
        self.doctor_service = DoctorService(db)
        self.tool_registry = ToolRegistry()
        self._register_tools()
    """!!!!!!!!对用户的数据结构做意图识别，槽位抽取!!!!!!!!!!"""
    def chat(self, request: AgentChatRequest) -> APIResponse:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""
        """request里有什么？"""
        #这里的 request 就是前端或接口传进来的请求对象  是用户请求的数据包  示例request.user_id  就是1 一次类推
        # {
        #   "user_id": 1,
        #   "session_id": "test-session-001",
        #   "query": "帮我大宝挂一个今天下午 2 点儿科专家的号"
        # }
        trace: list[str] = []
        """trace - 中文：踪迹    Agent 这次请求处理过程中，每一步做了什么"""
        # trace 是给用户/前端/验收人员看的“执行过程说明
        # [
        #     "LLM 不可用或返回异常，已切换规则解析 fallback。",
        #     "识别意图：book_appointment",
        #     "抽取槽位：{'patient_name': '大宝', 'department_name': '儿科'}",
        #     "权限校验通过：用户存在且可继续处理。",
        #     "调用工具：book_appointment",
        #     "挂号成功，号源库存已扣减。"
        # ]
        parsed = self.intent_service.parse(request.query)  # 把用户自然语言 query 交给 IntentService 去解析。
        """parsed"""
        # parsed.intent(用户要做什么) = "book_appointment"
        # parsed.slots(做这件事需要的参数) = {
        #     "patient_name": "大宝",
        #     "department_name": "儿科",
        #     "date_expr": "今天",
        #     "time_expr": "下午2点",
        #     "slot_type": "expert"
        # }
        # parsed.trace(解析过程说明) = [
        #     "LLM 不可用或返回异常，已切换规则解析 fallback。",
        #     "识别意图：book_appointment",
        #     "抽取槽位：{...}"
        # ]
        # parsed.missing_slots(缺少哪些必要信息) = []
        """intent_service.parse 逻辑  作用- 意图识别 ，抽取槽位"""
        # llm_result = self.llm_client.extract_intent_and_slots(query)
        # if llm_result:
        #     使用 LLM 结果
        # else:
        #     parsed = self._fallback_parse(query)
        # 系统会先尝试用 LLM 解析。如果 LLM 不可用或失败，就走规则解析 fallback，并把 “LLM 不可用或返回异常，已切换规则解析 fallback
        # fallback 解析里会做两件事：第一，识别意图，第二，抽取槽位

        trace.extend(parsed.trace) # 把意图识别和槽位抽取阶段产生的 trace，加入总 trace 里
        # trace 是总执行轨迹，parsed.trace 是解析阶段的轨迹，extend - 延长是把解析阶段轨迹合并进总轨迹。

        self.log_service.log_step(  # 日志信息
            user_id=request.user_id,
            session_id=request.session_id,
            query=request.query,
            intent=parsed.intent, # 记录识别出的意图
            step_name="receive_query",
            tool_name="",
            tool_input={"query": request.query},    # 问题
            tool_output={"intent": parsed.intent},  # 意图信息    intent-意图
            status="SUCCESS",
        )
        """状态管理"""
        self.state_service.upsert_state(
            user_id=request.user_id,
            session_id=request.session_id,
            query=request.query,
            intent=parsed.intent,
            slots_json=json.dumps(parsed.slots, ensure_ascii=False),
            state=TaskStateEnum.PENDING.value, # PENDING - 这个请求已经进入系统，正在等待后续处理。   PENDING - 待定
        )
        # 你可以把状态流转理解成：
        # PENDING
        # ↓
        # CHECKING
        # ↓
        # BOOKED / CANCELLED / AVAILABLE / FAILED / NEED_INFO
        #
        # 一开始设成 PENDING 的意义是：
        #
        # 先把这次 Agent 请求记录下来，表示任务已经进入处理流程，后面再根据执行结果更新为成功、失败、取消或需要补充信息。
        self.db.commit()
        """===================总结================="""
        #  用户请求进入 Agent 后，
        # 系统先创建 trace，
        # 然后解析用户 query，得到 intent 和 slots，
        # 把解析过程加入 trace，
        # 接着记录 receive_query 日志，
        # 最后把当前任务状态保存为 PENDING

        # 小节核心--chat() 一开始不是直接挂号，而是先把用户自然语言解析成 intent + slots，然后记录日志和初始状态 PENDING，为后面的权限校验和工具调用做准备
        # 在 AgentService.chat() 方法开头，系统首先创建 trace 列表，用来记录本次 Agent 请求的执行轨迹。
        # 然后调用 IntentService.parse(request.query)，对用户输入的自然语言做意图识别和槽位抽取，
        # 得到 parsed 对象。parsed 里面包含 intent、slots、trace 和 missing_slots。
        # 比如用户说“帮我大宝挂一个今天下午2点儿科专家号”，解析后 intent 是 book_appointment，
        # slots 里包含 patient_name=大宝、department_name=儿科、date_expr=今天、time_expr=下午2点、slot_type=expert。
        # 解析完成后，系统把 parsed.trace 合并到总 trace 中，然后通过 log_service 记录 receive_query 日志，
        # 保存用户原始 query 和识别出的 intent。最后通过 state_service 把本次任务状态初始化为 PENDING，表示这个请求已经进入 Agent 处理流程，但还没有真正执行挂号。


        if parsed.intent == "unknown":
            return self._need_info_response(request, parsed.intent, parsed.slots, trace, "暂时无法识别你的需求，请补充是挂号、查号源还是取消挂号。")
        if parsed.missing_slots:
            return self._need_info_response(
                request,
                parsed.intent,
                parsed.slots,
                trace,
                f"信息不足，请补充：{', '.join(parsed.missing_slots)}。",
            )
        # 如果意图不清楚，或者信息不完整，就先别调用工具

        """!!!!权限校验!!!!"""
        try:
            self.permission_service.get_user(request.user_id)  # 当前用户是否存在
            trace.append("权限校验通过：用户存在且可继续处理。")      # 它的作用是把这一步加入返回结果里的执行轨迹。
            self.state_service.upsert_state(
                user_id=request.user_id,
                session_id=request.session_id,
                query=request.query,
                intent=parsed.intent,
                slots_json=json.dumps(parsed.slots, ensure_ascii=False),
                state=TaskStateEnum.CHECKING.value,
            )
            self.db.commit()

            """!!!!!!!获取工具调用参数!!!!!!!!!"""
            tool_name, payload = self._build_tool_payload(request.user_id, parsed.intent, parsed.slots)
            # _build_tool_payload() 是把“Agent 解析结果”转换成“工具调用参数”。
            # payload 就是 Agent 调用工具时，传给工具的一包参数
            # slots 是自然语言解析结果，payload 是工具调用参数
            trace.append(f"调用工具：{tool_name}")
            self.log_service.log_step(
                user_id=request.user_id,
                session_id=request.session_id,
                query=request.query,
                intent=parsed.intent,
                step_name="tool_call",
                tool_name=tool_name,
                tool_input=payload,
                tool_output={},
                status="PENDING",
            )
            self.db.commit()
            result = self.tool_registry.invoke(tool_name, payload)
            trace.extend(result.get("trace", []))
            state = result["state"]
            self.state_service.upsert_state(
                user_id=request.user_id,
                session_id=request.session_id,
                query=request.query,
                intent=parsed.intent,
                slots_json=json.dumps(parsed.slots, ensure_ascii=False),
                state=state,
                result=result["message"],
            )
            self.log_service.log_step(
                user_id=request.user_id,
                session_id=request.session_id,
                query=request.query,
                intent=parsed.intent,
                step_name="tool_result",
                tool_name=tool_name,
                tool_input=payload,
                tool_output=result.get("data", {}),
                status="SUCCESS",
            )
            self.db.commit()
            return APIResponse(
                success=True,
                message=result["message"],
                data=result.get("data", {}),
                trace=trace,
                intent=parsed.intent,
                state=state,
            )
        except AgentError as exc:
            trace.extend(exc.trace)
            self.state_service.upsert_state(
                user_id=request.user_id,
                session_id=request.session_id,
                query=request.query,
                intent=parsed.intent,
                slots_json=json.dumps(parsed.slots, ensure_ascii=False),
                state=TaskStateEnum.FAILED.value,
                result=exc.message,
            )
            self.log_service.log_step(
                user_id=request.user_id,
                session_id=request.session_id,
                query=request.query,
                intent=parsed.intent,
                step_name="error",
                tool_name="",
                tool_input=parsed.slots,
                tool_output={},
                status="FAILED",
                error_message=exc.message,
            )
            self.db.commit()
            exc.intent = parsed.intent
            exc.state = TaskStateEnum.FAILED.value
            exc.trace = trace + exc.trace
            raise

    def _need_info_response(
        self,
        request: AgentChatRequest,
        intent: str,
        slots: dict[str, str],
        trace: list[str],
        message: str,
    ) -> APIResponse:
        self.state_service.upsert_state(
            user_id=request.user_id,
            session_id=request.session_id,
            query=request.query,
            intent=intent,
            slots_json=json.dumps(slots, ensure_ascii=False),
            state=TaskStateEnum.NEED_INFO.value,
            result=message,
        )
        self.log_service.log_step(
            user_id=request.user_id,
            session_id=request.session_id,
            query=request.query,
            intent=intent,
            step_name="need_info",
            tool_name="",
            tool_input=slots,
            tool_output={},
            status="NEED_INFO",
            error_message=message,
        )
        self.db.commit()
        return APIResponse(
            success=False,
            message=message,
            data={"slots": slots},
            trace=trace,
            intent=intent,
            state=TaskStateEnum.NEED_INFO.value,
        )
    """获取工具调用参数具体"""
    def _build_tool_payload(self, user_id: int, intent: str, slots: dict[str, str]) -> tuple[str, dict[str, Any]]:

        """解析日期"""
        start_date, end_date, exact_date = resolve_date_filters(slots.get("date_expr"))
        #  start_date, end_date, exact_date（精确时间） 为什么设置三个时间值
        #  更加适应用户查询日期语句  例如 有时候会问精确日期：今天，明天，上周三    有时候会问范围时间：上午下午最近
        """解析时间"""
        exact_time = resolve_time_value(slots.get("time_expr"))
        # 例如:slots.get("time_expr") = "下午2点"   转换成  exact_time = 14:00
        # 这一步很重要，因为数据库里一般不会存“下午2点”这种中文表达，而是存标准时间
        # 把自然语言时间变成数据库能使用的标准时间

        """组装 base_payload"""
        base_payload = {
            "user_id": user_id,
            "patient_name": slots.get("patient_name", "本人"),
            "department_name": slots.get("department_name"),
            "doctor_name": slots.get("doctor_name"),
            "start_date": start_date,
            "end_date": end_date,
            "exact_date": exact_date,
            "exact_time": exact_time,
            "slot_type": slots.get("slot_type"),
        }
        # 把分散的 slots 变成统一工具参数

        """_build_tool_payload() 内部第四步：根据 intent 选择工具名"""
        mapping = {
            "book_appointment": "book_appointment",
            "query_slots": "query_slots",
            "cancel_appointment": "cancel_appointment",
            "query_doctor_schedule": "query_doctor_schedule",
            "repeat_previous_doctor": "repeat_previous_doctor",
        }
        return mapping[intent], base_payload

    def _register_tools(self) -> None:
        self.tool_registry.register("book_appointment", self._tool_book_appointment, "预约挂号工具")
        self.tool_registry.register("query_slots", self._tool_query_slots, "查询号源工具")
        self.tool_registry.register("cancel_appointment", self._tool_cancel_appointment, "取消挂号工具")
        self.tool_registry.register("query_doctor_schedule", self._tool_query_doctor_schedule, "医生排班工具")
        self.tool_registry.register("repeat_previous_doctor", self._tool_repeat_previous_doctor, "复用历史医生工具")

    def _tool_book_appointment(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.registration_service.book_appointment(**payload)
        return {
            "state": TaskStateEnum.BOOKED.value,
            "message": f"已为{data['patient_name']}成功预约{data['appointment_time']}的{data['department_name']}号。",
            "data": data,
            "trace": [
                f"权限校验通过：用户可为{data['patient_name']}挂号。",
                f"找到可用号源：{data['doctor_name']} {data['appointment_time']}。",
                "挂号成功，号源库存已扣减。",
            ],
        }

    def _tool_query_slots(self, payload: dict[str, Any]) -> dict[str, Any]:
        schedules = self.slot_service.query_slots(
            department_name=payload.get("department_name"),
            doctor_name=payload.get("doctor_name"),
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            exact_date=payload.get("exact_date"),
            exact_time=payload.get("exact_time"),
            slot_type=payload.get("slot_type"),
            only_available=True,
        )
        if not schedules:
            self.slot_service.find_schedule_or_raise(
                department_name=payload.get("department_name"),
                doctor_name=payload.get("doctor_name"),
                start_date=payload.get("start_date"),
                end_date=payload.get("end_date"),
                exact_date=payload.get("exact_date"),
                exact_time=payload.get("exact_time"),
                slot_type=payload.get("slot_type"),
            )
        first = schedules[0]
        items = [
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
            for item in schedules[:5]
        ]
        return {
            "state": TaskStateEnum.AVAILABLE.value,
            "message": f"最近可用号源是 {first.work_date.isoformat()} {first.start_time.strftime('%H:%M')}，医生：{first.doctor.name}。",
            "data": {"schedules": items},
            "trace": [f"查询号源完成，返回 {len(items)} 条可用结果。"],
        }

    def _tool_cancel_appointment(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.registration_service.cancel_appointment(
            user_id=payload["user_id"],
            department_name=payload.get("department_name"),
            doctor_name=payload.get("doctor_name"),
            exact_date=payload.get("exact_date"),
            slot_type=payload.get("slot_type"),
            patient_name=payload.get("patient_name"),
        )
        return {
            "state": TaskStateEnum.CANCELLED.value,
            "message": f"已取消{data['department_name']}{data['appointment_time']}的挂号记录。",
            "data": data,
            "trace": ["已找到目标挂号记录。", "取消成功，号源库存已回补。"],
        }

    def _tool_query_doctor_schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        schedules = self.doctor_service.list_doctor_schedules(
            doctor_name=payload["doctor_name"],
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
        )
        items = [
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
            for item in schedules
        ]
        return {
            "state": TaskStateEnum.AVAILABLE.value,
            "message": f"已查询到 {payload['doctor_name']} 的坐诊安排。",
            "data": {"schedules": items},
            "trace": [f"查询医生排班完成，命中 {len(items)} 条记录。"],
        }

    def _tool_repeat_previous_doctor(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.registration_service.repeat_previous_doctor(
            user_id=payload["user_id"],
            patient_name=payload["patient_name"],
            department_name=payload.get("department_name"),
            slot_type=payload.get("slot_type"),
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
        )
        return {
            "state": TaskStateEnum.BOOKED.value,
            "message": f"已根据历史记录为{data['patient_name']}重新预约{data['doctor_name']}。",
            "data": data,
            "trace": ["已匹配历史专家挂号记录。", "已完成复约并扣减库存。"],
        }
