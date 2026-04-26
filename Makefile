.PHONY: benchmark benchmark-compare check-tusk-wrapper

API_URL ?= https://aiq-backend-production.up.railway.app
ADMIN_TOKEN ?= $(error Set ADMIN_TOKEN=<token> or export it)
TUSK_EXECUTABLE ?= tusk

# Run LLM benchmark: generates a fixed question set, then benchmarks all primary models 3x
# Usage: make benchmark ADMIN_TOKEN=<token> [RUNS=3]
benchmark:
	@QUESTION_IDS=$$(curl -s -H "X-Admin-Token: $(ADMIN_TOKEN)" \
		"$(API_URL)/v1/admin/llm-benchmark/question-set?total=30" \
		| python3 -c "import json,sys; d=json.load(sys.stdin); print(','.join(str(x) for x in d['question_ids']))") && \
	echo "Fixed question set: $$QUESTION_IDS" && \
	cd question-service && python3 scripts/benchmark_models.py \
		--runs $(or $(RUNS),3) \
		--question-ids "$$QUESTION_IDS" \
		--admin-token "$(ADMIN_TOKEN)" \
		--api-url "$(API_URL)"

# Fetch and display the human vs model comparison table
# Usage: make benchmark-compare ADMIN_TOKEN=<token>
benchmark-compare:
	@cd question-service && python3 scripts/benchmark_compare.py \
		--admin-token "$(ADMIN_TOKEN)" \
		--api-url "$(API_URL)"

# Verify the documented tusk executable supports commands used by agent skills.
# Usage: make check-tusk-wrapper [TUSK_EXECUTABLE=./.claude/bin/tusk]
check-tusk-wrapper:
	@TUSK_EXECUTABLE="$(TUSK_EXECUTABLE)" scripts/check_tusk_wrapper_commands.sh
