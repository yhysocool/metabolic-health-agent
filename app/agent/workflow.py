"""Metabolic Health Agent 的 LangGraph 工作流。"""

from datetime import date
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentState
from app.agent.tools import (
    analyze_health_trend,
    calculate_metabolic_status,
    get_recent_health_data,
    get_user_profile,
    retrieve_guideline,
    validate_health_plan,
)
from app.config import get_settings
from app.llm.base import BaseLLM, ChatMessage
from app.llm.factory import create_llm_provider
from app.rag.retriever import BaseRetriever, FaissRetriever
from app.repositories.base import HealthRepository
from app.safety.rules import SafetyRuleEngine
from app.schemas.plan import HealthPlan, HealthPlanDraft


def build_health_agent(
    repository: HealthRepository,
    *,
    retriever: BaseRetriever | None = None,
    llm: BaseLLM | None = None,
    safety_engine: SafetyRuleEngine | None = None,
) -> Any:
    """以注入的基础设施构建可测试的 LangGraph 编排。"""

    retriever = retriever or FaissRetriever()
    llm = llm or create_llm_provider()
    safety_engine = safety_engine or SafetyRuleEngine()
    settings = get_settings()

    async def load_user_profile(state: AgentState) -> AgentState:
        profile = await get_user_profile(repository, state["user_id"])
        return {"user_profile": profile}

    async def get_health_events(state: AgentState) -> AgentState:
        events = await get_recent_health_data(
            repository, state["user_id"], settings.health_lookback_days
        )
        return {"health_events": events}

    def health_analysis_tool(state: AgentState) -> AgentState:
        status = calculate_metabolic_status(
            repository, state["user_profile"], state.get("health_events", [])
        )
        return {"health_status": status}

    def trend_analysis_tool(state: AgentState) -> AgentState:
        trend = analyze_health_trend(state.get("health_events", []))
        return {"trend": trend}

    def retrieve_guideline_tool(state: AgentState) -> AgentState:
        status = state["health_status"]
        query = (
            f"目标 {state['user_profile'].goal.value}，健康关注等级 {status.label.value}，"
            f"睡眠趋势 {state['trend']['sleep'].value}，活动趋势 {state['trend']['activity'].value}"
        )
        documents = retrieve_guideline(retriever, query, settings.rag_top_k)
        return {"retrieved_docs": documents}

    async def generate_plan(state: AgentState) -> AgentState:
        status = state["health_status"]
        documents = state.get("retrieved_docs", [])
        mock_context = "\n".join(document.content for document in documents)
        llm_note = await llm.chat(
            [
                ChatMessage(role="system", content=SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=(
                        f"用户目标：{state['user_profile'].goal.value}；"
                        f"健康管理分数：{status.score}；参考资料：{mock_context}"
                    ),
                ),
            ]
        )
        draft = HealthPlanDraft(
            user_id=state["user_id"],
            date=date.today(),
            exercise_plan=[
                "从可轻松完成的日常步行开始，记录主观疲劳并循序渐进。",
                "每周安排适量基础力量活动；如身体不适，应停止并咨询专业人员。",
            ],
            diet_plan=[
                "保持规律进餐，优先选择多样化、少加工的食物。",
                "记录饮食和饱腹感，用长期可持续的小调整替代激进限制。",
            ],
            sleep_plan=[
                "保持相对固定的起床和入睡时间。",
                "连续记录睡眠时长与白天精神状态，用于后续趋势复盘。",
            ],
            reason=(
                f"当前非诊断性健康管理标签为 {status.label.value}，分数为 {status.score}。"
                f"计划基于 Mock 健康事件和 Mock 检索文档生成。{llm_note} "
                "本计划不构成医疗诊断或治疗建议。"
            ),
        )
        return {"plan_draft": draft}

    def safety_check(state: AgentState) -> AgentState:
        validation = validate_health_plan(safety_engine, state["plan_draft"])
        if not validation.safe:
            raise ValueError(f"健康计划未通过安全检查：{'; '.join(validation.issues)}")
        return {"safety_validation": validation}

    async def save_plan(state: AgentState) -> AgentState:
        plan = await repository.save_plan(state["plan_draft"])
        return {"plan": plan}

    workflow = StateGraph(AgentState)
    workflow.add_node("load_user_profile", load_user_profile)
    workflow.add_node("get_health_events", get_health_events)
    workflow.add_node("health_analysis_tool", health_analysis_tool)
    workflow.add_node("trend_analysis_tool", trend_analysis_tool)
    workflow.add_node("retrieve_guideline_tool", retrieve_guideline_tool)
    workflow.add_node("generate_plan", generate_plan)
    workflow.add_node("safety_check", safety_check)
    workflow.add_node("save_plan", save_plan)

    workflow.add_edge(START, "load_user_profile")
    workflow.add_edge("load_user_profile", "get_health_events")
    workflow.add_edge("get_health_events", "health_analysis_tool")
    workflow.add_edge("health_analysis_tool", "trend_analysis_tool")
    workflow.add_edge("trend_analysis_tool", "retrieve_guideline_tool")
    workflow.add_edge("retrieve_guideline_tool", "generate_plan")
    workflow.add_edge("generate_plan", "safety_check")
    workflow.add_edge("safety_check", "save_plan")
    workflow.add_edge("save_plan", END)
    return workflow.compile()


async def generate_health_plan(
    repository: HealthRepository, user_id: str
) -> HealthPlan:
    """API 使用的简化入口，执行完整工作流并返回已保存计划。"""

    result = await build_health_agent(repository).ainvoke({"user_id": user_id})
    return HealthPlan.model_validate(result["plan"])

