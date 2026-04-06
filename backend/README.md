Welcome to this Electric Vehicle Charger Planner, below is the following commands that need to be run to access the application. 

1: Run the LightGBM Model 
- Before you can run the application you must run the machine learning model once so that energy consumption values are computed. 
Commands to Run LightGBM Model: 
cd backend 
cd energy-consumption 
python run_pipeline.py 

The results of the model can be seen in the trip_energy.csv file.

2: Run the Backend
- Activiate conda environment and run the development server
conda activate ev-routing 
cd backend
uvicorn backend.api:app --reload --host 127.0.0.1 --port 8000
open in browser: http://127.0.0.1:8000

3: Run the Frontend
cd frontend
npm install
npm run dev
Open the Vite URL (usually http://localhost:5173)

4: Run the Tests 
Running ui_test_plan.cy.js:
cd tests
npx cypress open

Running routing_unit_tests.py
cd tests
python routing_unit_tests.py

Running test_api_integration.py 
cd tests
python test_api_integration.py 
