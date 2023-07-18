from flask import Flask, request, send_file
import os
import subprocess
app = Flask(__name__)
@app.route('/')
def homePage():
    return "home page"

@app.route('/fileUpload', methods=['POST'])
def fileUpload():
    file = request.form(['sample'])
    file.save(os.path.join('input_waves', file.filename))
    f = open('filenames.txt', 'w')
    f.write(f'{file.filename}\n')
    subprocess.run(['sh', './send.sh', file.filename])
    return "File uploaded successfully"

@app.route('/download')
def download_file():
    with open('filenames.txt') as f:
        new_filename = os.path.join('output_waves', f.strip())
        return send_file(new_filename, as_attachment=True)
