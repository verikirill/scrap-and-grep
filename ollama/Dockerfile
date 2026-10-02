# Ollama with the embedding model inside: a start in a closed network pulls
# nothing. A new named volume gets the model from the image; a directory of
# models brought in an archive has it already (scripts/offline_bundle.sh).
FROM ollama/ollama:0.35.0

ARG EMBEDDING_MODEL=embeddinggemma:300m

# The server runs only for the pull and stops with this step. The progress bar
# would fill the build log with thousands of lines; it is shown on a failure.
RUN ollama serve >/tmp/serve.log 2>&1 & \
    for _ in $(seq 1 60); do ollama list >/dev/null 2>&1 && break; sleep 1; done; \
    ollama pull "$EMBEDDING_MODEL" >/tmp/pull.log 2>&1 \
      || { tail -n 5 /tmp/pull.log /tmp/serve.log; exit 1; }; \
    ollama list && rm -f /tmp/serve.log /tmp/pull.log
