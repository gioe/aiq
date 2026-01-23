# Start Question Service

Start the question generation service to generate new IQ test questions.

Argument: $ARGUMENTS (number of questions to generate, defaults to 5)

Run this command in the background:
```bash
cd /Users/mattgioe/aiq/question-service && source venv/bin/activate && python3 run_generation.py --count ${ARGUMENTS:-5} --verbose
```

Check the output to monitor question generation progress. The service will:
1. Generate questions using multiple LLMs
2. Run them through judge validation
3. Insert approved questions into the database
