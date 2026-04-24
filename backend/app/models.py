from sqlalchemy import Column, Integer, String, Boolean
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    password = Column(String(255))
    role = Column(String(50))


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    path = Column(String(255))
    size = Column(String(50))
    owner_id = Column(Integer)
    starred = Column(Boolean, default=False)
    shared = Column(Boolean, default=False)