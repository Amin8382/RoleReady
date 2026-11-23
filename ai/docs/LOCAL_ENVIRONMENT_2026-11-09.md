# Mission 001: Windows environment evidence (9 November 2026)

Workspace: `C:\Users\gasmi\Downloads\amin\RoleReady`.
Branch: `feat/amin-five-model-runtime`, based on `91c147b`.
This is a synthetic runtime check, not an integrated product or quality benchmark.

## Machine and initial state

| Item | Observed value |
| --- | --- |
| OS | Windows 11 Home, 64-bit, build 10.0.26200 |
| CPU | Intel Core i9-13905H, 14 cores / 20 logical processors |
| System RAM reported by WMI | 33,946,087,424 bytes (about 31.61 GiB) |
| Discrete GPU | NVIDIA GeForce RTX 4080 Laptop GPU |
| Dedicated VRAM from NVIDIA-SMI | 12,282 MiB; approximately 10,013 MiB free at initial diagnostic |
| Other graphics | Intel Iris Xe Graphics |
| NVIDIA driver | 610.62 |
| Driver CUDA capability | 13.3 reported by NVIDIA-SMI; this is not an installed CUDA toolkit |
| System disk C: | 1,022,484,615,168 bytes; initially 166,538,969,088 bytes free (155.10 GiB) |
| Original Python | `C:\Python314\python.exe`, 3.14.5 |
| Original `ai/.venv` | Python 3.14.5; original package/test dependencies; preserved |
| Original user PyTorch | 2.12.0+cpu; `torch.version.cuda is None`; CUDA unavailable |
| New isolated interpreter | CPython 3.11.18 in `ai/.runtime/python/`, environment `ai/.venv311/` |
| Verified new PyTorch | 2.11.0+cu128, CUDA runtime 12.8, CUDA available, compute capability 8.9 |
| Remaining C: space after setup | 146.79 GiB |
| Existing supporting tools | eSpeak NG, Ollama 0.40.15, Docker, WSL (Ubuntu 24.04 and docker-desktop) |

No CUDA compiler (`nvcc`) was found on PATH. A compatible PyTorch wheel bundles
the CUDA runtime needed for these checks; installing a system toolkit is not
part of this mission. WMI's `AdapterRAM` truncates this GPU to roughly 4 GB;
use NVIDIA-SMI's dedicated-memory reading instead.

The outer checkout initially used `feat/amin-ai-data-pipeline` at `6bbeabd`.
Fetching origin exposed the existing runtime branch, which was checked out
without overwriting changes. The accidental `ai/RoleReady/` clone is clean at
`6bbeabde91d3babf4ef002e99d36ca0b4722ed6d`, with no local-only branch commits
relative to its cached remote refs. It remains intact and must not be staged.

## Isolated installation

Run these commands from `ai/` in PowerShell. They do not change PATH, the Windows
registry, execution policy, NVIDIA drivers or the original virtual environment.
The archive is portable tooling, not a system installer.

```powershell
New-Item -ItemType Directory -Path .runtime/tools -Force | Out-Null
Invoke-WebRequest https://github.com/astral-sh/uv/releases/download/0.13.7/uv-x86_64-pc-windows-msvc.zip -OutFile .runtime/tools/uv.zip
Get-FileHash .runtime/tools/uv.zip -Algorithm SHA256
Expand-Archive .runtime/tools/uv.zip -DestinationPath .runtime/tools/uv
$env:UV_CACHE_DIR="$PWD/.runtime/cache/uv"
$env:UV_PYTHON_INSTALL_DIR="$PWD/.runtime/python"
.runtime/tools/uv/uv.exe python install 3.11.18 --no-bin --no-registry
.runtime/tools/uv/uv.exe venv .venv311 --python 3.11.18 --seed
$env:PIP_CACHE_DIR="$PWD/.runtime/cache/pip"
.venv311/Scripts/python.exe -m pip install -e ".[retrieval,voice,test]"
.venv311/Scripts/python.exe -m pip install "torch==2.11.0+cu128" --index-url https://download.pytorch.org/whl/cu128
.venv311/Scripts/python.exe -m pip install "huggingface-hub==1.33.0"
```

