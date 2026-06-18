"""
Judge module: receives all panel responses, produces structured analysis.

Output JSON structure:
  - consensus:      points most/all models agree on
  - contradictions: disagreements with each model's position
  - coverage_gaps:  points ALL models missed
  - unique_insights: valuable points only ONE model made
  - blind_spots:    topics none addressed
  - confidence:     float 0-1
"""

import json
import logging
from typing import Any

from src.adapters.registry import AdapterRegistry
from src.models.schemas import ChatRequest, ModelResponse

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """你是一个严格的交叉分析裁判（Judge）。你将收到同一个问题的多个模型回答。
你的任务不是给出答案，而是分析这些回答之间的关系。

请输出严格的 JSON，格式如下：
{
  "consensus": ["多数或全部模型一致的观点1", "观点2"],
  "contradictions": [
    {
      "topic": "分歧主题",
      "positions": {
        "模型A": "观点A",
        "模型B": "观点B",
        "模型C": "观点C"
      },
      "judge_note": "裁判对分歧的分析"
    }
  ],
  "coverage_gaps": ["所有模型都遗漏的要点1"],
  "unique_insights": {
    "模型A": "仅模型A提出的有价值观点",
    "模型B": "仅模型B提出的有价值观点",
    "模型C": "仅模型C提出的有价值观点"
  },
  "blind_spots": ["所有模型都未涉及的领域1"],
  "confidence": 0.82,
  "recommendation": "综合建议：采纳哪些观点，如何处理分歧"
}

注意：
- consensus 只包含真正一致的观点，不要凑数
- contradictions 要具体列出每个模型的不同立场
- unique_insights 只记录有真正价值的独特见解
- confidence 基于共识比例和信息质量综合评估
- recommendation 给出明确的综合建议
"""


class JudgeModule:
    """Calls the judge model to produce structured cross-analysis."""

    def __init__(self, registry: AdapterRegistry, judge_model: str):
        self.registry = registry
        self.judge_model = judge_model

    async def analyze(
        self,
        original_prompt: ChatRequest,
        panel_responses: list[ModelResponse],
    ) -> dict[str, Any]:
        """
        Send all panel responses to judge model, get structured analysis.

        Returns:
            Dict with keys: consensus, contradictions, coverage_gaps,
            unique_insights, blind_spots, confidence, recommendation, usage
        """
        adapter = self.registry.get(self.judge_model)
        if adapter is None:
            logger.error("Judge model %s not found", self.judge_model)
            return self._empty_analysis()

        # Build the judge prompt
        user_content = self._build_judge_prompt(original_prompt, panel_responses)

        from src.models.schemas import ModelRequest

        judge_request = ModelRequest(
            model=self.judge_model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,  # Low temperature for analytical consistency
            max_tokens=4096,
            stream=False,
        )

        try:
            response = await adapter.chat(judge_request)
            analysis = self._parse_judge_response(response.content)
            analysis["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
            logger.info(
                "Judge analysis complete | confidence=%.2f | consensus=%d | contradictions=%d",
                analysis.get("confidence", 0),
                len(analysis.get("consensus", [])),
                len(analysis.get("contradictions", [])),
            )
            return analysis
        except Exception as e:
            logger.error("Judge call failed: %s", e, exc_info=True)
            return self._empty_analysis()

    def _build_judge_prompt(
        self,
        original_prompt: ChatRequest,
        panel_responses: list[ModelResponse],
    ) -> str:
        """Build the prompt that sends all panel responses to the judge."""
        # Extract original user question
        original_question = ""
        for msg in original_prompt.messages:
            if msg.get("role") == "user":
                original_question = msg.get("content", "")
                break

        parts = [
            f"## 原始问题\n{original_question}\n",
            "## 各模型回答\n",
        ]

        for resp in panel_responses:
            model_name = resp.model
            content = resp.content[:4000]  # Truncate for token budget
            parts.append(f"### {model_name} 的回答\n{content}\n")

        parts.append(
            "\n请基于以上回答进行严格的交叉分析，输出 JSON 格式的分析报告。"
        )

        return "\n".join(parts)

    def _parse_judge_response(self, raw_content: str) -> dict[str, Any]:
        """Parse the judge's JSON response, with fallback for malformed JSON."""
        # Try to extract JSON from the response
        content = raw_content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first and last lines (fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)

        try:
            analysis = json.loads(content)
            # Validate required fields
            required = [
                "consensus",
                "contradictions",
                "coverage_gaps",
                "unique_insights",
                "blind_spots",
                "confidence",
            ]
            for key in required:
                if key not in analysis:
                    analysis[key] = [] if key != "confidence" else 0.5

            return analysis
        except json.JSONDecodeError as e:
            logger.warning("Judge response not valid JSON: %s", e)
            logger.debug("Raw judge response: %s", content[:500])
            return self._empty_analysis(raw_content)

    def _empty_analysis(self, raw: str = "") -> dict[str, Any]:
        """Return a minimal analysis structure when judge fails."""
        return {
            "consensus": [],
            "contradictions": [],
            "coverage_gaps": [],
            "unique_insights": {},
            "blind_spots": [],
            "confidence": 0.0,
            "recommendation": raw[:500] if raw else "Judge analysis unavailable.",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
        }
