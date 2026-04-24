from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
import shutil, os

from app.database import SessionLocal
from app.models import File as FileModel

router = APIRouter(prefix="/files")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def get_files(db: Session = Depends(get_db)):
    return db.query(FileModel).all()


@router.post("/upload")
def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_path = f"{UPLOAD_DIR}/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    new_file = FileModel(
        name=file.filename,
        path=file_path,
        size="unknown",
        owner_id=1
    )

    db.add(new_file)
    db.commit()

    return {"message": "uploaded"}