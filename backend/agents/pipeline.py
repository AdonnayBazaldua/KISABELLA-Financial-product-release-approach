import asyncio
from langgraph.graph import StateGraph, END
from agents.schemas import PipelineState
from agents.financial import run_financial_agent


def financial_node(state: PipelineState) -> dict:
    try:
        result = run_financial_agent(state["inputs"])
        return {"financial_result": result}
    except Exception as e:
        return {"error": f"Agente financiero falló: {str(e)}"}


def determine_verdict(state: PipelineState) -> dict:
    financial = state.get("financial_result")
    if not financial or state.get("error"):
        return {
            "final_verdict": "no_viable",
            "final_score": 0,
            "final_summary": state.get("error", "Error en el análisis"),
        }

    score = financial["score"]
    if score >= 70:
        verdict = "viable"
    elif score >= 45:
        verdict = "viable_con_ajustes"
    else:
        verdict = "no_viable"

    return {
        "final_verdict": verdict,
        "final_score": score,
        "final_summary": financial["analisis_extenso"],
    }


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("financial_agent", financial_node)
    graph.add_node("verdict", determine_verdict)

    graph.set_entry_point("financial_agent")
    graph.add_edge("financial_agent", "verdict")
    graph.add_edge("verdict", END)

    return graph.compile()


pipeline = build_pipeline()


async def run_pipeline(evaluation_id: str, inputs: dict) -> PipelineState:
    initial_state: PipelineState = {
        "evaluation_id": evaluation_id,
        "inputs": inputs,
        "financial_result": None,
        "market_result": None,
        "risk_result": None,
        "strategy_result": None,
        "final_verdict": None,
        "final_score": None,
        "final_summary": None,
        "error": None,
    }
    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: pipeline.invoke(initial_state)
    )
    return result
