# Agent Factory Book

## Structure

- `frontend/` contains the course site and chat UI
- `backend/` contains the FastAPI + RAG backend
- `knowledge_base/` contains markdown source content
- `vector_db/` stores the ChromaDB index

## Run locally

### Backend

```bash
cd backend
uvicorn main:app --reload
```

### Frontend

Serve the `frontend/` folder with any local static server.

## APIs

- `POST /auth/signup`
- `POST /auth/login`
- `GET /me`
- `POST /connections`
- `GET /connections`
- `DELETE /connections/{id}`
- `POST /connections/{id}/test`
- `POST /tools`
- `GET /tools`
- `DELETE /tools/{id}`
- `POST /tools/{id}/test`
- `GET /health`
- `POST /ingest`
- `POST /chat`

## Security

- Use `JWT_SECRET` for auth tokens
- Use `ENCRYPTION_KEY` to encrypt stored API secrets
- Never put API keys in frontend code
- Store the JWT locally only for development/testing

## Chat rules

- Answers must come only from the book content
- If the book does not contain the answer, the tutor must respond with:
  `The current book content does not contain enough information about this.`
# Agent-factory-book
