ARG BASE_IMAGE=alibaba-cloud-linux-3-registry.cn-hangzhou.cr.aliyuncs.com/alinux3/python:3.11.1

FROM ${BASE_IMAGE} AS builder

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=mirrors.aliyun.com \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    HF_HOME=/opt/model-cache/huggingface \
    TRANSFORMERS_CACHE=/opt/model-cache/huggingface \
    XDG_CACHE_HOME=/opt/model-cache

WORKDIR /app

RUN python -m venv "${VIRTUAL_ENV}" && \
    pip install --upgrade pip setuptools wheel

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

# 预下载 BGE Embedding + Reranker 模型到缓存目录
RUN python -c "\
from FlagEmbedding import BGEM3FlagModel, FlagReranker; \
BGEM3FlagModel('BAAI/bge-m3', use_fp16=False); \
FlagReranker('BAAI/bge-reranker-large', use_fp16=False)"

# ── 运行时镜像 ──────────────────────────────────────────
FROM ${BASE_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    HF_HOME=/opt/model-cache/huggingface \
    TRANSFORMERS_CACHE=/opt/model-cache/huggingface \
    XDG_CACHE_HOME=/opt/model-cache

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/model-cache /opt/model-cache
COPY pyproject.toml ./
COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
