$env:PYTHONUNBUFFERED="1"
Set-Location "C:\Users\刘禹含\Desktop\RAG"
& "D:\Anaconda\envs\RAG\python.exe" -u "local_embedding_service.py" *> "embedding_out.txt"
