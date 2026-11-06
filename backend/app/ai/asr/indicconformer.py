"""IndicConformer ASR provider (AI4Bharat / NeMo).

Official docs: https://github.com/AI4Bharat/IndicConformerASR

Key facts verified from the official README:
* checkpoints are `.nemo` archives loaded with AI4Bharat NeMo (nemo-v2 branch),
* multilingual checkpoint: indicconformer_stt_multi_hybrid_rnnt_600m.nemo,
* monolingual checkpoints use short language codes (hi, kn, ta, te, ml, ...),
* license: MIT.

This provider lazy-imports NeMo and only loads the checkpoint on first use.
Weights are NEVER downloaded automatically — set INDICCONFORMER_CHECKPOINT to
a local .nemo path (or provide ASR_REMOTE_URL).

Timestamps: RNNT decoding exposes chunk/utterance level hypotheses; we map
each recognized hypothesis back to the chunk time range we sent it. We do not
claim word-level timestamps.
"""
from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from app.ai.asr.base import ASRProvider
from app.ai.types import ASRResult, ASRSegmentResult, ProviderInfo
from app.core.config import settings
from app.core.errors import ModelLoadError, ProviderError

logger = logging.getLogger("lecturelens.asr.indicconformer")

_REMOTE_CONTRACT = (
    "Remote ASR contract: POST {url} with JSON "
    '{"language": str, "sample_rate": int, "audio_b64": str (s16le mono PCM)}, '
    "response JSON {\"text\": str} or {\"segments\": [{\"start\",\"end\",\"text\"}]}."
)


