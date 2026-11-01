#!/bin/bash
# Asks for your keys (hidden, kept only for this Terminal window), then runs the Mira evaluation.
# Usage: bash evaluation/run_with_keys.sh            runs four tests as a first try
#        bash evaluation/run_with_keys.sh --run-name full-run     runs all 17 supported tests
cd "$(dirname "$0")/.." || exit 1
read -s -p "OpenAI key (hidden, paste then press Enter): " OPENAI_API_KEY; echo
read -s -p "Langfuse public key (hidden, paste then press Enter): " LANGFUSE_PUBLIC_KEY; echo
read -s -p "Langfuse secret key (hidden, paste then press Enter): " LANGFUSE_SECRET_KEY; echo
export OPENAI_API_KEY LANGFUSE_PUBLIC_KEY LANGFUSE_SECRET_KEY
if [ $# -eq 0 ]; then
  python3 evaluation/run_eval.py --only T10,T5,T2,T8 --run-name first-try
else
  python3 evaluation/run_eval.py "$@"
fi
