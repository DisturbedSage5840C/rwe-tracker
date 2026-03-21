# syntax=docker/dockerfile:1.7
# NOTE: This image is intentionally large (~3GB) because models are baked in for zero cold-start download latency.

ARG PYTHON_IMAGE=python:3.11-slim

FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV VENV_PATH=/opt/venv

WORKDIR /build

RUN apt-get update \
	&& apt-get install -y --no-install-recommends gcc g++ build-essential curl \
	&& python -m venv ${VENV_PATH} \
	&& ${VENV_PATH}/bin/pip install --upgrade pip setuptools wheel \
	&& rm -rf /var/lib/apt/lists/*

# Copy requirements first to maximize layer cache hit rate.
COPY apps/nlp/requirements.txt /build/requirements.txt
RUN ${VENV_PATH}/bin/pip install --no-cache-dir -r /build/requirements.txt

# -- Model pre-cache (runs at BUILD time, not at runtime) ----------------------
# Baking weights into the image eliminates the 3-4 min Cloud Run cold-start
# caused by downloading ~1.3 GB of weights on first container boot.
# Trade-off: image is ~3 GB - acceptable for an ML inference service.
# All four artifacts are cached into HF_HOME so the lifespan loader finds them
# instantly via from_pretrained() with no network call.

ENV HF_HOME=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence-transformers

RUN ${VENV_PATH}/bin/python -c "\
from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
import torch, os; \
model_name = 'cardiffnlp/twitter-roberta-base-sentiment-latest'; \
tok = AutoTokenizer.from_pretrained(model_name); \
model = AutoModelForSequenceClassification.from_pretrained(model_name); \
print('Sentiment model loaded, exporting to ONNX...'); \
dummy_input = tok('test', return_tensors='pt'); \
os.makedirs('/app/models/onnx', exist_ok=True); \
torch.onnx.export(\
	model,\
	(dummy_input['input_ids'], dummy_input['attention_mask']),\
	'/app/models/onnx/pharma_sentiment.onnx',\
	input_names=['input_ids', 'attention_mask'],\
	output_names=['logits'],\
	dynamic_axes={'input_ids': {0: 'batch', 1: 'seq'}, 'attention_mask': {0: 'batch', 1: 'seq'}},\
	opset_version=14\
); \
print('ONNX export complete.')"

RUN ${VENV_PATH}/bin/python -c "\
from sentence_transformers import SentenceTransformer; \
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
test_vec = model.encode('preflight check'); \
assert len(test_vec) == 384, f'Expected 384 dims, got {len(test_vec)}'; \
print(f'Embedding model ready. Dims: {len(test_vec)}')"

# Smoke-test ONNX runtime can load the exported file before the image is sealed
RUN ${VENV_PATH}/bin/python -c "\
import onnxruntime as ort; \
sess = ort.InferenceSession('/app/models/onnx/pharma_sentiment.onnx'); \
print('ONNX Runtime session initialised. Inputs:', [i.name for i in sess.get_inputs()])"

FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV VENV_PATH=/opt/venv
ENV PATH="${VENV_PATH}/bin:${PATH}"
ENV HF_HOME=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence-transformers

WORKDIR /app/apps/nlp

RUN apt-get update \
	&& apt-get install -y --no-install-recommends curl libgomp1 \
	&& rm -rf /var/lib/apt/lists/* \
	&& groupadd --gid 10001 appuser \
	&& useradd --uid 10001 --gid appuser --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder ${VENV_PATH} ${VENV_PATH}
COPY --from=builder /app/.cache /app/.cache
COPY --from=builder /app/models/onnx /app/models/onnx
COPY apps /app/apps

RUN chown -R appuser:appuser /app/.cache /app/models /app

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=40s CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--no-access-log"]