The downloaded uv 0.13.7 archive SHA-256 was
`0CDC5B38FE5A8168ED6A25814F5BA43C21D313DD3187314FCCB37B7CEC46E021`.
Do not overwrite an existing environment when repeating setup; use another
directory for an independent reproduction.

uv provisioned Python successfully but its parallel dependency installation
encountered repeated Windows cache rename/access errors. The environment was
then populated successfully using its own pip. The first dependency resolution
selected CPU-only torch 2.15.0; the explicit CUDA wheel installation replaces
that package only inside `.venv311`.

Hugging Face Hub 2.4.0/Xet transfers stalled in this session. Standard HTTPS with
Xet disabled and Hub 1.33.0 completed the BGE transfer. This observation does not
establish an upstream defect. The final environment must retain the verified
package versions instead of resolving all dependencies afresh.

The exact installed dependency snapshot is
[`requirements-windows-cu128-py311.lock.txt`](../requirements-windows-cu128-py311.lock.txt).
It is specific to Windows x64 / Python 3.11, not the Linux CI environment. In a
fresh isolated environment, install the CUDA torch wheel from the official index
first, then install the lock and editable package:

```powershell
.venv311/Scripts/python.exe -m pip install "torch==2.11.0+cu128" --index-url https://download.pytorch.org/whl/cu128
.venv311/Scripts/python.exe -m pip install -r requirements-windows-cu128-py311.lock.txt
.venv311/Scripts/python.exe -m pip install -e ".[retrieval,voice,test]" -c requirements-windows-cu128-py311.lock.txt
```

The lock includes Kokoro 0.9.4, faster-whisper 1.2.1, CTranslate2 4.8.5,
sentence-transformers 5.7.0, FAISS CPU 1.15.1, numpy 2.4.6, transformers 5.22.2,
Hub 1.33.0 and soundfile 0.14.0. `en_core_web_sm` 3.8.0 is pinned to its official
wheel URL and SHA-256. The snapshot is version-pinned; it is not a fully hashed
wheelhouse. `pip install --dry-run -r ...` passed against the actual environment;
a second clean-machine installation has not been performed.

## Model revisions and commands

| Model | Publisher revision used |
| --- | --- |
| BGE-small-en-v1.5 | `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` |
| faster-whisper-small.en | `d1d751a5f8271d482d14ca55d9e2deeebbae577f` |
| Kokoro-82M | `f3ff3571791e39611d31c381e3a41a3af07b4987` |

```powershell
$env:HF_HOME="$PWD/.runtime/huggingface"
$env:HF_HUB_DISABLE_TELEMETRY="1"
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN="1"
$env:HF_HUB_DISABLE_XET="1"
.venv311/Scripts/python.exe -m pip check
.venv311/Scripts/python.exe -m pytest -q
.venv311/Scripts/python.exe -m roleready_ai.local_benchmark bge --device cuda --revision 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a --report outputs/bge-cuda.json
.venv311/Scripts/python.exe -m roleready_ai.local_benchmark kokoro --device cuda --revision f3ff3571791e39611d31c381e3a41a3af07b4987 --report outputs/kokoro-cuda.json
.venv311/Scripts/python.exe -m roleready_ai.local_benchmark whisper --device cpu --revision d1d751a5f8271d482d14ca55d9e2deeebbae577f --audio outputs/question.wav --report outputs/whisper-cpu.json
$env:PATH="$PWD/.venv311/Lib/site-packages/torch/lib;$env:PATH"
.venv311/Scripts/python.exe -m roleready_ai.local_benchmark whisper --device cuda --revision d1d751a5f8271d482d14ca55d9e2deeebbae577f --audio outputs/question.wav --report outputs/whisper-cuda.json
```

