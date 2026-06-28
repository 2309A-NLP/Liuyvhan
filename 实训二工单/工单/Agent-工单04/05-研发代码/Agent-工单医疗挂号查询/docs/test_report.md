# 测试报告

核心 6 个测试问题已在 `tests/test_registration_cases.py` 中覆盖。

1. `帮我大宝挂一个今天下午 2 点儿科专家的号`
   结果：`BOOKED`
   工具：`book_appointment`

2. `牙科最近的号哪天的？`
   结果：`AVAILABLE`
   工具：`query_slots`

3. `我之前挂过眼科的一个专家，帮我再约那个专家的号`
   结果：`BOOKED`
   工具：`repeat_previous_doctor`

4. `我明天上午 9 点想带二宝看皮肤科，还有号吗？`
   结果：`AVAILABLE`
   工具：`query_slots`

5. `取消我上周三挂的消化内科普通号`
   结果：`CANCELLED`
   工具：`cancel_appointment`

6. `帮我查下张建国医生下周的坐诊时间`
   结果：`AVAILABLE`
   工具：`query_doctor_schedule`
