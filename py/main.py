from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import datetime, os, json

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
]
REDIRECT_URI = "http://localhost:8000/auth/callback"
TOKEN_STORE = "token_store.json"

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

@app.get("/")
def root():
    return {"message": "Visit /auth to authenticate with Google."}

@app.get("/auth")
def auth():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(auth_url)

@app.get("/auth/callback")
def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "No code in request"}, status_code=400)

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    try:
        flow.fetch_token(code=code)
    except Exception as e:
        return JSONResponse({"error": f"Token fetch failed: {e}"}, status_code=500)

    credentials = flow.credentials
    with open(TOKEN_STORE, "w") as f:
        json.dump({
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes
        }, f)

    return RedirectResponse("http://localhost:5173/chat")

@app.get("/is-authenticated")
def is_authenticated():
    if os.path.exists(TOKEN_STORE):
        return {"status": "authenticated"}
    return JSONResponse({"error": "Not authenticated"}, status_code=401)

@app.get("/add-event")
def add_event(summary: str = "Test Event", start: str = None, end: str = None):
    if not os.path.exists(TOKEN_STORE):
        return JSONResponse({"error": "User not authenticated"}, status_code=401)
    try:
        with open(TOKEN_STORE, "r") as f:
            creds = json.load(f)
        credentials = Credentials(**creds)
        service = build("calendar", "v3", credentials=credentials)
        now = datetime.datetime.utcnow()
        start_time = start or now.replace(hour=14, minute=0, second=0, microsecond=0).isoformat() + "Z"
        end_time = end or now.replace(hour=15, minute=0, second=0, microsecond=0).isoformat() + "Z"
        event = {"summary": summary, "start": {"dateTime": start_time}, "end": {"dateTime": end_time}}
        created = service.events().insert(calendarId="primary", body=event).execute()
        return {"message": "Event created", "event_link": created.get("htmlLink")}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
