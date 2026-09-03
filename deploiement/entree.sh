#!/usr/bin/env bash
# Demarre vLLM, attend qu'il reponde, puis lance l'API.
#
# L'ordre compte : lancer les deux en parallele ferait echouer les premieres
# requetes pendant tout le chargement des poids, soit plusieurs minutes.
set -euo pipefail

commande_vllm=(
  vllm serve "${MODELE_BASE}"
  --host 127.0.0.1
  --port 8000
  --served-model-name "${VLLM_MODELE}"
  --max-model-len 2048
  # Voir modal_app.py : le prechauffage sur 256 requetes sature un petit GPU.
  --max-num-seqs 16
  --gpu-memory-utilization 0.90
)

if [[ -n "${ADAPTATEUR}" ]]; then
  commande_vllm+=(
    --enable-lora
    --max-lora-rank 16
    --lora-modules "${VLLM_MODELE}=${ADAPTATEUR}"
  )
fi

"${commande_vllm[@]}" &
pid_vllm=$!

# Si vLLM meurt, le conteneur doit mourir avec lui : une API qui survit a son
# moteur repondrait 500 indefiniment sans que l'orchestrateur la remplace.
trap 'kill -TERM "${pid_vllm}" 2>/dev/null || true' EXIT

echo "attente du démarrage de vLLM…"
for _ in $(seq 1 300); do
  if curl -sf "${VLLM_BASE_URL}/health" >/dev/null; then
    echo "vLLM prêt."
    break
  fi
  if ! kill -0 "${pid_vllm}" 2>/dev/null; then
    echo "vLLM s'est arrêté pendant le démarrage." >&2
    exit 1
  fi
  sleep 2
done

curl -sf "${VLLM_BASE_URL}/health" >/dev/null || {
  echo "vLLM n'a pas démarré dans le délai imparti." >&2
  exit 1
}

exec uvicorn triage.api.app:app --host 0.0.0.0 --port "${PORT}"
