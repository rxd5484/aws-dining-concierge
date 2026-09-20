#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGION="us-east-1"
STACK_NAME="dining-concierge"

echo "Setting up AWS deployment tools..."

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required. Install Homebrew first, then rerun this script."
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "Installing AWS CLI..."
  brew install awscli
fi

if ! command -v sam >/dev/null 2>&1; then
  echo "Installing AWS SAM CLI..."
  brew install aws-sam-cli
fi

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Installing Python 3.12 for the Lambda runtime..."
  brew install python@3.12
fi

echo "AWS CLI: $(aws --version 2>&1)"
echo "SAM CLI: $(sam --version 2>&1)"

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "No active AWS CLI session found. Opening AWS browser login..."
  aws login --region "$REGION"
fi

echo "Authenticated AWS identity:"
aws sts get-caller-identity

echo "Building backend..."
cd "$REPO_ROOT/backend"
sam build

echo "Deploying backend to AWS..."
sam deploy \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset

API_URL="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
  --output text)"

if [[ -z "$API_URL" || "$API_URL" == "None" ]]; then
  echo "Deployment completed, but ApiUrl could not be read automatically."
  exit 1
fi

echo "Connecting the local Next.js frontend to AWS..."
printf 'NEXT_PUBLIC_API_URL=%s\n' "$API_URL" > "$REPO_ROOT/frontend/.env.local"

echo
echo "AWS backend deployed successfully."
echo "API URL: $API_URL"
echo "Created frontend/.env.local with NEXT_PUBLIC_API_URL."
echo
echo "Next: restart the frontend with:"
echo "  cd $REPO_ROOT/frontend"
echo "  npm run dev"
