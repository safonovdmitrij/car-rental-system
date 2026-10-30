"""PostgreSQL storage for catalog and occupied intervals."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Car(Base):
    __tablename__ = "cars"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    characteristics: Mapped[dict] = mapped_column(JSON)
    daily_rate: Mapped[str] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_version: Mapped[int] = mapped_column(Integer,default=0)


class Occupation(Base):
    __tablename__ = "occupations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    car_id: Mapped[str] = mapped_column(ForeignKey("cars.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String)


class Account(Base):
    __tablename__="accounts"
    id: Mapped[str]=mapped_column(String,primary_key=True)
    email: Mapped[str]=mapped_column(Text)
    email_key: Mapped[str]=mapped_column(Text,unique=True)
    first_name: Mapped[str]=mapped_column(Text)
    last_name: Mapped[str]=mapped_column(Text)
    phone: Mapped[str]=mapped_column(Text)
    password_hash: Mapped[str]=mapped_column(Text)
    role: Mapped[str]=mapped_column(String,default="client")
    failed_attempts: Mapped[int]=mapped_column(Integer,default=0)
    blocked_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


class LoginSession(Base):
    __tablename__="login_sessions"
    token_hash: Mapped[str]=mapped_column(String,primary_key=True)
    account_id: Mapped[str]=mapped_column(ForeignKey("accounts.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool]=mapped_column(Boolean,default=False)


class QuoteRecord(Base):
    __tablename__='quotes'
    token_hash: Mapped[str]=mapped_column(String,primary_key=True)
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    car_id: Mapped[str]=mapped_column(ForeignKey('cars.id',ondelete='CASCADE'))
    starts_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    rate_version: Mapped[int]=mapped_column(Integer)
    daily_rate: Mapped[str]=mapped_column(Text)
    days: Mapped[int]=mapped_column(Integer)
    total: Mapped[str]=mapped_column(Text)


class Booking(Base):
    __tablename__='bookings'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    car_id: Mapped[str]=mapped_column(ForeignKey('cars.id'))
    account_id: Mapped[str]=mapped_column(ForeignKey('accounts.id'))
    starts_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    daily_rate: Mapped[str]=mapped_column(Text)
    days: Mapped[int]=mapped_column(Integer)
    total: Mapped[str]=mapped_column(Text)
    cancelled: Mapped[bool]=mapped_column(Boolean,default=False)
    cancelled_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    author_id: Mapped[str|None]=mapped_column(ForeignKey('accounts.id'),nullable=True)
    author_role: Mapped[str|None]=mapped_column(String,nullable=True)
    reason: Mapped[str|None]=mapped_column(Text,nullable=True)


class ServicePeriod(Base):
    __tablename__='service_periods'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    car_id: Mapped[str]=mapped_column(ForeignKey('cars.id'))
    starts_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    reason: Mapped[str]=mapped_column(Text)
