# Model Selection & Integration Notes

All claims below were verified against the official repositories/model cards on
2026-01 (links in each section). Nothing here is invented.

## 1. ASR — AI4Bharat IndicConformer

* Repo: https://github.com/AI4Bharat/IndicConformerASR (branch `master`;
  contains README + LICENSE only — the actual code path is **AI4Bharat NeMo**).
* Loading: checkpoints are `.nemo` archives loaded with
  [AI4Bharat NeMo](https://github.com/AI4Bharat/NeMo) (`nemo-v2` branch):
  `git clone https://github.com/AI4Bharat/NeMo.git && cd NeMo && git checkout nemo-v2 && bash reinstall.sh`
* Available checkpoints (official README):
  * Multilingual 600M hybrid RNNT:
    `indicconformer_stt_multi_hybrid_rnnt_600m.nemo`
    (objectstore.e2enetworks.net/indicconformer/models/...)
  * Monolingual large hybrid RNNT per language with short codes:
    `hi`, `kn`, `ta`, `te`, `ml`, `bn`, ... (English is covered by the
    multilingual checkpoint; there is no monolingual `en` entry in the table).
* Official model license: **MIT**.
* Timestamps: the hybrid RNNT decoding path exposes **utterance/chunk level**
  timings (via NeMo's segment hypotheses), not reliable word-level timestamps.
  The implementation therefore stores segment start/end times at chunk level and
  does not claim word alignment.
* Long audio: audio is chunked by the segmentation service before inference;
  chunks are merged with de-duplication of overlap regions.

## 2. LLM — BharatGen Param-1-2.9B-Instruct

* Model card: https://huggingface.co/bharatgenai/Param-1-2.9B-Instruct
* License: **Apache-2.0**; language tags on the card: **`hi`, `en` only**.
* Load pattern (official card):
  ```python
  tokenizer = AutoTokenizer.from_pretrained("bharatgenai/Param-1-2.9B-Instruct",
                                            trust_remote_code=False)
  model = AutoModelForCausalLM.from_pretrained(..., trust_remote_code=True,
                                                device_map="auto")
  inputs = tokenizer.apply_chat_template(conversation, return_tensors="pt",
                                         add_generation_prompt=True)
  output = model.generate(inputs, max_new_tokens=..., do_sample=True,
                          top_k=50, top_p=0.95, temperature=0.6, ...)
  ```
* Architecture: `ParamBharatGenForCausalLM` (custom code in the repo —
  `trust_remote_code=True` required), hidden 2048, 32 layers,
  `max_position_embeddings: 8192` in `config.json` (README text mentions 2048 —
  we treat the **config.json** value as authoritative and keep prompts well
  below it anyway).
* Consequence for LectureLens: Param-1 is a **bilingual Hindi–English** model.
  The pipeline therefore:
  1. keeps the original transcript in its source language,
  2. translates non-English/Hindi sources to English with IndicTrans2,
  3. generates notes + quiz in English (canonical generation language),
  4. translates the generated material to the user's requested language.
  Param-1 is **never** fed Kannada/Tamil/Telugu/Malayalam text directly.

## 3. Translation — AI4Bharat IndicTrans2

* Repo: https://github.com/AI4Bharat/IndicTrans2
* Language identifiers used by the official models (from the repo README):

  | Language | Code |
  |---|---|
  | English | `eng_Latn` |
  | Hindi | `hin_Deva` |
  | Kannada | `kan_Knda` |
  | Tamil | `tam_Taml` |
  | Telugu | `tel_Telu` |
  | Malayalam | `mal_Mlym` |

* Model families (HF checkpoints):
  * En→Indic: `ai4bharat/indictrans2-en-indic-dist-200M` (distilled) / `...-1B` (base)
  * Indic→En: `ai4bharat/indictrans2-indic-en-dist-200M` / `...-1B`
  * Indic→Indic: `ai4bharat/indictrans2-indic-indic-dist-320M` / `...-1B`
* Inference requirements (official `huggingface_interface`): the HF-compatible
  models use `IndicTransToolkit` preprocessing + `AutoModelForSeq2SeqLM`.
  Sequence length is limited (base ~256/512 tokens; RoPE variants up to 2048),
  so LectureLens translates in **bounded chunks** and reassembles.
* The implementation selects the correct direction automatically
  (en↔indic via the direction-specific checkpoints, indic↔indic via the
  indic-indic checkpoint).

## 4. Voice activity detection

No official VAD ships with the IndicConformer repo. LectureLens implements a
small, dependency-free **energy-based VAD** (short-time RMS with adaptive
threshold + hangover) on top of FFmpeg-decoded PCM, and additionally consults
`ffmpeg silencedetect` output. Speech regions are cut at low-energy points with
a configurable overlap so words/sentences are not clipped mid-utterance.

## 5. Hardware & dependency requirements

| Mode | Requirement |
|---|---|
| Demo (`*_PROVIDER=mock`) | CPU only; no checkpoints; ≤ 2 GB RAM for pipeline |
| Real ASR | NeMo install, ~1–3 GB `.nemo` checkpoint, ≥ 8 GB RAM (GPU optional) |
| Real LLM | ~6 GB weights (bf16) → 16 GB RAM or 8 GB VRAM recommended |
| Real translation | ~0.5–2 GB per direction checkpoint, CPU-feasible |
| Remote GPU | set `*_REMOTE_URL` to an OpenAI-compatible/HTTP inference endpoint |

Weights are **never** downloaded at application startup; providers load lazily
on first job and fail with an explicit configuration message if unavailable.

## 6. Mock providers

Deterministic, clearly-flagged stand-ins used for development, tests and the
classroom demo when GPUs/weights are unavailable:

* `MockASR` — emits language-appropriate demo lecture segments spanning the
  real audio duration (segment timings come from the actual VAD segmentation).
* `MockLLM` — produces schema-valid notes and exactly 5 MCQs grounded in the
  provided transcript segments (extractive heuristics, no invented facts).
* `MockTranslation` — deterministic pseudo-translation that preserves
  structure/IDs (used only to exercise the translation pipeline end-to-end).

Every mock result carries `is_mock=True`; the API exposes per-provider mode at
`GET /api/v1/settings/providers`, and the UI shows a persistent badge.
