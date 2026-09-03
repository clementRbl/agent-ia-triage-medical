# Image de service : vLLM et l'API dans un meme conteneur.
#
# Base officielle vLLM plutot qu'une image CUDA nue : elle embarque deja le
# pilote, PyTorch et vLLM compiles ensemble. Les reconstruire ici ferait une
# image d'une quinzaine de gigaoctets pour un resultat identique.
FROM vllm/vllm-openai:v0.11.0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    TRIAGE_JOURNAL=/journal/journal_triage.jsonl \
    VLLM_BASE_URL=http://127.0.0.1:8000 \
    VLLM_MODELE=triage-qwen3-1.7b \
    MODELE_BASE=Qwen/Qwen3-1.7B-Base \
    ADAPTATEUR="" \
    PORT=8080

WORKDIR /app

# Les dependances d'abord : elles changent rarement, le cache de couches evite
# de les reinstaller a chaque modification du code.
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv \
    && uv export --no-hashes --group api --no-emit-project > /tmp/requis.txt \
    && pip install --no-cache-dir -r /tmp/requis.txt \
    && rm /tmp/requis.txt

COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps -e .

COPY deploiement/entree.sh /usr/local/bin/entree.sh
RUN chmod +x /usr/local/bin/entree.sh \
    && mkdir -p /journal

# Le journal d'audit doit survivre au conteneur : sans volume, chaque
# redemarrage effacerait les traces medicales.
VOLUME ["/journal"]

EXPOSE 8080

# La sonde interroge l'API, pas vLLM : c'est l'API que les clients appellent,
# et elle seule sait si la chaine complete repond.
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD python -c "import httpx,os,sys; sys.exit(0 if httpx.get(f'http://127.0.0.1:{os.environ[\"PORT\"]}/sante', timeout=5).status_code==200 else 1)"

ENTRYPOINT ["/usr/local/bin/entree.sh"]
