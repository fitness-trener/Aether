from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

app = FastAPI()

@app.get("/users/{user_id}")
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="not found")
    return {"id": user.id, "name": user.name}

@app.post("/users")
def create_user(payload: dict, db: Session = Depends(get_db)):
    user = User(name=payload["name"], email=payload["email"])
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id}
