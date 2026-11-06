"""IndicTrans2 translation provider (AI4Bharat).

Verified against https://github.com/AI4Bharat/IndicTrans2:

* language identifiers are script-tagged: eng_Latn, hin_Deva, kan_Knda,
  tam_Taml, tel_Telu, mal_Mlym, ...
* three checkpoint families:
    - En -> Indic : ai4bharat/indictrans2-en-indic-dist-200M (or -1B)
    - Indic -> En : ai4bharat/indictrans2-indic-en-dist-200M (or -1B)
    - Indic -> Indic: ai4bharat/indictrans2-indic-indic-dist-320M (or -1B)
* HF-compatible models are loaded with AutoModelForSeq2SeqLM +
  IndicTransToolkit preprocessing (official huggingface_interface).
* sequence lengths are bounded, so text is translated in chunks.

Weights are lazy-loaded on first use; set TRANSLATION_REMOTE_URL to call a
hosted endpoint instead. Never downloaded at startup.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from app.ai.translation.base import TranslationProvider
from app.ai.types import ProviderInfo
from app.core.config import settings
from app.core.errors import ModelLoadError, ProviderError
from app.core.languages import get_language

logger = logging.getLogger("lecturelens.translation.indictrans2")


class IndicTrans2(TranslationProvider):
    name = "translation"

    def __init__(self) -> None:
        self._models: Dict[Tuple[str, str], object] = {}
        self._tokenizers: Dict[Tuple[str, str], object] = {}
        self._load_error: Optional[str] = None
        self._processor = None

    def info(self) -> ProviderInfo:
        detail = settings.translation_remote_url or (
            f"directions loaded: {sorted(self._models.keys()) or 'none (lazy)'}")
        if self._load_error:
            detail = self._load_error
        return ProviderInfo(name="translation", provider="indictrans2",
                            mode="real", loaded=bool(self._models),
                            detail=detail)

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _direction(src_key: str, tgt_key: str) -> str:
        src = get_language(src_key).indictrans
        tgt = get_language(tgt_key).indictrans
        if src == "eng_Latn" and tgt != "eng_Latn":
            return "en-indic"
        if tgt == "eng_Latn" and src != "eng_Latn":
            return "indic-en"
        if src != "eng_Latn" and tgt != "eng_Latn":
            return "indic-indic"
        return "identity"

    def _checkpoint_for(self, direction: str) -> str:
        if direction == "en-indic":
            return settings.indictrans_en_indic_model
        if direction == "indic-en":
            return settings.indictrans_indic_en_model
        if direction == "indic-indic":
            return settings.indictrans_indic_indic_model
        raise ProviderError(f"Unsupported translation direction: {direction}")

    def _load_direction(self, direction: str):
        key = (direction, "loaded")
        if direction in self._models:
            return self._models[direction], self._tokenizers[direction]
        if self._load_error:
            raise ModelLoadError(self._load_error)

        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            self._load_error = (
                "transformers/torch are not installed for IndicTrans2. "
                "Install real-translation extras (see backend/requirements.txt) "
                "or set TRANSLATION_PROVIDER=mock."
            )
            raise ModelLoadError(self._load_error) from exc

        try:
            from IndicTransToolkit import IndicTransTokenizer  # type: ignore
            processor = IndicTransTokenizer()
        except ImportError:
            try:  # older package name used in some mirrors
                from indictrans_toolkit import IndicTransTokenizer  # type: ignore
                processor = IndicTransTokenizer()
            except ImportError as exc:
                self._load_error = (
                    "IndicTransToolkit is not installed. Install the official "
                    "IndicTrans2 huggingface_interface requirements "
                    "(IndicTransToolkit), or set TRANSLATION_PROVIDER=mock."
                )
                raise ModelLoadError(self._load_error) from exc

        ckpt = self._checkpoint_for(direction)
        try:
            logger.info("Loading IndicTrans2 checkpoint %s (lazy)...", ckpt)
            tokenizer = AutoTokenizer.from_pretrained(ckpt, trust_remote_code=True)
            model = AutoModelForSeq2SeqLM.from_pretrained(
                ckpt, trust_remote_code=True,
                torch_dtype=torch.float32,
            )
            model.eval()
            if settings.model_device == "cuda" and torch.cuda.is_available():
                model = model.cuda()
            self._models[direction] = model
            self._tokenizers[direction] = tokenizer
            if self._processor is None:
                self._processor = processor
            return model, tokenizer
        except Exception as exc:  # noqa: BLE001
            self._load_error = (
                f"Failed to load IndicTrans2 checkpoint '{ckpt}': {exc}. "
                "Set the model id/path in the environment or use "
                "TRANSLATION_PROVIDER=mock."
            )
            raise ModelLoadError(self._load_error) from exc

    # -------------------------------------------------------------- translate
    def translate_batch(self, texts: List[str], source_lang: str,
                        target_lang: str) -> List[str]:
        if not texts:
            return []
        src_key, tgt_key = get_language(source_lang).key, get_language(target_lang).key
        if src_key == tgt_key:
            return list(texts)

        if settings.translation_remote_url:
            return self._remote(texts, src_key, tgt_key)

        direction = self._direction(src_key, tgt_key)
        if direction == "identity":
            return list(texts)

        model, tokenizer = self._load_direction(direction)
        src_code = get_language(src_key).indictrans
        tgt_code = get_language(tgt_key).indictrans

        out: List[str] = []
        try:
            import torch
            for chunk in _split_chunks(texts, settings.translation_chunk_chars):
                if self._processor is not None and hasattr(self._processor, "process_text"):
                    # IndicTransToolkit API: process_text(text, src_lang, tgt_lang)
                    processed = [
                        self._processor.process_text(t, src_code, tgt_code)
                        for t in chunk
                    ]
                else:  # pragma: no cover - fallback without toolkit processor
                    processed = chunk
                batch = tokenizer(
                    processed, return_tensors="pt", padding=True, truncation=True,
                    max_length=512,
                )
                with torch.no_grad():
                    generated = model.generate(**batch, max_length=512)
                decoded = tokenizer.batch_decode(generated, skip_special_tokens=True)
                # The official toolkit detokenizes target-script output
                if self._processor is not None and hasattr(self._processor, "postprocess_batch"):
                    decoded = self._processor.postprocess_batch(decoded, lang=tgt_code)
                out.extend(d.strip() for d in decoded)
        except ModelLoadError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"IndicTrans2 translation failed: {exc}") from exc

        if len(out) != len(texts):
            raise ProviderError(
                f"Translation returned {len(out)} results for {len(texts)} inputs.")
        return out

    def _remote(self, texts: List[str], src_key: str, tgt_key: str) -> List[str]:
        import httpx
        src = get_language(src_key).indictrans
        tgt = get_language(tgt_key).indictrans
        try:
            resp = httpx.post(
                settings.translation_remote_url,
                json={"texts": texts, "source_language": src,
                      "target_language": tgt},
                timeout=300.0,
            )
            resp.raise_for_status()
            data = resp.json()
            translations = data.get("translations") or data.get("texts") or []
            if len(translations) != len(texts):
                raise ProviderError("Remote translation count mismatch.")
            return [str(t) for t in translations]
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Remote translation endpoint failed: {exc}",
                detail='Contract: POST {"texts": [...], "source_language": '
                       '"eng_Latn", "target_language": "kan_Knda"} -> '
                       '{"translations": [...]}',
            ) from exc


def _split_chunks(texts: List[str], max_chars: int) -> List[List[str]]:
    """Group texts into batches that stay under max_chars per sequence."""
    batches: List[List[str]] = []
    current: List[str] = []
    size = 0
    for t in texts:
        t_len = len(t)
        if current and size + t_len > max_chars:
            batches.append(current)
            current, size = [], 0
        current.append(t)
        size += t_len
    if current:
        batches.append(current)
    return batches
