"""BharatGen Param-1-2.9B-Instruct provider.

Verified against the official model card:
https://huggingface.co/bharatgenai/Param-1-2.9B-Instruct

* bilingual (hi/en) instruction model — we always feed ENGLISH text
  (the pipeline translates non-English sources first),
* loaded with AutoModelForCausalLM(trust_remote_code=True) because the repo
  ships a custom `ParamBharatGenForCausalLM` architecture,
* generation via tokenizer.apply_chat_template(..., add_generation_prompt=True)
  then model.generate with the card's sampling defaults (we lower temperature
  for more deterministic structured output),
* lazy loading: weights are only fetched/loaded on first use; never at startup.

Set LLM_REMOTE_URL to use a hosted OpenAI-compatible endpoint instead
(e.g. a vLLM server serving Param-1).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.ai.llm.base import LLMProvider
from app.ai.types import GenerationContext, LLMResult, ProviderInfo
from app.core.config import settings
from app.core.errors import GenerationError, ModelLoadError, ProviderError

logger = logging.getLogger("lecturelens.llm.param1")

NOTES_SYSTEM = (
    "You are a meticulous academic note-taker. You ONLY use information "
    "present in the provided lecture transcript. Never invent facts. "
    "If something is unclear, put it under 'uncertain'. "
    "Respond with a single JSON object and nothing else."
)

QUIZ_SYSTEM = (
    "You are an exam setter. Create EXACTLY five multiple-choice questions "
    "strictly from the provided lecture transcript. Never invent facts. "
    "Each question must have exactly four options (A, B, C, D) with exactly "
    "one correct answer, a non-empty explanation, a difficulty of "
    "easy|medium|hard, and source_segments (integer segment ids from the "
    "transcript). Respond with a single JSON object and nothing else."
)

_NOTES_INSTRUCTION = """Create structured lecture notes from the transcript below.

Return ONLY JSON with this shape:
{
  "title": str,
  "overview": str,
  "sections": [{"id": "section-1", "heading": str, "content": [str, ...], "source_segments": [int, ...]}],
  "key_terms": [{"term": str, "definition": str, "source_segments": [int, ...]}],
  "key_takeaways": [str, ...],
  "examples": [str, ...],
  "important_points": [str, ...],
  "uncertain": [str, ...]
}

Rules:
- Ground EVERY statement in the transcript; cite source_segments accurately.
- Use the segment markers like [S1], [S2] appearing before each segment.
- 3 to 6 sections; at least 1 key term and 3 key takeaways when possible.

TRANSCRIPT:
{transcript}
"""

_QUIZ_INSTRUCTION = """Create a quiz from the transcript below.

Return ONLY JSON:
{{"questions": [
  {{"id": "question-1", "question": str, "options": [
      {{"id": "A", "text": str}}, {{"id": "B", "text": str}},
      {{"id": "C", "text": str}}, {{"id": "D", "text": str}}],
   "correct_option": "A|B|C|D", "explanation": str,
   "difficulty": "easy|medium|hard", "source_segments": [int, ...]}}
]}}
Exactly five questions, four unique options each, exactly one correct answer.

