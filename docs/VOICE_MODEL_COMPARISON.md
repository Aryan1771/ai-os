# Local synthetic speech-model comparison

The runner uses **existing local files only**. It never opens a microphone, plays
audio, queries an account, sends text to a provider, downloads a model, changes the
selected model, or enables listening. Run from the existing project venv:

```bash
~/.ai_os/venv/bin/python -m pytest -q tests/test_voice_model_comparison.py
~/.ai_os/venv/bin/python -m ai_os.voice_model_comparison \
  --model ~/.ai_os/models/ggml-base.bin \
  --model ~/.ai_os/models/ggml-small.bin
```

The second file must already exist. Without `--model`, the saved Whisper model is
tested. One to three existing `ggml-*.bin` files inside this runtime's `models`
directory are accepted; symlinks, paths outside that directory and path traversal
are rejected. The saved English and Hindi Piper models and their JSON configs
must also be present there. Missing assets cause a public failure, never a download.

For each language, the installed Piper CLI synthesizes a fixed public phrase into
a private temporary WAV. FFmpeg resamples it to mono 16 kHz signed 16-bit PCM.
The same WAV is passed to each candidate in selected-language and per-utterance
matching modes through the real runtime transcription adapter. Each transcription
uses a fresh subprocess. Children run in bounded process groups, and temporary
audio/metadata is removed on normal completion or failure. The complete run has a
180-second budget, bounded subprocess output and per-worker time limits.

The optional `--script-hint` adds a separate Hindi-only CLI experiment using the
fixed context `हिन्दी भाषा, देवनागरी लिपि।`. That context is not the reference
sentence. It does not change the runtime adapter or save a preference; any apparent
improvement still needs separate phrases and owner microphone validation.

`--additional-hindi` adds three fixed sentences: a greeting, preparing for work
and asking about today's weather. They reduce dependence on the monitor sentence
and its borrowed English word; they remain synthetic TTS tests. No reference is
passed as a Whisper prompt.

Results contain fixed references, asset sizes/SHA256 values, accepted/rejected
state, language metadata, normalized exact match, word error rate (WER), character
error rate (CER), synthesis/resample time and transcription worker wall time.
Transcript text is withheld. Punctuation/case are normalized; combining marks are
preserved; CER excludes spaces. A transcript rejected by the runtime's script
guard has WER/CER `null`, rather than an invented score. A completed experiment's
`ok: true` does not mean every language passed.

Rows also report the fixed backend enum `cpu`, `cuda` or `unknown`. CUDA evidence
requires Whisper's actual `using CUDA0 backend` initialization and a positive CUDA
model-buffer allocation, without a failed-initialization marker. Detecting a CUDA
device alone is insufficient. Raw stderr is withheld; the evidence resets for
each transcription. Other backend formats remain `unknown` rather than guessed.

The optional NVIDIA sampler reports whole-device baseline and sampled peak during
**sequential Piper/STT stages**. It includes other existing GPU allocations, and
does not prove peak concurrent Ollama/STT/TTS memory, real microphone latency,
audibility, speaker matching, wake accuracy, accents or code switching. The small
fixed set is a regression probe, not a representative benchmark.

## Approved small-model provisioning

