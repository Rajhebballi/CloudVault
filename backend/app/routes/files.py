# from fastapi import APIRouter, UploadFile, File, Depends
# from sqlalchemy.orm import Session
# import shutil, os

# from app.database import SessionLocal
# from app.models import File as FileModel

# router = APIRouter(prefix="/files")

# UPLOAD_DIR = "uploads"
# os.makedirs(UPLOAD_DIR, exist_ok=True)

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# @router.get("/")
# def get_files(db: Session = Depends(get_db)):
#     return db.query(FileModel).all()


# @router.post("/upload")
# def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
#     file_path = f"{UPLOAD_DIR}/{file.filename}"

#     with open(file_path, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)

#     new_file = FileModel(
#         name=file.filename,
#         path=file_path,
#         size="unknown",
#         owner_id=1
#     )

#     db.add(new_file)
#     db.commit()

#     return {"message": "uploaded"}

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from jose import jwt
import os

from app.database import get_db
from app.models import File as FileModel, User

router = APIRouter(prefix="/files", tags=["Files"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

SECRET_KEY = os.getenv("SECRET_KEY", "cloudvault-super-secret-key-change-in-prod")
ALGORITHM  = "HS256"


def get_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes/1024**2:.1f} MB"
    return f"{size_bytes/1024**3:.1f} GB"


# ─── LIST FILES ──────────────────────────────────────────────────────────────
@router.get("/")
def get_files(
    filter: str = Query("all", description="all | starred | shared | trash | recent"),
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(token, db)

    # Admins see all files; users see only their own
    query = db.query(FileModel)
    if user.role != "admin":
        query = query.filter(FileModel.owner_id == user.id)

    if filter == "starred":
        query = query.filter(FileModel.starred == True, FileModel.trash == False)
    elif filter == "shared":
        query = query.filter(FileModel.shared == True, FileModel.trash == False)
    elif filter == "trash":
        query = query.filter(FileModel.trash == True)
    elif filter == "recent":
        query = query.filter(FileModel.trash == False).order_by(FileModel.id.desc()).limit(20)
    else:  # all / myfiles
        query = query.filter(FileModel.trash == False)

    files = query.all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "size": f.size,
            "file_type": f.file_type,
            "starred": f.starred,
            "shared": f.shared,
            "trash": f.trash,
            "owner_id": f.owner_id,
            "created_at": str(f.created_at)[:10] if f.created_at else "",
        }
        for f in files
    ]


# ─── UPLOAD ──────────────────────────────────────────────────────────────────
@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    user = get_user_from_token(token, db)

    # Save to uploads/<user_id>/filename
    user_dir = os.path.join(UPLOAD_DIR, str(user.id))
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, file.filename)

    with open(file_path, "wb") as buffer:
        content = file.file.read()
        buffer.write(content)
        size_bytes = len(content)

    new_file = FileModel(
        name=file.filename,
        path=file_path,
        size=human_size(size_bytes),
        file_type=file.content_type or "application/octet-stream",
        owner_id=user.id,
    )
    db.add(new_file)
    db.commit()
    db.refresh(new_file)

    return {"message": "Uploaded successfully", "file_id": new_file.id, "name": new_file.name}


# ─── STAR / UNSTAR ───────────────────────────────────────────────────────────
@router.patch("/{file_id}/star")
def toggle_star(file_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(FileModel).filter(FileModel.id == file_id, FileModel.owner_id == user.id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    f.starred = not f.starred
    db.commit()
    return {"starred": f.starred}


# ─── TRASH / RESTORE ─────────────────────────────────────────────────────────
@router.patch("/{file_id}/trash")
def trash_file(file_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(FileModel).filter(FileModel.id == file_id, FileModel.owner_id == user.id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    f.trash = True
    f.starred = False
    db.commit()
    return {"message": "Moved to trash"}


@router.patch("/{file_id}/restore")
def restore_file(file_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    f = db.query(FileModel).filter(FileModel.id == file_id, FileModel.owner_id == user.id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    f.trash = False
    db.commit()
    return {"message": "Restored"}


# ─── PERMANENT DELETE ────────────────────────────────────────────────────────
@router.delete("/{file_id}")
def delete_file(file_id: int, token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)

    query = db.query(FileModel).filter(FileModel.id == file_id)
    if user.role != "admin":
        query = query.filter(FileModel.owner_id == user.id)

    f = query.first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")

    # Remove from disk
    if os.path.exists(f.path):
        os.remove(f.path)

    db.delete(f)
    db.commit()
    return {"message": "Deleted permanently"}


# ─── ADMIN: ALL FILES ────────────────────────────────────────────────────────
@router.get("/admin/all")
def admin_all_files(token: str = Query(...), db: Session = Depends(get_db)):
    user = get_user_from_token(token, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")

    files = db.query(FileModel).all()
    return [
        {"id": f.id, "name": f.name, "size": f.size, "owner_id": f.owner_id,
         "starred": f.starred, "trash": f.trash, "created_at": str(f.created_at)[:10]}
        for f in files
    ]