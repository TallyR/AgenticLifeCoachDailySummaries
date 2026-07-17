# MessagingCronJob

A FastAPI service.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in the values.

## Run

```bash
source venv/bin/activate
uvicorn main:app --reload
```

Then visit http://127.0.0.1:8000 (docs at http://127.0.0.1:8000/docs).