class IndicConformerASR(ASRProvider):
    name = "asr"

    def __init__(self) -> None:
        self._model = None
        self._load_error: Optional[str] = None

    # ------------------------------------------------------------------ info
    def info(self) -> ProviderInfo:
        loaded = self._model is not None
        detail = settings.asr_remote_url or (
            f"checkpoint={settings.indicconformer_checkpoint or '<unset>'}"
        )
        if self._load_error:
            detail = self._load_error
        return ProviderInfo(name="asr", provider="indicconformer", mode="real",
                            loaded=loaded, detail=detail)

    # ------------------------------------------------------------------ load
    def _load(self):
        if self._model is not None:
            return self._model
        if self._load_error:
            raise ModelLoadError(self._load_error, detail=_REMOTE_CONTRACT)

        ckpt = settings.indicconformer_checkpoint
        if not ckpt:
            self._load_error = (
                "IndicConformer checkpoint not configured. Set "
                "INDICCONFORMER_CHECKPOINT=/path/to/indicconformer_stt_multi_hybrid_rnnt_600m.nemo "
                "(download from the official AI4Bharat IndicConformerASR README), "
                "or set ASR_REMOTE_URL to a GPU inference endpoint, or use ASR_PROVIDER=mock."
            )
            raise ModelLoadError(self._load_error, detail=_REMOTE_CONTRACT)

        path = Path(ckpt).expanduser()
        if not path.exists():
            self._load_error = (
                f"IndicConformer checkpoint not found at '{path}'. "
                "Download the official .nemo file and update INDICCONFORMER_CHECKPOINT."
            )
            raise ModelLoadError(self._load_error)

        try:
            import nemo  # noqa: F401
            from nemo.collections.asr.models import EncDecRNNTBPEModel
        except ImportError as exc:
            self._load_error = (
                "NeMo is not installed. Install AI4Bharat NeMo first: "
                "git clone https://github.com/AI4Bharat/NeMo.git && cd NeMo && "
                "git checkout nemo-v2 && bash reinstall.sh"
            )
            raise ModelLoadError(self._load_error) from exc

        try:
            device = "cuda" if settings.model_device == "cuda" else None
            model = EncDecRNNTBPEModel.restore_from(str(path), map_location=device or "cpu")
            model.eval()
            if settings.model_device == "cuda":
                model = model.cuda()
            self._model = model
            logger.info("IndicConformer loaded from %s", path)
            return model
        except Exception as exc:  # noqa: BLE001 — surface any weight/load failure
            self._load_error = f"Failed to load IndicConformer checkpoint: {exc}"
            raise ModelLoadError(self._load_error) from exc

    # ------------------------------------------------------------- transcribe
    def transcribe(self, audio_path: Path, language: str,
                   chunk_times: List[tuple]) -> ASRResult:
        if settings.asr_remote_url:
            return self._transcribe_remote(audio_path, language, chunk_times)

        model = self._load()

        # Optional language switch for the multilingual checkpoint. The official
        # hybrid RNNT models expose `language` via cfg; we attempt known safe
        # APIs and degrade gracefully rather than guessing.
        try:
            lang_cfg = getattr(model, "cfg", None)
            if lang_cfg is not None and hasattr(model, "change_language"):
                model.change_language(language)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not set ASR language explicitly: %s", exc)

        from app.services import audio as audio_service
        pcm = audio_service.extract_pcm(audio_path)
        sample_rate = settings.target_sample_rate

        results: List[ASRSegmentResult] = []
        # Write each chunk to a temp WAV and run NeMo's documented transcribe API.
        for i, (start, end) in enumerate(chunk_times, start=1):
            start_b = int(start * sample_rate) * 2
            end_b = int(end * sample_rate) * 2
            chunk_pcm = pcm[max(0, start_b):min(len(pcm), end_b)]
            if not chunk_pcm:
                continue
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
                # minimal WAV header for 16 kHz mono s16le
                import struct
                data_len = len(chunk_pcm)
                sr = sample_rate
                byte_rate = sr * 2
                header = struct.pack(
                    "<4sI4s4sIHHIIHH4sI",
                    b"RIFF", 36 + data_len, b"WAVE", b"fmt ", 16,
                    1, 1, sr, byte_rate, 2, 16, b"data", data_len,
                )
                fh.write(header)
                fh.write(chunk_pcm)
                tmp_path = fh.name
            try:
                hypotheses = model.transcribe(paths2audio_files=[tmp_path],
                                              return_hypotheses=True)  # type: ignore[call-arg]
                text = self._hypothesis_text(hypotheses)
            except Exception as exc:  # noqa: BLE001
                raise ProviderError(
                    f"IndicConformer transcription failed on chunk {i}: {exc}"
                ) from exc
            finally:
                Path(tmp_path).unlink(missing_ok=True)

            results.append(ASRSegmentResult(
                start=float(start), end=float(end),
                text=text.strip(), language=language))

        return ASRResult(
            segments=[r for r in results if r.text],
            language=language, is_mock=False, provider="indicconformer",
            detail="IndicConformer chunk-level transcription.",
        )

    @staticmethod
    def _hypothesis_text(hypotheses) -> str:
        """Extract text from NeMo hypotheses (list of Hypothesis or strings)."""
        if not hypotheses:
            return ""
        texts: List[str] = []
        for h in hypotheses:
            if isinstance(h, str):
                texts.append(h)
            elif isinstance(h, (list, tuple)):
                for item in h:
                    texts.append(IndicConformerASR._hypothesis_text([item]))
            else:
                txt = getattr(h, "text", None)
                if txt is None and isinstance(h, dict):
                    txt = h.get("text", "")
                texts.append(txt or "")
        return " ".join(t for t in texts if t)

    # ----------------------------------------------------------------- remote
    def _transcribe_remote(self, audio_path: Path, language: str,
                           chunk_times: List[tuple]) -> ASRResult:
        import httpx

        from app.services import audio as audio_service
        pcm = audio_service.extract_pcm(audio_path)
        try:
            resp = httpx.post(
                settings.asr_remote_url,
                json={
                    "language": language,
                    "sample_rate": settings.target_sample_rate,
                    "audio_b64": base64.b64encode(pcm).decode("ascii"),
                },
                timeout=300.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Remote ASR endpoint failed: {exc}",
                                detail=_REMOTE_CONTRACT) from exc

        if "segments" in data and isinstance(data["segments"], list):
            segs = [ASRSegmentResult(
                start=float(s.get("start", 0.0)),
                end=float(s.get("end", 0.0)),
                text=str(s.get("text", "")),
                language=language,
            ) for s in data["segments"]]
        else:
            text = str(data.get("text", ""))
            segs = [ASRSegmentResult(start=s, end=e, text=text, language=language)
                    for (s, e) in chunk_times] if text else []

        return ASRResult(segments=[s for s in segs if s.text],
                         language=language, is_mock=False,
                         provider="indicconformer(remote)",
                         detail=settings.asr_remote_url)
