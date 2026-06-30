"""Synthesizer module: merges panel responses + judge analysis into final answer."""
from __future__ import annotations

import json
import logging
from typing import Any

from app.fusion.adapters.registry import AdapterRegistry
from app.fusion.schemas import ChatRequest, ModelRequest, ModelResponse

logger = logging.getLogger(__name__)

SYNTHESIZER_SYSTEM_PROMPT = """你是一个综合合成器（Synthesizer）。你将收到：
1. 原始用户问题
2. 多个模型的原始回答
3. Judge 的交叉分析报告（含共识、矛盾、盲区、独特洞察）

你的任务是生成一个融合后的最终答案，要求：
- **共识采纳**：优先采用 Judge 标记为共识的内容
- **矛盾裁决**：对 Judge 标记的矛盾点，给出你的判断和理由
- **盲区补充**：补充 Judge 指出的覆盖盲区
- **洞察整合**：将各模型的独特洞察自然融入回答
- **连贯自然**：最终输出是连贯、自然、完整的回答，不是拼接
- **保持原始意图**：遵循用户原始问题的意图和上下文

直接输出最终答案，不要解释你的合成过程。
"""


class SynthesizerModule:
    def __init__(self, registry: AdapterRegistry, synthesizer_model: str):
        self.registry = registry
        self.synthesizer_model = synthesizer_model

    async def synthesize(
        self, original_prompt: ChatRequest, panel_responses: list[ModelResponse], judge_analysis: dict[str, Any]
    ) -> ModelResponse:
        adapter = self.registry.get(self.synthesizer_model)
        if adapter is None:
            logger.error("Synthesizer model %s not found", self.synthesizer_model)
            return panel_responses[0]

        user_content = self._build_synthesizer_prompt(original_prompt, panel_responses, judge_analysis)
        synth_request = ModelRequest(
            model=self.synthesizer_model,
            messages=[
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.5,
            max_tokens=8192,
            stream=False,
        )

        try:
            response = await adapter.chat(synth_request)
            return response
        except Exception as e:
            logger.error("Synthesizer call failed: %s", e, exc_info=True)
            return panel_responses[0]

    def _build_synthesizer_prompt(
        self, original_prompt: ChatRequest, panel_responses: list[ModelResponse], judge_analysis: dict[str, Any]
    ) -> str:
        original_question = ""
        history_parts = []
        for msg in original_prompt.messages:
            if msg.get("role") == "user":
                original_question = msg.get("content", "")
            history_parts.append(f"[{msg.get('role', 'unknown')}] {msg.get('content', '')[:2000]}")

        def _truncate(content: str, limit: int) -> str:
            if len(content) > limit:
                return content[:limit] + "\n\n[...剩余内容已截断]"
            return content

        panel_parts = [f"### {r.model}\n{_truncate(r.content, 6000)}" for r in panel_responses]
        judge_section = json.dumps(judge_analysis, ensure_ascii=False, indent=2)

        return (
            f"## 原始对话上下文\n{chr(10).join(history_parts)}\n\n"
            f"## 原始问题\n{original_question}\n\n"
            f"## 各模型原始回答\n\n{chr(10).join(panel_parts)}\n\n"
            f"## Judge 交叉分析报告\n\n{judge_section}\n\n"
            "请基于以上信息，生成融合后的最终答案。"
        )
