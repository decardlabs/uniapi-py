"""
Synthesizer module: takes Judge analysis + panel responses, produces final answer.

The synthesizer is NOT a simple text merger. It uses the Judge's structured
analysis to make informed decisions about what to include, what to resolve,
and what to add from blind spots.
"""

import logging
from typing import Any

from src.adapters.registry import AdapterRegistry
from src.models.schemas import ChatRequest, ModelResponse, ModelRequest

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
    """Calls the synthesizer model to produce the final fused answer."""

    def __init__(self, registry: AdapterRegistry, synthesizer_model: str):
        self.registry = registry
        self.synthesizer_model = synthesizer_model

    async def synthesize(
        self,
        original_prompt: ChatRequest,
        panel_responses: list[ModelResponse],
        judge_analysis: dict[str, Any],
    ) -> ModelResponse:
        """
        Merge panel responses using judge analysis into final answer.

        Returns:
            ModelResponse with the synthesized content.
        """
        adapter = self.registry.get(self.synthesizer_model)
        if adapter is None:
            logger.error("Synthesizer model %s not found", self.synthesizer_model)
            # Fallback: return the first panel response
            return panel_responses[0]

        # Build synthesizer prompt
        user_content = self._build_synthesizer_prompt(
            original_prompt, panel_responses, judge_analysis
        )

        synth_request = ModelRequest(
            model=self.synthesizer_model,
            messages=[
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.5,  # Moderate temperature for coherent synthesis
            max_tokens=8192,
            stream=False,
        )

        try:
            response = await adapter.chat(synth_request)
            logger.info(
                "Synthesis complete | model=%s | tokens=%d",
                self.synthesizer_model,
                response.usage.completion_tokens,
            )
            return response
        except Exception as e:
            logger.error("Synthesizer call failed: %s", e, exc_info=True)
            # Fallback: return the first panel response
            return panel_responses[0]

    def _build_synthesizer_prompt(
        self,
        original_prompt: ChatRequest,
        panel_responses: list[ModelResponse],
        judge_analysis: dict[str, Any],
    ) -> str:
        """Build the prompt that includes all context for the synthesizer."""
        import json

        # Extract original user question and conversation history
        original_question = ""
        history_parts = []
        for msg in original_prompt.messages:
            if msg.get("role") == "user":
                original_question = msg.get("content", "")
            history_parts.append(f"[{msg.get('role', 'unknown')}] {msg.get('content', '')[:2000]}")

        # Build panel responses section
        panel_parts = []
        for resp in panel_responses:
            model_name = resp.model
            content = resp.content[:6000]  # Truncate for token budget
            panel_parts.append(f"### {model_name}\n{content}")

        # Build judge analysis section (formatted for readability)
        judge_section = json.dumps(judge_analysis, ensure_ascii=False, indent=2)

        prompt = f"""## 原始对话上下文
{chr(10).join(history_parts)}

## 原始问题
{original_question}

## 各模型原始回答

{chr(10).join(panel_parts)}

## Judge 交叉分析报告

{judge_section}

请基于以上信息，生成融合后的最终答案。"""

        return prompt