On 2026-10-20, the owner approved downloading and comparing the official
[multilingual small file](https://huggingface.co/ggerganov/whisper.cpp/blob/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-small.bin).
The official repository API reported:

- Revision: `5359861c739e955e79d9a303bcbc70fb988958b1`.
- File: `ggml-small.bin`, **487,601,967 bytes**.
- Published LFS SHA256:
  `1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b`.

The existing venv's `hf download` CLI downloaded that exact revision/file into a
new private staging directory with implicit authentication and telemetry disabled.
No package was installed. A first short attempt failed; the safe retry completed.
The staged size/SHA256 matched before creating the final file without overwriting
an existing destination. An independent final readback matched the same SHA256;
the regular final file is mode 0600. Staging was cleaned up. The saved model,
base file, enrollment profile and listening preferences were preserved.

Downloading/comparing this candidate does **not** approve selecting it as the
runtime model, changing service state, or redistributing it in an ISO. No model
file belongs in Git. See [guided checks](VOICE_DIAGNOSTICS.md) for physical
microphone/relevance/audibility acceptance.

## Initial CPU comparison

On 2026-10-20, the runner's **15 focused tests** and correctness lint passed before
the installed comparison. The command above, with `--script-hint`, completed in
**37.227 seconds**. Nothing was recorded or played aloud; the saved selection
remained `ggml-base.bin`.

| Model | Language | Mode | STT worker seconds | Accepted | WER | CER |
| --- | --- | --- | ---: | --- | ---: | ---: |
| base | English | selected | 1.111 | yes, normalized exact | 0 | 0 |
| base | English | match | 1.719 | yes, detected `en`, normalized exact | 0 | 0 |
| small | English | selected | 3.289 | yes, normalized exact | 0 | 0 |
| small | English | match | 6.251 | yes, detected `en`, normalized exact | 0 | 0 |
| base | Hindi | selected | 1.144 | no, script mismatch | — | — |
| base | Hindi | match | 1.999 | no, script mismatch | — | — |
| base | Hindi | fixed script hint | 2.432 | yes, incorrect transcript | 1.0000 | 0.8889 |
| small | Hindi | selected | 4.281 | yes, incorrect transcript | 0.5714 | 0.3704 |
| small | Hindi | match | 7.102 | yes, detected `hi`, incorrect transcript | 0.5714 | 0.3704 |
| small | Hindi | fixed script hint | 4.331 | yes, incorrect transcript | 0.5714 | 0.3704 |

Piper synthesis/resampling took 1.221/0.158 seconds for the 2.171-second English
clip and 1.263/0.045 seconds for the 2.299-second Hindi clip. GPU sampling produced
164 samples, zero sampling failures, **4680 MiB baseline and sampled peak**. That
existing allocation is included; the run did not demonstrate NVIDIA offload by
Whisper. This is not a simultaneous voice/model peak.

The small candidate improved the Hindi writing system on this sentence but still
misrecognized four of seven normalized words. Its automatic-language path was
slower. The script hint failed to repair accuracy and admitted an incorrect base
transcript; it is **not** a recommended runtime fix. TTS pronunciation and the
single chosen sentence also affect these scores. Further fixed phrases and owner
microphone checks are required before selecting a candidate. No runtime model
switch was approved or performed.

Asset identities for this run:

| Asset | SHA256 |
| --- | --- |
| `ggml-base.bin` | `60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe` |
| `ggml-small.bin` | `1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b` |
| `en_US-lessac-medium.onnx` | `5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f` |
| English JSON config | `efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0` |
| `hi_IN-pratham-medium.onnx` | `169964b0871667f6793416d4b35e97357a68ba1ad01df8580c28048989ee7693` |
| Hindi JSON config | `b68edd2cd7950dd436314013b7cd12e9699e5a3f6fe5af5af94294cf6aa7b9fd` |

## Installed transcription backend

Read-only package/library inspection found `whisper-cpp 1.9.5-1` (CLI reports
`1.9.5-dev`) with system `ggml 0.26.0-1`. `/usr/lib/ggml` contains CPU variants;
no CUDA/Vulkan backend was found there, and `ggml-cuda` is not installed. The CLI
links system GGML. Combined with the unchanged NVIDIA samples, this supports a
CPU-only explanation for the measured path; installing CUDA alone does not add a
Whisper CUDA backend.

An isolated user-space build was subsequently completed, following
[upstream NVIDIA build instructions](https://github.com/ggml-org/whisper.cpp/tree/d1be6fde11ac6e0407606b4e42fe72d34add8037#nvidia-gpu-support).
The inspected official release is v1.9.5, commit
`d1be6fde11ac6e0407606b4e42fe72d34add8037`. CMake 4.4.4, Ninja 1.13.2,
GCC/G++ 15.3.0 and CUDA 13.4.92 are already present; the GPU reports compute
capability 8.9. The fresh build used vendored GGML, CUDA architecture 89, two
parallel jobs, no curl/server/tests, no installation, and a 6 GiB build reserve
after checking free space. System libraries, PATH, the saved executable/model and
services were preserved. The initial table above predates this build.

The approved isolated build uses a **new** directory:
`~/.ai_os/build/whisper-cpp-v1.9.5-cuda-d1be6fde-d39xtlbz`.
Its private `regenos-build.json` records the completed artifact's upstream
revision and SHA256. The inspected upstream license is MIT. Build commands do not call
`install`, `ldconfig`, a model downloader or a service command:

```bash
cmake -S ~/.ai_os/build/whisper-cpp-v1.9.5-cuda-d1be6fde-d39xtlbz/source \
  -B ~/.ai_os/build/whisper-cpp-v1.9.5-cuda-d1be6fde-d39xtlbz/build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89 \
  -DCMAKE_CUDA_COMPILER=/opt/cuda/bin/nvcc \
  -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++-15 \
  -DCMAKE_C_COMPILER=/usr/bin/gcc-15 -DCMAKE_CXX_COMPILER=/usr/bin/g++-15 \
  -DBUILD_SHARED_LIBS=OFF -DGGML_BACKEND_DL=OFF -DWHISPER_USE_SYSTEM_GGML=OFF \
  -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=OFF \
  -DWHISPER_BUILD_EXAMPLES=ON -DWHISPER_CURL=OFF -DGGML_CUDA_NCCL=OFF
cmake --build ~/.ai_os/build/whisper-cpp-v1.9.5-cuda-d1be6fde-d39xtlbz/build \
  --target whisper-cli --parallel 2
```

The comparison's optional `--whisper-cli` accepts only a regular executable ELF
inside a private build with that exact official revision and a matching binary
SHA256 manifest. Arbitrary commands, symlinks, changed binaries and public/tampered
manifests are rejected. This is accidental-misconfiguration protection in the
same user account, not a cryptographic authentication or sandbox boundary.
Passing a candidate to the comparison never changes the saved runtime executable.

## Completed CUDA build and five-phrase comparison

The build was interrupted near completion and then resumed for its final eight
steps; it was not a fresh uninterrupted build. The resulting executable is
`~/.ai_os/build/whisper-cpp-v1.9.5-cuda-d1be6fde-d39xtlbz/build/bin/whisper-cli`,
**70,642,360 bytes**, SHA256
`858821c4f683a6066bfe3cc455b340d65292fa19bdce5b65206cde3b36f4166f`.
The installed `/usr/bin/whisper-cli` remains unchanged. Leaving this candidate
unused was the pre-selection rollback; there is no system installation to undo.

After **56 focused comparison/STT regression tests passed**, the same two model
files and Piper assets were compared with one fixed English sentence and all four
fixed Hindi sentences, using both selected-language and matching modes. These
commands each produce 20 rows and do not include the script-hint experiment:

```bash
~/.ai_os/venv/bin/python -m ai_os.voice_model_comparison \
  --model ~/.ai_os/models/ggml-base.bin \
  --model ~/.ai_os/models/ggml-small.bin --additional-hindi
~/.ai_os/venv/bin/python -m ai_os.voice_model_comparison \
  --model ~/.ai_os/models/ggml-base.bin \
  --model ~/.ai_os/models/ggml-small.bin --additional-hindi \
  --whisper-cli ~/.ai_os/build/whisper-cpp-v1.9.5-cuda-d1be6fde-d39xtlbz/build/bin/whisper-cli
```

Only sanitized metrics from the private reports were reviewed. No microphone was
opened, audio played, private speech inspected, or runtime setting changed.

| Run | Total seconds | Row backend | GPU samples / failures | Baseline / sampled peak MiB |
| --- | ---: | --- | ---: | ---: |
| System CLI | 80.243 | `cpu`, all 20 | 352 / 1 | 21 / 21 |
| Isolated CUDA CLI | 22.500 | `cuda`, all 20 | 101 / 0 | 21 / 961 |

Ollama was unloaded for these sequential runs. The CUDA initialization, positive
model-buffer evidence and memory rise confirm NVIDIA offload for this candidate.
The 961 MiB figure is a sampled whole-device peak during sequential Piper/STT;
it is **not** the peak of concurrent Ollama, STT, TTS and desktop use. The CPU
sampler missed one sample, and sampled peaks can miss short allocations.

All English rows were normalized exact matches. STT worker times include a fresh
subprocess and model initialization; the first CUDA row had a cold-start cost and
was slower than its CPU counterpart. These are individual observations, not
averages or a guarantee of full conversation latency:

| Model | Mode | CPU seconds | CUDA seconds |
| --- | --- | ---: | ---: |
| base | selected | 0.997 | 2.558, first CUDA row |
| base | match | 1.558 | 0.600 |
| small | selected | 2.959 | 0.630 |
| small | match | 5.606 | 0.647 |

Base failed the Hindi script guard on **all four** phrases in both modes and
backends. Its rejected rows have no WER/CER score. Small passed the language/script
guard on all four phrases, and matching mode detected `hi`; **none** was a
normalized exact match. The following scores were identical between selected and
matching modes within each backend:

| Hindi sample | CPU small WER / CER | CUDA small WER / CER | CPU small seconds, selected / match | CUDA small seconds, selected / match |
| --- | ---: | ---: | ---: | ---: |
| 0: new monitor | 0.5714 / 0.4815 | 0.7143 / 0.4815 | 5.745 / 8.337 | 0.792 / 0.850 |
| 1: greeting | 0.5000 / 0.0500 | 0.5000 / 0.0500 | 5.792 / 8.149 | 0.783 / 0.751 |
| 2: work preparation | 0.1429 / 0.0400 | 0.1429 / 0.0400 | 3.554 / 6.098 | 0.738 / 0.807 |
| 3: weather | 0.8333 / 0.4091 | 1.0000 / 0.3636 | 3.779 / 6.236 | 0.817 / 0.832 |

WER includes word-boundary differences; low CER with higher WER should not be
treated as proof of the same amount of semantic error. Piper pronunciation,
decoder/backend differences and this small sample limit interpretation. These
results show a latency improvement and more suitable Hindi script handling, but
do **not** establish reliable Hindi transcription or real microphone acceptance.
The comparison itself left the base model and system CLI selected. Afterwards,
the owner separately approved switching **only** the `whisper_cli` setting to
the verified CUDA executable above. A private backup was created at
`~/.ai_os/backups/cuda-backend-vyhpgela/config.json` before the atomic key-only
update. The base model, language, enrollment profile, listening state and every
other configuration key were preserved. No service was restarted, so an existing
long-lived process may still hold its previous configuration until reloaded.

Rollback must restore only the saved `whisper_cli` value from that backup into
the current configuration, using the same atomic settings writer. It must not
copy the backup over the whole current file, which could overwrite concurrent
settings changes. Selecting small remains unapproved. Guided English/Hindi
microphone and end-to-end response checks are still required; the faster backend
does not establish reliable Hindi transcription.
