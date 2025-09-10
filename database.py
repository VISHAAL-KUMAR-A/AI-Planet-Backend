from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, JSON, Enum as SQLEnum, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import os
import enum
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Database Models


class ComponentTypeEnum(enum.Enum):
    USER_QUERY = "user_query"
    KNOWLEDGE_BASE = "knowledge_base"
    LLM_ENGINE = "llm_engine"
    OUTPUT = "output"


class QueryStatusEnum(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Component(Base):
    __tablename__ = "components"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    component_type = Column(SQLEnum(ComponentTypeEnum), nullable=False)
    # Store component-specific config
    configuration = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow)


class Query(Base):
    __tablename__ = "queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query = Column(Text, nullable=False)
    component_id = Column(UUID(as_uuid=True), nullable=False)
    workflow_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(SQLEnum(QueryStatusEnum), nullable=False,
                    default=QueryStatusEnum.PENDING)
    context = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    next_component_id = Column(UUID(as_uuid=True), nullable=True)


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    components = Column(JSON, nullable=True)  # List of component IDs
    connections = Column(JSON, nullable=True)  # List of connections
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow)

# Dependency to get DB session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create tables


def create_tables():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)

# Function to drop tables (for development/testing)


def drop_tables():
    """Drop all tables in the database"""
    Base.metadata.drop_all(bind=engine)

# Initialize database


def init_db():
    """Initialize the database with tables"""
    create_tables()
