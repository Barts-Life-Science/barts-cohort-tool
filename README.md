# Cohort Definition Builder

This project has two parts:
- A **backend API** using Python FastAPI framework
  - Code under /app 
- A **web frontend** using React
  - Code under /frontend


## Prerequisites
- Python 3.x installed
- `pip` and `virtualenv` or `venv` available
- Node.js and npm installed


## Development Setup
For the development setup:
- create a terminal for the frontend
- cd to the frontend directory
- run `npm start` for automatic reloading react app on http://localhost:3000
- create a second terminal for the backend
- run `uvicorn app.main:app --reload` for automatic reloading backend on http://localhost:8000
- The frontend app will proxy the backend app so all can be accessed on port 3000.

## Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install the frontend dependencies:
   ```bash
   npm ci
   ```

   This installs all dependencies defined in `package-lock.json`, including `idb-keyval`.

3. The frontend uses IndexedDB (via `idb-keyval`) to store cohort results in the browser.

   IndexedDB supports larger datasets than `sessionStorage`, allowing the demo application to display results for large patient cohorts without encountering the typical Web Storage quota limit.

   Results are stored locally in the browser and can be removed by clearing the site's browser data.

## Production Setup
For the production setup we build the frontend and serve it from the backend:
- In a terminal cd to the frontend directory
- run `npm run build` to create the static files
- cd back to the project root
- run `uvicorn app.main:app` to start the backend on http://localhost:8000
- The frontend app will be served by the backend on port 8000.
- Use a web proxy server like Nginx or Apache2 to add SSL and any required authentication. 

## API Setup Instructions

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Create the virtual environment
    ```bash
    python -m venv .venv
    ```

3. Activate the virtual environment:

    **__Linux/MacOS:__**
    ```bash
    source .venv/bin/activate
    ```
    **Windows:**
    ```bash
    .venv\Scripts\activate
    ```

4. Install dependencies:
    ```bash
    pip install -r requirements.txt
   ```

5. Run the application:
    ```bash
    uvicorn app.main:app --reload
    ```
