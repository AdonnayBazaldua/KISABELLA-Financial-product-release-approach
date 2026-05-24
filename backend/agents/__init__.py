"""Capa de agentes — pipeline LangGraph multi-agente para evaluaciones.

Ver:
- contracts.py: shapes Pydantic que viajan por el pipeline
- llm_client.py: wrapper de ChatAnthropic con with_structured_output (próximo)
- base.py: build_agent() factory (próximo)
- pipeline.py: build_pipeline() LangGraph (próximo)

ADRs: 001 (functional agents), 002 (agent_results dict), 003 (Pydantic en LLMClient),
007 (langchain-anthropic), 011 (tools llamados directo).
"""
