from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import List, Optional, Dict, Any
from pathlib import Path
import sys
import csv
import os
import json
from threading import Lock
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials as firebase_credentials
from firebase_admin import firestore
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

# Make src/routing importable
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src' / 'routing'))

from src.routing import api_logic


security = HTTPBearer(auto_error=False)
EXPECTED_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "project-27ffc5fd-b1d7-41-e0556")
LOCAL_PROFILE_STORE = project_root / "backend" / "profile_store.json"
_profile_store_lock = Lock()


def _get_firebase_app():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        cred_info = json.loads(service_account_json)
        cred = firebase_credentials.Certificate(cred_info)
        return firebase_admin.initialize_app(cred)

    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if service_account_path and Path(service_account_path).exists():
        cred = firebase_credentials.Certificate(service_account_path)
        return firebase_admin.initialize_app(cred)

    return firebase_admin.initialize_app(firebase_credentials.ApplicationDefault())


def _get_firestore_client():
    app = _get_firebase_app()
    return firestore.client(app=app)


def _load_local_profiles() -> Dict[str, Dict[str, Any]]:
    with _profile_store_lock:
        if not LOCAL_PROFILE_STORE.exists():
            return {}
        try:
            with open(LOCAL_PROFILE_STORE) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            return {}


def _save_local_profiles(profiles: Dict[str, Dict[str, Any]]) -> None:
    with _profile_store_lock:
        LOCAL_PROFILE_STORE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_PROFILE_STORE, "w") as f:
            json.dump(profiles, f, indent=2)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )
    try:
        request_adapter = google_requests.Request()
        decoded = google_id_token.verify_firebase_token(credentials.credentials, request_adapter)
        if not decoded:
            raise ValueError("Unable to decode Firebase ID token")

        aud = decoded.get("aud")
        iss = decoded.get("iss")
        expected_iss = f"https://securetoken.google.com/{EXPECTED_FIREBASE_PROJECT_ID}"
        if aud != EXPECTED_FIREBASE_PROJECT_ID or iss != expected_iss:
            raise ValueError(
                f"Token project mismatch. Expected {EXPECTED_FIREBASE_PROJECT_ID}, got aud={aud}, iss={iss}"
            )

        uid = decoded.get("uid") or decoded.get("user_id") or decoded.get("sub")
        if not uid:
            raise ValueError("Token missing user id")

        return {
            "uid": str(uid),
            "email": decoded.get("email"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {e}",
        )


class RouteRequest(BaseModel):
    start_postcode: str
    end_postcode: str
    soc: float
    car_model: Optional[str] = None
    umbrella_choice: Optional[str] = 'distance'
    meal_window: Optional[str] = None
    priorities: Optional[List[str]] = None
    journey_start: Optional[str] = None


class ChargerOut(BaseModel):
    id: Optional[int]
    title: Optional[str]
    max_power: Optional[float]
    is_fast: Optional[bool]
    route_km: Optional[float]
    distance: Optional[float]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    meal_window: Optional[str] = None
    nearby_places: Optional[List[str]] = None
    price: Optional[float] = None
    num_points: Optional[int] = None
    traffic_delay: Optional[float] = None
    meal_stop: Optional[bool] = None
    score: Optional[float] = None
    breakdown: Optional[Dict[str, Dict[str, Any]]] = None


class RouteResponse(BaseModel):
    total_km: float
    est_range_km: float
    start_coords: Optional[List[float]] = None
    chargers: List[ChargerOut]
    logs: Optional[str] = None


class CarModelsResponse(BaseModel):
    models: List[str]


class UserProfileIn(BaseModel):
    car_model: Optional[str] = None
    home_destination_postcode: Optional[str] = None
    default_mode: Optional[str] = None
    default_priorities: List[str] = Field(default_factory=list)


class UserProfileOut(BaseModel):
    car_model: Optional[str] = None
    home_destination_postcode: Optional[str] = None
    default_mode: Optional[str] = None
    default_priorities: List[str] = Field(default_factory=list)


app = FastAPI(title="EV Routing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post('/api/v1/route', response_model=RouteResponse)
def compute_route(req: RouteRequest, current_user: Dict[str, Optional[str]] = Depends(get_current_user)):
    print("Received POST /api/v1/route with data:", req)
    print("Authenticated user:", current_user.get("uid"))
    try:
        out = api_logic.compute_route(
            req.start_postcode,
            req.end_postcode,
            req.soc,
            req.car_model,
            umbrella_choice=(req.umbrella_choice or 'distance'),
            priorities=req.priorities,
            journey_start=req.journey_start,
        )
        print("Returning response:", {**out, "logs": "<service>"})
        return RouteResponse(**out)
    except Exception as e:
        print("Error in compute_route:", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/v1/car-models', response_model=CarModelsResponse)
def get_car_models(current_user: Dict[str, Optional[str]] = Depends(get_current_user)):
    try:
        csv_path = project_root / "data" / "raw" / "car-energy-database-30.csv"
        models: List[str] = []
        with open(csv_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                model = (row.get('Car Model ') or '').strip()
                if model:
                    models.append(model)
        models = sorted(set(models))
        return CarModelsResponse(models=models)
    except Exception as e:
        print("Error in get_car_models:", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/api/v1/profile', response_model=UserProfileOut)
def get_profile(current_user: Dict[str, Optional[str]] = Depends(get_current_user)):
    try:
        uid = str(current_user.get("uid") or "").strip()
        if not uid:
            raise HTTPException(status_code=401, detail="Missing user id in token")
        data: Dict[str, Any] = {}
        try:
            db = _get_firestore_client()
            doc = db.collection("user_profiles").document(uid).get()
            if doc.exists:
                data = doc.to_dict() or {}
        except Exception as firestore_error:
            print("Firestore unavailable for get_profile, falling back to local store:", firestore_error)
        if not data:
            profiles = _load_local_profiles()
            data = profiles.get(uid, {})

        return UserProfileOut(
            car_model=data.get("car_model"),
            home_destination_postcode=data.get("home_destination_postcode"),
            default_mode=data.get("default_mode"),
            default_priorities=data.get("default_priorities") or [],
        )
    except Exception as e:
        print("Error in get_profile:", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.put('/api/v1/profile', response_model=UserProfileOut)
def save_profile(profile: UserProfileIn, current_user: Dict[str, Optional[str]] = Depends(get_current_user)):
    try:
        uid = str(current_user.get("uid") or "").strip()
        if not uid:
            raise HTTPException(status_code=401, detail="Missing user id in token")
        valid_modes = {"distance", "meal", None}
        if profile.default_mode not in valid_modes:
            raise HTTPException(status_code=400, detail="default_mode must be 'distance' or 'meal'")

        valid_priorities = {"price", "max_power", "is_fast", "num_points", "distance", "traffic_delay"}
        priorities = [p for p in (profile.default_priorities or []) if p in valid_priorities][:2]

        payload = {
            "car_model": profile.car_model,
            "home_destination_postcode": profile.home_destination_postcode,
            "default_mode": profile.default_mode,
            "default_priorities": priorities,
            "updated_by": current_user.get("email") or uid,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        try:
            db = _get_firestore_client()
            db.collection("user_profiles").document(uid).set(payload, merge=True)
        except Exception as firestore_error:
            print("Firestore unavailable for save_profile, falling back to local store:", firestore_error)
            profiles = _load_local_profiles()
            profiles[uid] = {
                "car_model": payload.get("car_model"),
                "home_destination_postcode": payload.get("home_destination_postcode"),
                "default_mode": payload.get("default_mode"),
                "default_priorities": payload.get("default_priorities") or [],
                "updated_by": payload.get("updated_by"),
            }
            _save_local_profiles(profiles)

        return UserProfileOut(
            car_model=payload.get("car_model"),
            home_destination_postcode=payload.get("home_destination_postcode"),
            default_mode=payload.get("default_mode"),
            default_priorities=payload.get("default_priorities") or [],
        )
    except HTTPException:
        raise
    except Exception as e:
        print("Error in save_profile:", e)
        raise HTTPException(status_code=500, detail=str(e))
