from app.core.container import container


if __name__ == "__main__":
    result = container.evaluation_service.run(
        questions_file="./data/processed/evaluation_questions.json",
        file_name=None,
        top_k=None,
    )
    print(result)
