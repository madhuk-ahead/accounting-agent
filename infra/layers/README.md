# Lambda layers

The chat Lambda uses two layers:

- **strands-ahead** – Strands-AHEAD SDK (no-op telemetry)
- **openai** – OpenAI Python SDK

You can either:

1. **Use existing layer ARNs**  
   Set `strands_layer_arn` and `openai_layer_arn` in your tfvars so Terraform does not create new layers.

2. **Build and use local layers**  
   Place the built zips in `infra/layers/artifacts/`:
   - `strands-ahead-layer.zip` – Build: place `strands_ahead-*.whl` in repo root `strands-ahead-package/`, then run `./infra/layers/strands_ahead/build_layer.sh` from repo root. Output: `infra/layers/artifacts/strands-ahead-layer.zip`.
   - `openai-layer.zip` – Build via `scripts/build_layers.sh` (openai section) or see README.  
   Then run `terraform apply` without setting the layer ARN variables.

If neither ARNs nor zips are provided, Terraform will fail when creating the chat Lambda.
