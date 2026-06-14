"""Known skill keywords used for resume parsing and job matching.

This list is intentionally broad (general SWE/AI/ML/data) and can be
extended by users via their profile's core_skills/avoid_skills fields.
"""

SKILL_KEYWORDS = [
    # AI / ML / GenAI
    "machine learning", "deep learning", "nlp", "natural language processing",
    "generative ai", "genai", "llm", "large language models", "rag",
    "retrieval augmented generation", "agentic ai", "langchain", "langgraph",
    "llamaindex", "transformers", "huggingface", "fine-tuning", "prompt engineering",
    "computer vision", "reinforcement learning", "mlops", "llmops",
    "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost",
    "bedrock", "openai", "anthropic", "", "gpt", "vector database",
    "pinecone", "faiss", "chroma", "weaviate", "embeddings",

    # Cloud / Infra
    "aws", "azure", "gcp", "google cloud", "databricks", "snowflake",
    "kubernetes", "docker", "terraform", "ci/cd", "jenkins", "airflow",
    "lambda", "ec2", "s3", "sagemaker", "spark", "kafka",

    # Backend / API
    "python", "fastapi", "flask", "django", "java", "scala", "go", "c++",
    "rest api", "graphql", "microservices", "node.js", "typescript",

    # Data
    "sql", "postgresql", "mysql", "mongodb", "nosql", "etl", "data engineering",
    "data pipeline", "pandas", "numpy", "data warehouse", "elasticsearch",

    # Frontend
    "react", "angular", "vue", "javascript", "html", "css",

    # General
    "agile", "scrum", "git", "linux", "rest", "microservice", "design patterns",
]
