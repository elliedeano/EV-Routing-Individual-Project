Frontend quick start

1. Install dependencies

cd frontend
npm install

2. Start mock server (from project root)

# install json-server once if needed
npm install -g json-server
json-server --watch mock/db.json --port 3001

3. Run frontend dev server

cd frontend
npm run dev

Open the Vite URL (usually http://localhost:5173)

Notes:
- The frontend reads API base from VITE_API_BASE in frontend/.env
- The app now requires Firebase Auth (email/password)
- Add these keys to frontend/.env:
	- VITE_FIREBASE_API_KEY
	- VITE_FIREBASE_AUTH_DOMAIN
	- VITE_FIREBASE_PROJECT_ID
	- VITE_FIREBASE_APP_ID
- Backend endpoints are authenticated; frontend sends Firebase ID token in Authorization header
- Set VITE_API_BASE to your backend URL (local or deployed)