The CUDA Whisper command was verified with the venv's torch DLL directory added
to **that shell process's** PATH. It supplies CUDA 12 cuBLAS and cuDNN 9 to
CTranslate2; no permanent/system PATH change or separate toolkit install occurred.
CPU Whisper was additionally tested against a Windows SAPI synthetic WAV,
generated locally with the same sentence and an English voice, before the CUDA
replacement. Its command used `--device cpu --audio outputs/synthetic-sapi.wav
--report outputs/whisper-cpu-sapi.json`.

Only public model assets and synthetic text/audio were used. Reports, weights,
tool caches and audio stay in ignored local directories. The public Kokoro model
was already cached under the Windows user account; a copy was made inside the
workspace rather than downloading its 327,212,226-byte checkpoint again.
Kokoro additionally needs the `en_core_web_sm` language package for phonemization.

## Verified results

Before CUDA replacement, the original 17 AI tests passed under Python 3.11.18
and `pip check` found no broken requirements. Retrieval/voice libraries imported
successfully. Running pytest from the repository root incorrectly collected the
nested clone and backend tests; use the documented `ai/` working directory.
Sandbox-account temp-directory errors disappeared under the Windows user;
these were environment errors, not AI package assertion failures.

Real BGE/FAISS CPU inference passed with torch 2.15.0+cpu: artifact preparation
90,665.43 ms, model loading 1,107.18 ms, embedding/indexing 262.54 ms, query
32.23 ms. Three 384-dimensional vectors were indexed. SQL ranked first
(0.916508), the general teamwork question second (0.508591), and the unrelated
frontend question was excluded. This early CPU baseline precedes the final CUDA
environment; it is not a CUDA measurement.

The final CUDA environment passed the **17 existing AI tests in 0.36 seconds**,
`pip check`, the Windows readiness script (with an explicit interpreter), and
the following real GPU checks. The explicit CUDA tensor test returned 8.0 for eight ones, and torch.cuda.is_available() was True:

| Model / actual backend | Artifact preparation ms | Model loading ms | Inference ms | Result |
| --- | ---: | ---: | ---: | --- |
| BGE / torch CUDA + CPU FAISS | 1,342.16 | 1,329.65 | 135.51 | SQL first; unrelated role excluded; 384 dimensions |
| Kokoro / torch CUDA, af_heart | 1,298.09 | 5,335.36 | 3,531.54 | 3.2 seconds of finite, non-silent 24 kHz audio |
| Whisper / CTranslate2 CUDA FP16 | 1,351.66 | 1,671.37 | 1,448.03 | Exact transcription of Kokoro's sentence |

BGE's separate three-question embedding/index build took **671.20 ms** on CUDA.
The GPU samples were run sequentially in separate processes. Already-cached
artifacts account for the short preparation times above.

| GPU run | Whole GPU used baseline / after load / after inference (MiB) | Torch peak allocated (MiB) |
| --- | --- | ---: |
| BGE | 1,475 / 1,688 / 1,745 | 137.26 |
| Kokoro | 1,598 / 1,963 / 2,318 | 614.48 |
| Whisper | 1,598 / 2,176 / 2,194 | Not applicable: CTranslate2 allocations |

The synthetic sentence and Whisper's exact output were both:
**"Tell me about an engineering project you built."**
Kokoro's CUDA WAV peak amplitude was 0.357147; its CPU WAV was also non-silent
and 3.2 seconds long. The earlier CPU Kokoro run took 2,422.68 ms for inference;
its 170,492.75 ms first setup/load phase **included the spaCy language-package
download/install**, so it must not be compared with cached model loading.
The earlier Whisper CPU int8 run loaded in 3,105.11 ms and transcribed Windows
SAPI audio in 4,849.17 ms, after 328,036.87 ms artifact preparation/download.
The final torch 2.11.0+cu128 environment also passed CPU int8 Whisper on Kokoro's
WAV: 1,398.65 ms preparation, 2,947.42 ms loading and 4,777.69 ms inference, with
the same exact transcript (`outputs/whisper-cpu.json`).

