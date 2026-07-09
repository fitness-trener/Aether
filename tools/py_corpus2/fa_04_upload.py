from fastapi import FastAPI, UploadFile
import shutil

app = FastAPI()

@app.post("/upload")
def upload(file: UploadFile):
    dest = "/data/uploads/" + file.filename
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return {"saved": dest}
