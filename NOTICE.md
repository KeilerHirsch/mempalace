# NOTICE

## MemPalace

Copyright (c) 2026 MemPalace Contributors

`mempalace` is licensed under the MIT License (see `LICENSE` in the repository root).

This notice lists third-party software packages that MemPalace depends on and may
distribute (directly or transitively). Each package remains governed by its own
license and copyright; this notice exists to satisfy the attribution obligations
of those licenses. The MemPalace MIT license does not relicense third-party code.

- Dependency resolution: `uv.lock`, commit `1b0d8405` (2026-08-02).
- License information: package metadata (PyPI), retrieved 2026-09-13. The
  authoritative license text ships inside each installed package; where package
  metadata is missing or ambiguous, the project's own `LICENSE`/`COPYING` file
  takes precedence.
- Dev/test/toolchain-only dependencies (pytest, ruff, mypy, pre-commit, etc.) are
  not installed for end users and are not listed here.

## Core runtime dependencies

| Package | Versions (uv.lock) | License (SPDX) | Homepage |
|---|---|---|---|
| `annotated-doc` | 0.0.4 | MIT | https://github.com/fastapi/annotated-doc |
| `annotated-types` | 0.7.0 | MIT | https://github.com/annotated-types/annotated-types |
| `anyio` | 4.12.1, 4.13.0 | MIT | — |
| `attrs` | 26.1.0 | MIT | — |
| `bcrypt` | 5.0.0 | Apache-2.0 | — |
| `build` | 1.4.2 | MIT | — |
| `certifi` | 2026.2.25 | MPL-2.0 | https://github.com/certifi/python-certifi |
| `charset-normalizer` | 3.4.7 | MIT | — |
| `chromadb` | 1.5.7 | Apache-2.0 | https://github.com/chroma-core/chroma |
| `click` | 8.1.8, 8.3.2 | BSD-3-Clause | https://github.com/pallets/click/ |
| `colorama` | 0.4.6 | BSD-3-Clause | https://github.com/tartley/colorama |
| `coloredlogs` | 15.0.1 | MIT | https://coloredlogs.readthedocs.io |
| `durationpy` | 0.10 | MIT | https://github.com/icholy/durationpy |
| `exceptiongroup` | 1.3.1 | MIT | — |
| `filelock` | 3.19.1, 3.25.2 | Unlicense (3.19.1) / MIT (3.25.2) [Wechsel im Lock] | https://github.com/tox-dev/py-filelock |
| `flatbuffers` | 25.12.19 | Apache-2.0 | https://google.github.io/flatbuffers/ |
| `fsspec` | 2025.10.0, 2026.3.0 | BSD-3-Clause | https://github.com/fsspec/filesystem_spec |
| `googleapis-common-protos` | 1.74.0 | Apache-2.0 | https://github.com/googleapis/google-cloud-python/tree/main/packages/googleapis-common-protos |
| `grpcio` | 1.80.0 | Apache-2.0 | https://grpc.io |
| `h11` | 0.16.0 | MIT | https://github.com/python-hyper/h11 |
| `hf-xet` | 1.4.3 | Apache-2.0 | https://github.com/huggingface/xet-core |
| `httpcore` | 1.0.9 | BSD-3-Clause | https://www.encode.io/httpcore/ |
| `httptools` | 0.7.1 | MIT | https://github.com/MagicStack/httptools |
| `httpx` | 0.28.1 | BSD-3-Clause | https://github.com/encode/httpx |
| `huggingface-hub` | 1.8.0, 1.9.1 | Apache-2.0 | https://github.com/huggingface/huggingface_hub |
| `humanfriendly` | 10.0 | MIT | https://humanfriendly.readthedocs.io |
| `idna` | 3.11 | BSD-3-Clause | https://github.com/kjd/idna |
| `importlib-metadata` | 8.7.1 | Apache-2.0 | https://github.com/python/importlib_metadata |
| `importlib-resources` | 6.5.2 | Apache-2.0 | https://github.com/python/importlib_resources |
| `jsonschema` | 4.25.1, 4.26.0 | MIT | https://github.com/python-jsonschema/jsonschema |
| `jsonschema-specifications` | 2025.9.1 | MIT | https://github.com/python-jsonschema/jsonschema-specifications |
| `kubernetes` | 35.0.0 | Apache-2.0 | https://github.com/kubernetes-client/python |
| `markdown-it-py` | 3.0.0, 4.0.0 | MIT | https://github.com/executablebooks/markdown-it-py |
| `mdurl` | 0.1.2 | MIT | https://github.com/executablebooks/mdurl |
| `mmh3` | 5.2.0, 5.2.1 | MIT | https://pypi.org/project/mmh3/ |
| `mpmath` | 1.3.0 | BSD-3-Clause | http://mpmath.org/ |
| `numpy` | 2.0.2, 2.2.6, 2.4.4 | BSD-3-Clause (Komponenten: 0BSD/MIT/Zlib/CC0-1.0) | https://numpy.org |
| `oauthlib` | 3.3.1 | BSD-3-Clause | https://github.com/oauthlib/oauthlib |
| `onnxruntime` | 1.20.1, 1.24.3, 1.24.4 | MIT | https://onnxruntime.ai |
| `opentelemetry-api` | 1.40.0 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-api |
| `opentelemetry-exporter-otlp-proto-common` | 1.40.0 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/exporter/opentelemetry-exporter-otlp-proto-common |
| `opentelemetry-exporter-otlp-proto-grpc` | 1.40.0 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/exporter/opentelemetry-exporter-otlp-proto-grpc |
| `opentelemetry-proto` | 1.40.0 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-proto |
| `opentelemetry-sdk` | 1.40.0 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-sdk |
| `opentelemetry-semantic-conventions` | 0.61b0 | Apache-2.0 | https://github.com/open-telemetry/opentelemetry-python/tree/main/opentelemetry-semantic-conventions |
| `orjson` | 3.11.5, 3.11.8 | Apache-2.0 OR MIT (3.11.5) / MPL-2.0 AND (Apache-2.0 OR MIT) (3.11.8) [Wechsel im Lock] | — |
| `overrides` | 7.7.0 | Apache-2.0 | https://github.com/mkorpela/overrides |
| `packaging` | 26.0 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging |
| `protobuf` | 6.33.6 | 3-Clause BSD License | https://developers.google.com/protocol-buffers/ |
| `pybase64` | 1.4.3 | BSD-2-Clause | https://github.com/mayeut/pybase64 |
| `pydantic` | 2.12.5 | MIT | https://github.com/pydantic/pydantic |
| `pydantic-core` | 2.41.5 | MIT | https://github.com/pydantic/pydantic-core |
| `pydantic-settings` | 2.11.0, 2.13.1 | MIT | https://github.com/pydantic/pydantic-settings |
| `pygments` | 2.20.0 | BSD-2-Clause | https://pygments.org |
| `pypika` | 0.51.1 | Apache-2.0 | https://github.com/kayak/pypika |
| `pyproject-hooks` | 1.2.0 | MIT | https://github.com/pypa/pyproject-hooks |
| `pyreadline3` | 3.5.4 | BSD-3-Clause | https://github.com/pyreadline3/pyreadline3 |
| `python-dateutil` | 2.9.0.post0 | Apache-2.0 / BSD-3-Clause (Dual) | https://github.com/dateutil/dateutil |
| `python-dotenv` | 1.2.1, 1.2.2 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| `pyyaml` | 6.0.3 | MIT | https://pyyaml.org/ |
| `referencing` | 0.36.2, 0.37.0 | MIT | https://github.com/python-jsonschema/referencing |
| `requests` | 2.32.5, 2.33.1 | Apache-2.0 | https://requests.readthedocs.io |
| `requests-oauthlib` | 2.0.0 | ISC | https://github.com/requests/requests-oauthlib |
| `rich` | 14.3.3 | MIT | https://github.com/Textualize/rich |
| `rpds-py` | 0.27.1, 0.30.0 | MIT | https://github.com/crate-py/rpds |
| `shellingham` | 1.5.4 | ISC | https://github.com/sarugaku/shellingham |
| `six` | 1.17.0 | MIT | https://github.com/benjaminp/six |
| `sympy` | 1.14.0 | BSD-3-Clause | https://sympy.org |
| `tenacity` | 9.1.2, 9.1.4 | Apache-2.0 | https://github.com/jd/tenacity |
| `tokenizers` | 0.22.2 | Apache-2.0 | https://github.com/huggingface/tokenizers |
| `tomli` | 2.4.1 | MIT | https://github.com/hukkin/tomli |
| `tqdm` | 4.67.3 | MPL-2.0 AND MIT | — |
| `typer` | 0.23.2, 0.24.1 | MIT | https://github.com/fastapi/typer |
| `typing-extensions` | 4.15.0 | PSF-2.0 | https://github.com/python/typing_extensions |
| `typing-inspection` | 0.4.2 | MIT | https://github.com/pydantic/typing-inspection |
| `urllib3` | 2.6.3 | MIT | — |
| `uvicorn` | 0.39.0, 0.44.0 | BSD-3-Clause | https://uvicorn.dev/ |
| `uvloop` | 0.22.1 | MIT | — |
| `watchfiles` | 1.1.1 | MIT | https://github.com/samuelcolvin/watchfiles |
| `websocket-client` | 1.9.0 | Apache-2.0 | https://github.com/websocket-client/websocket-client.git |
| `websockets` | 15.0.1, 16.0 | BSD-3-Clause | https://github.com/python-websockets/websockets |
| `zipp` | 3.23.0 | MIT | https://github.com/jaraco/zipp |