Detailed local records: `ai/outputs/bge-cpu.json`, `bge-cuda.json`,
`kokoro-cpu.json`, `kokoro-cuda.json`, `whisper-cpu-sapi.json` and
`whisper-cpu.json` and `whisper-cuda.json` (all under `ai/outputs/`). Audio: `question.wav`,
`question-cpu.wav`, `synthetic-sapi.wav`. These remain gitignored. No runtime
assertion failed once dependencies and weights were available; no existing AI
test assertion needed a code fix. Setup issues and interrupted transfers are
recorded above rather than being reported as model successes.

Timings exclude Python import overhead. Artifact preparation includes downloads
and metadata requests; model loading is measured separately. Single-query times
are smoke observations, not statistically reliable latency benchmarks. NVIDIA-SMI
snapshots include desktop/other processes; torch peak allocation excludes
CTranslate2 and other non-torch allocations.

## Large-model serving assessment (no weights downloaded)

For 12 GiB VRAM, begin with **one quantized large model loaded at a time**, a
short context (initially around 4K tokens), one request at a time, and explicit
unloading between Qwen and Prometheus. This is a capacity recommendation, not a
measured guarantee. FP16 Prometheus requires roughly 14 GB for weights alone,
before KV cache and runtime overhead; simultaneous full-precision serving is
unsuitable here.

- **Qwen:** the [Ollama Qwen3.5 4B Q4_K_M listing](https://ollama.com/library/qwen3.5:4b-q4_K_M)
  provides a 3.3 GB package. Ollama is already installed, with only
  `llama3.2:1b` currently listed locally. Its [OpenAI-compatible interface](https://docs.ollama.com/api/openai-compatibility)
  matches the adapter shape; the actual served ID must be configured explicitly.
  Verify the installed Ollama version supports Qwen3.5 before an approved pull.
- **Prometheus:** the [publisher's GGUF repository](https://huggingface.co/prometheus-eval/prometheus-7b-v2.0-GGUF)
  lists Q4_K_M (about 4.37 GB). A current CUDA build of llama.cpp is a candidate
  native-Windows server; Ollama also documents [GGUF import](https://docs.ollama.com/import).
  Preserve the Mistral conversation template and the four rubric prompts, then
  calibrate quantized scores against human ratings.
- **vLLM:** [upstream requirements](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)
  specify Linux; use a separate WSL/Linux environment if selected. Do not install
  it into this Windows voice/retrieval environment.

[Qwen's model card](https://huggingface.co/Qwen/Qwen3.5-4B) notes that thinking is
enabled by default. Configure and verify non-thinking responses at the chosen
server/API boundary so the existing strict JSON adapter receives a JSON object
within its output budget. No endpoint compatibility or seven-question live
generation has been proven yet. Both large-model endpoints remain unconfigured.

## Readiness and next handoff

| Model | State after this mission |
| --- | --- |
| BGE + FAISS | Real CPU and CUDA embedding/retrieval smoke passed; quality/persistence evaluation pending |
| Whisper Small English | Real CPU int8 and CUDA FP16 transcription passed on synthetic English speech |
| Kokoro 82M | Real CPU and CUDA audio generation passed; CUDA audio transcribed exactly by Whisper |
| Qwen3.5 4B | Adapter/unit tests present; weights not downloaded; no real inference |
| Prometheus 7B v2 | Adapter/mock tests present; weights not downloaded; no real inference or calibration |

Remaining gates: choose/verify a quantized large-model server and exact artifact,
then (in a separately authorized download task) test live Qwen structured output
and seven grounded questions against synthetic CV/job input. Integrate through
Oussema's backend contracts before Khaled connects the UI. Prometheus reference
curation and two-reviewer calibration, privacy/session persistence, voice UI,
held-out retrieval quality, accent/noise tests and end-to-end validation remain
unfinished. Do not interpret these smoke checks as completion of those gates.