TRANSCRIPT:
{transcript}
"""


class Param1LLM(LLMProvider):
    name = "llm"

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self._load_error: Optional[str] = None

    def info(self) -> ProviderInfo:
        detail = settings.llm_remote_url or f"model={settings.param1_model_id}"
        if self._load_error:
            detail = self._load_error
        return ProviderInfo(name="llm", provider="param1", mode="real",
                            loaded=self._model is not None, detail=detail)

    # ------------------------------------------------------------------ load
    def _load(self):
        if self._model is not None:
            return self._model, self._tokenizer
        if self._load_error:
            raise ModelLoadError(self._load_error)

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            self._load_error = (
                "transformers/torch are not installed. Install the real-LLM "
                "extras: pip install torch transformers accelerate "
                "(see backend/requirements.txt), or set LLM_PROVIDER=mock."
            )
            raise ModelLoadError(self._load_error) from exc

        model_id = settings.param1_model_id
        try:
            logger.info("Loading Param-1 weights from %s (lazy)...", model_id)
            tokenizer = AutoTokenizer.from_pretrained(
                model_id, trust_remote_code=False)
            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
            model = AutoModelForCausalLM.from_pretrained(
                model_id, trust_remote_code=True, torch_dtype=dtype,
                device_map="auto" if settings.model_device != "cpu" else None,
            )
            model.eval()
            self._model, self._tokenizer = model, tokenizer
            return model, tokenizer
        except Exception as exc:  # noqa: BLE001
            self._load_error = (
                f"Failed to load Param-1 ('{model_id}'): {exc}. "
                "Ensure the weights are available locally or set LLM_REMOTE_URL "
                "to a hosted endpoint, or use LLM_PROVIDER=mock."
            )
            raise ModelLoadError(self._load_error) from exc

    # ------------------------------------------------------------ generation
    def _chat(self, system: str, user: str, max_new_tokens: int) -> str:
        if settings.llm_remote_url:
            return self._chat_remote(system, user, max_new_tokens)

        model, tokenizer = self._load()
        conversation = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            inputs = tokenizer.apply_chat_template(
                conversation, return_tensors="pt", add_generation_prompt=True)
            if not hasattr(inputs, "dim"):  # older transformers return list
                import torch
                inputs = torch.tensor([inputs])
            device = next(model.parameters()).device
            inputs = inputs.to(device)
            import torch
            with torch.no_grad():
                output = model.generate(
                    inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=settings.param1_temperature > 0,
                    top_k=50,
                    top_p=0.95,
                    temperature=max(settings.param1_temperature, 1e-5),
                    eos_token_id=tokenizer.eos_token_id,
                    pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
                    use_cache=True,
                )
            gen = output[0][inputs.shape[-1]:]
            return tokenizer.decode(gen, skip_special_tokens=True)
        except ModelLoadError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Param-1 generation failed: {exc}") from exc

    def _chat_remote(self, system: str, user: str, max_new_tokens: int) -> str:
        import httpx
        try:
            resp = httpx.post(
                settings.llm_remote_url,
                json={
                    "model": settings.param1_model_id,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_new_tokens,
                    "temperature": settings.param1_temperature,
                },
                timeout=300.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Remote LLM endpoint failed: {exc}",
                detail="Expected an OpenAI-compatible chat/completions endpoint.",
            ) from exc

    # ------------------------------------------------------- public methods
    def generate_notes(self, ctx: GenerationContext) -> LLMResult:
        prompt = _NOTES_INSTRUCTION.format(transcript=_number_segments(ctx))
        text = self._chat(NOTES_SYSTEM, prompt, settings.param1_max_new_tokens_notes)
        payload = _extract_json(text)
        return LLMResult(payload=payload, is_mock=False, provider="param1",
                         raw_text=text)

    def generate_quiz(self, ctx: GenerationContext) -> LLMResult:
        prompt = _QUIZ_INSTRUCTION.format(transcript=_number_segments(ctx))
        text = self._chat(QUIZ_SYSTEM, prompt, settings.param1_max_new_tokens_quiz)
        payload = _extract_json(text)
        if "questions" not in payload and isinstance(payload, list):
            payload = {"questions": payload}
        return LLMResult(payload=payload, is_mock=False, provider="param1",
                         raw_text=text)


def _number_segments(ctx: GenerationContext) -> str:
    parts = []
    for idx, text in zip(ctx.segment_indices, ctx.segment_texts):
        parts.append(f"[S{idx}] {text}")
    return "\n".join(parts) if parts else ctx.transcript_text


def _extract_json(text: str) -> Dict[str, Any]:
    """Best-effort extraction of a JSON object from model output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"questions": data} if data and isinstance(data[0], dict) else {"items": data}
    except json.JSONDecodeError:
        pass
    # find the outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    raise GenerationError(
        "Model output did not contain valid JSON.",
        detail={"snippet": text[:300]},
    )