### Optional extra: extract (binary/text extraction)

| Package | Versions (uv.lock) | License (SPDX) | Homepage |
|---|---|---|---|
| `beautifulsoup4` | 4.14.3 | MIT / MIT License | https://www.crummy.com/software/BeautifulSoup/bs4/ |
| `cffi` | 2.0.0 | MIT | https://github.com/python-cffi/cffi |
| `cobble` | 0.1.4 | BSD (PyPI-Klassifikator; Quelltext prüfen) | http://github.com/mwilliamson/python-cobble |
| `cryptography` | 48.0.0 | Apache-2.0 OR BSD-3-Clause | — |
| `defusedxml` | 0.7.1 | PSF-2.0 | https://github.com/tiran/defusedxml |
| `et-xmlfile` | 2.0.0 | MIT | https://foss.heptapod.net/openpyxl/et_xmlfile |
| `librt` | 0.11.0 | MIT | https://github.com/mypyc/librt |
| `lxml` | 6.1.1 | BSD-3-Clause | https://lxml.de/ |
| `magika` | 0.6.2, 0.6.3 | Apache-2.0 | https://github.com/google/magika |
| `mammoth` | 1.11.0 | BSD-2-Clause | https://github.com/mwilliamson/python-mammoth |
| `markdownify` | 1.2.2 | MIT | http://github.com/matthewwithanm/python-markdownify |
| `markitdown` | 0.1.5 | MIT | https://github.com/microsoft/markitdown |
| `openpyxl` | 3.1.5 | MIT | https://openpyxl.readthedocs.io |
| `pdfminer-six` | 20251230 | MIT | https://github.com/pdfminer/pdfminer.six |
| `pdfplumber` | 0.11.9 | MIT | https://github.com/jsvine/pdfplumber |
| `pillow` | 12.2.0 | MIT-CMU | https://python-pillow.github.io |
| `platformdirs` | 4.4.0, 4.9.6 | MIT | https://github.com/tox-dev/platformdirs |
| `pycparser` | 3.0 | BSD-3-Clause | https://github.com/eliben/pycparser |
| `pypdfium2` | 5.8.0 | BSD-3-Clause / Apache-2.0 (gemischt) | https://github.com/pypdfium2-team/pypdfium2 |
| `python-discovery` | 1.3.1 | MIT | https://github.com/tox-dev/python-discovery |
| `python-pptx` | 1.0.2 | MIT | https://github.com/scanny/python-pptx |
| `soupsieve` | 2.8.4 | MIT | https://github.com/facelessuser/soupsieve |
| `striprtf` | 0.0.32 | BSD-3-Clause | https://github.com/joshy/striprtf |
| `xlsxwriter` | 3.2.9 | BSD-2-Clause | https://github.com/jmcnamara/XlsxWriter |

