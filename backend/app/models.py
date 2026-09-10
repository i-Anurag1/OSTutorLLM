from datetime import datetime
from sqlalchemy import String,Integer,Float,DateTime,ForeignKey,Text,Boolean,JSON
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
class User(Base):
    __tablename__='users'; id:Mapped[int]=mapped_column(primary_key=True); email:Mapped[str]=mapped_column(String(255),unique=True,index=True); password_hash:Mapped[str]=mapped_column(String(255)); name:Mapped[str]=mapped_column(String(120)); role:Mapped[str]=mapped_column(String(30),default='student'); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Topic(Base):
    __tablename__='topics'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(120),unique=True); description:Mapped[str]=mapped_column(Text); difficulty:Mapped[str]=mapped_column(String(20),default='medium'); active:Mapped[bool]=mapped_column(Boolean,default=True)
class Progress(Base):
    __tablename__='progress'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True); topic_id:Mapped[int]=mapped_column(ForeignKey('topics.id')); mastery:Mapped[float]=mapped_column(Float,default=0); attempts:Mapped[int]=mapped_column(Integer,default=0); correct:Mapped[int]=mapped_column(Integer,default=0); updated_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)
class Activity(Base):
    __tablename__='activities'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); kind:Mapped[str]=mapped_column(String(40)); topic:Mapped[str]=mapped_column(String(120)); score:Mapped[float]=mapped_column(Float,default=0); payload:Mapped[dict]=mapped_column(JSON,default=dict); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class ChatLog(Base):
    __tablename__='chat_logs'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); question:Mapped[str]=mapped_column(Text); answer:Mapped[str]=mapped_column(Text); citations:Mapped[list]=mapped_column(JSON,default=list); grounded:Mapped[bool]=mapped_column(Boolean,default=False); latency_ms:Mapped[float]=mapped_column(Float,default=0); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Source(Base):
    __tablename__='sources'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(255)); path:Mapped[str]=mapped_column(String(500),unique=True); status:Mapped[str]=mapped_column(String(30),default='pending'); version:Mapped[int]=mapped_column(Integer,default=1); chunks:Mapped[int]=mapped_column(Integer,default=0); checksum:Mapped[str]=mapped_column(String(64)); uploaded_by:Mapped[int]=mapped_column(ForeignKey('users.id')); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class AuditLog(Base):
    __tablename__='audit_logs'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=True); action:Mapped[str]=mapped_column(String(100)); detail:Mapped[str]=mapped_column(Text,default=''); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Question(Base):
    __tablename__='questions'; id:Mapped[int]=mapped_column(primary_key=True); topic:Mapped[str]=mapped_column(String(120),index=True); difficulty:Mapped[str]=mapped_column(String(20)); kind:Mapped[str]=mapped_column(String(20)); prompt:Mapped[str]=mapped_column(Text); options:Mapped[list|None]=mapped_column(JSON,nullable=True); answer:Mapped[str]=mapped_column(Text); explanation:Mapped[str]=mapped_column(Text,default=''); created_by:Mapped[int]=mapped_column(ForeignKey('users.id')); active:Mapped[bool]=mapped_column(Boolean,default=True)
