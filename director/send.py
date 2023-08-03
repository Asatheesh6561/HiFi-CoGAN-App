from fastapi import FastAPI, HTTPException, UploadFile, File, Response
import os
import subprocess

app = FastAPI()

@app.get('/')
def home_page():
    return "Home page"

@app.post('/fileUpload/')
async def file_upload(sample: UploadFile = File(...)):
    filename = os.path.join('input_waves', sample.filename)
    with open(filename, 'wb') as f:
        content = await sample.read()
        f.write(content)
    with open('filenames.txt', 'w') as f:
        f.write(f'{sample.filename}\n')
    subprocess.run(['sh', './send.sh', sample.filename])
    return {"message": "File uploaded successfully"}

@app.get('/download/')
async def download_file():
    try:
        with open('filenames.txt') as f:
            new_filename = os.path.join('output_waves', f.readline().strip())
            return Response(new_filename, media_type='application/octet-stream', headers={'Content-Disposition': f'attachment; filename={os.path.basename(new_filename)}'})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