### Optional extra: milvus backend

| Package | Versions (uv.lock) | License (SPDX) | Homepage |
|---|---|---|---|
| `cachetools` | 6.2.6, 7.1.4 | MIT | https://github.com/tkem/cachetools/ |
| `faiss-cpu` | 1.14.3 | MIT | https://github.com/facebookresearch/faiss |
| `milvus-lite` | 3.0 | Apache-2.0 | https://github.com/milvus-io/milvus-lite |
| `pandas` | 2.3.3, 3.0.3 | BSD-3-Clause | — |
| `pyarrow` | 24.0.0 | Apache-2.0 | https://arrow.apache.org/ |
| `pymilvus` | 3.0.0 | Apache-2.0 | — |
| `pytz` | 2026.2 | MIT | http://pythonhosted.org/pytz |
| `setuptools` | 82.0.1 | MIT | https://github.com/pypa/setuptools |

### Optional extra: pgvector backend

| Package | Versions (uv.lock) | License (SPDX) | Homepage |
|---|---|---|---|
| `psycopg` | 3.2.13, 3.3.4 | LGPL-3.0-only | https://psycopg.org/ |
| `psycopg-binary` | 3.2.13, 3.3.4 | LGPL-3.0-only | https://psycopg.org/ |
| `tzdata` | 2026.2 | Apache-2.0 | https://github.com/python/tzdata |

### Optional extra: gpu (ONNX Runtime CUDA)

| Package | Versions (uv.lock) | License (SPDX) | Homepage |
|---|---|---|---|
| `onnxruntime-gpu` | 1.20.2, 1.24.3, 1.25.0 | MIT | https://onnxruntime.ai |

### Optional extra: dml (ONNX Runtime DirectML)

| Package | Versions (uv.lock) | License (SPDX) | Homepage |
|---|---|---|---|
| `onnxruntime-directml` | 1.20.1, 1.24.3, 1.24.4 | MIT | https://onnxruntime.ai |

### Optional extra: spellcheck

| Package | Versions (uv.lock) | License (SPDX) | Homepage |
|---|---|---|---|
| `autocorrect` | 2.6.1 | LGPL-3.0 | https://github.com/fsondej/autocorrect |

## Maintenance note

Licenses change between releases (for example, `orjson` and `filelock` differ
between the versions pinned in this lock, and `pathspec` moved from MIT to
MPL-2.0). Maintainers must re-verify license metadata and this notice on every
dependency update, and include any changed entries in the same commit as the
update.

_Generated 2026-09-13 from `uv.lock` @ 1b0d8405. SPDX identifiers per the SPDX
License List; the authoritative terms are the license texts shipped with each
package._
