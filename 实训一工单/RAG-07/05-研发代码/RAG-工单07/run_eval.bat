curl -X POST "http://127.0.0.1:8002/api/v1/evaluation/run" ^
  -H "Content-Type: application/json" ^
  -d "{\"questions_file\": \"./data/processed/evaluation_questions.json\", \"file_name\": null, \"top_k\": 5}"
