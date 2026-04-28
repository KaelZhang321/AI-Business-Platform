ARG BASE_IMAGE=alibaba-cloud-linux-3-registry.cn-hangzhou.cr.aliyuncs.com/alinux3/python:3.11.1

FROM ${BASE_IMAGE} AS builder

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG TORCH_VERSION=2.4.1+cpu
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=mirrors.aliyun.com \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    HOME=/opt/model-cache \
    HF_HOME=/opt/model-cache/huggingface \
    TRANSFORMERS_CACHE=/opt/model-cache/huggingface \
    XDG_CACHE_HOME=/opt/model-cache

WORKDIR /app

RUN python -m venv "${VIRTUAL_ENV}" && \
    pip install --upgrade pip setuptools wheel

COPY pyproject.toml ./

# 固定 CPU-only torch，避免 FlagEmbedding/peft 依赖解析时拉取数百 MB 的 nvidia_* CUDA 轮子。
RUN pip install --no-cache-dir --progress-bar off \
    "torch==${TORCH_VERSION}" \
    --index-url "${TORCH_INDEX_URL}" \
    --extra-index-url "${PIP_INDEX_URL}"

# 将第三方依赖与业务代码安装拆层，业务代码变更时可复用大依赖缓存。
RUN printf 'torch==%s\n' "${TORCH_VERSION}" > /tmp/constraints.txt && \
    python -c "import tomllib; cfg = tomllib.load(open('pyproject.toml', 'rb')); print('\\n'.join(cfg.get('project', {}).get('dependencies', [])))" > /tmp/requirements.txt && \
    pip install --no-cache-dir --progress-bar off \
      -c /tmp/constraints.txt \
      -r /tmp/requirements.txt \
      --extra-index-url "${TORCH_INDEX_URL}"

COPY app ./app

# 依赖已在上一层安装完成，这里只注册当前项目包，避免重复触发依赖解析。
RUN pip install --no-cache-dir --no-deps .

# 预下载 BGE Embedding + Reranker 模型到缓存目录
#RUN python -c "\
#from FlagEmbedding import BGEM3FlagModel, FlagReranker; \
#BGEM3FlagModel('BAAI/bge-m3', use_fp16=False); \
#FlagReranker('BAAI/bge-reranker-large', use_fp16=False)"

# ── 运行时镜像 ──────────────────────────────────────────
FROM ${BASE_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    HOME=/opt/model-cache \
    HF_HOME=/opt/model-cache/huggingface \
    TRANSFORMERS_CACHE=/opt/model-cache/huggingface \
    XDG_CACHE_HOME=/opt/model-cache

WORKDIR /app

# 统一容器时区为 Asia/Shanghai，避免与宿主机日志时间轴错位。
RUN if command -v dnf >/dev/null 2>&1; then \
      dnf install -y tzdata && dnf clean all; \
    elif command -v yum >/dev/null 2>&1; then \
      yum install -y tzdata && yum clean all; \
    else \
      echo "No package manager found for tzdata install" >&2; exit 1; \
    fi && \
    ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && \
    echo "${TZ}" >/etc/timezone

COPY --from=builder /opt/venv /opt/venv
COPY pyproject.toml ./
COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
