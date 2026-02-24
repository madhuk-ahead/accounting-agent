# Lambda layers for Strands-AHEAD and OpenAI
# Provide layer ARNs via variables to use existing layers; otherwise build artifacts and create new layers.

data "aws_lambda_layer_version" "strands_ahead_existing" {
  count      = var.strands_layer_arn != null ? 1 : 0
  layer_name = split(":", var.strands_layer_arn)[6]
  version    = tonumber(split(":", var.strands_layer_arn)[7])
}

resource "aws_lambda_layer_version" "strands_ahead" {
  count               = var.strands_layer_arn == null ? 1 : 0
  filename            = var.strands_layer_arn == null ? "${path.module}/layers/artifacts/strands-ahead-layer.zip" : null
  layer_name          = "${local.name_prefix}-strands-ahead"
  compatible_runtimes  = ["python3.11"]
  description         = "Strands-AHEAD package (no-op telemetry)"

  source_code_hash = var.strands_layer_arn == null ? filebase64sha256("${path.module}/layers/artifacts/strands-ahead-layer.zip") : null
}

data "aws_lambda_layer_version" "openai_existing" {
  count      = var.openai_layer_arn != null ? 1 : 0
  layer_name = split(":", var.openai_layer_arn)[6]
  version    = tonumber(split(":", var.openai_layer_arn)[7])
}

resource "aws_lambda_layer_version" "openai" {
  count               = var.openai_layer_arn == null ? 1 : 0
  filename            = var.openai_layer_arn == null ? "${path.module}/layers/artifacts/openai-layer.zip" : null
  layer_name          = "${local.name_prefix}-openai"
  compatible_runtimes  = ["python3.11"]
  description         = "OpenAI Python SDK"

  source_code_hash = var.openai_layer_arn == null ? filebase64sha256("${path.module}/layers/artifacts/openai-layer.zip") : null
}
