from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import os
import json

app = FastAPI()

@app.post('/receiver')  # Consistent route with correct spelling
async def receive_semgrep(request: Request):
    print("Request received at /receiver")  # Debug log to confirm hits
    auth_header = request.headers.get('Authorization')
    if auth_header != f"Bearer {os.environ.get('API_TOKEN')}":
        raise HTTPException(status_code=401, detail='Unauthorized')
    try:
        semgrep_data = await request.json()
        # TODO: Process semgrep_data here (store, analyze, forward, etc.)
        print('Received Semgrep results:', json.dumps(semgrep_data, indent=2))
        return JSONResponse(content={'status': 'success', 'message': 'Results received'})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
