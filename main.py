from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import uuid
import os
from dotenv import load_dotenv

# Import database components
from database import get_db, init_db, Component, Query, Workflow, ComponentTypeEnum, QueryStatusEnum

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="AI Workflow Builder API",
    description="No-Code/Low-Code web application for creating intelligent workflows",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup


@app.on_event("startup")
async def startup_event():
    init_db()

# Enums (using the same values as database enums for compatibility)


class ComponentType(str, Enum):
    USER_QUERY = "user_query"
    KNOWLEDGE_BASE = "knowledge_base"
    LLM_ENGINE = "llm_engine"
    OUTPUT = "output"


class QueryStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Pydantic Models


class UserQueryComponentCreate(BaseModel):
    name: str = Field(..., description="Name of the user query component")
    description: Optional[str] = Field(
        None, description="Description of the component")
    placeholder_text: Optional[str] = Field(
        "Enter your question here...", description="Placeholder text for the query input")
    max_length: Optional[int] = Field(
        1000, description="Maximum length of user query")


class UserQueryComponentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    placeholder_text: str
    max_length: int
    component_type: ComponentType
    created_at: datetime
    updated_at: datetime


class UserQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000,
                       description="User's question or query")
    component_id: str = Field(...,
                              description="ID of the user query component")
    workflow_id: Optional[str] = Field(
        None, description="ID of the workflow this query belongs to")
    context: Optional[Dict[str, Any]] = Field(
        None, description="Additional context for the query")


class UserQueryResponse(BaseModel):
    id: str
    query: str
    component_id: str
    workflow_id: Optional[str]
    status: QueryStatus
    created_at: datetime
    processed_at: Optional[datetime]
    next_component_id: Optional[str]
    result: Optional[Dict[str, Any]]


class ComponentConnection(BaseModel):
    from_component_id: str
    to_component_id: str
    connection_type: str = "default"


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    components: List[str] = []
    connections: List[ComponentConnection] = []


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    components: List[str]
    connections: List[ComponentConnection]
    created_at: datetime
    updated_at: datetime

# Helper functions


def generate_id() -> str:
    return str(uuid.uuid4())


def get_current_timestamp() -> datetime:
    return datetime.utcnow()

# Database helper functions


def db_component_to_response(component: Component) -> UserQueryComponentResponse:
    """Convert database Component to UserQueryComponentResponse"""
    config = component.configuration or {}
    return UserQueryComponentResponse(
        id=str(component.id),
        name=component.name,
        description=component.description,
        placeholder_text=config.get(
            "placeholder_text", "Enter your question here..."),
        max_length=config.get("max_length", 1000),
        component_type=ComponentType(component.component_type.value),
        created_at=component.created_at,
        updated_at=component.updated_at
    )


def db_query_to_response(query: Query) -> UserQueryResponse:
    """Convert database Query to UserQueryResponse"""
    return UserQueryResponse(
        id=str(query.id),
        query=query.query,
        component_id=str(query.component_id),
        workflow_id=str(query.workflow_id) if query.workflow_id else None,
        status=QueryStatus(query.status.value),
        created_at=query.created_at,
        processed_at=query.processed_at,
        next_component_id=str(
            query.next_component_id) if query.next_component_id else None,
        result=query.result
    )


def db_workflow_to_response(workflow: Workflow) -> WorkflowResponse:
    """Convert database Workflow to WorkflowResponse"""
    connections = []
    if workflow.connections:
        connections = [ComponentConnection(**conn)
                       for conn in workflow.connections]

    return WorkflowResponse(
        id=str(workflow.id),
        name=workflow.name,
        description=workflow.description,
        components=workflow.components or [],
        connections=connections,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at
    )

# API Endpoints


@app.get("/")
async def root():
    return {"message": "AI Workflow Builder API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": get_current_timestamp()}

# User Query Component Endpoints


@app.post("/api/components/user-query", response_model=UserQueryComponentResponse)
async def create_user_query_component(component: UserQueryComponentCreate, db: Session = Depends(get_db)):
    """
    Create a new User Query Component
    """
    # Create configuration dictionary
    config = {
        "placeholder_text": component.placeholder_text,
        "max_length": component.max_length
    }

    # Create database component
    db_component = Component(
        name=component.name,
        description=component.description,
        component_type=ComponentTypeEnum.USER_QUERY,
        configuration=config
    )

    db.add(db_component)
    db.commit()
    db.refresh(db_component)

    return db_component_to_response(db_component)


@app.get("/api/components/user-query/{component_id}", response_model=UserQueryComponentResponse)
async def get_user_query_component(component_id: str, db: Session = Depends(get_db)):
    """
    Get a specific User Query Component by ID
    """
    try:
        component_uuid = uuid.UUID(component_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid component ID format")

    db_component = db.query(Component).filter(
        and_(
            Component.id == component_uuid,
            Component.component_type == ComponentTypeEnum.USER_QUERY
        )
    ).first()

    if not db_component:
        raise HTTPException(status_code=404, detail="Component not found")

    return db_component_to_response(db_component)


@app.get("/api/components/user-query", response_model=List[UserQueryComponentResponse])
async def list_user_query_components(db: Session = Depends(get_db)):
    """
    List all User Query Components
    """
    db_components = db.query(Component).filter(
        Component.component_type == ComponentTypeEnum.USER_QUERY
    ).all()

    return [db_component_to_response(comp) for comp in db_components]


@app.put("/api/components/user-query/{component_id}", response_model=UserQueryComponentResponse)
async def update_user_query_component(component_id: str, component: UserQueryComponentCreate, db: Session = Depends(get_db)):
    """
    Update an existing User Query Component
    """
    try:
        component_uuid = uuid.UUID(component_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid component ID format")

    db_component = db.query(Component).filter(
        and_(
            Component.id == component_uuid,
            Component.component_type == ComponentTypeEnum.USER_QUERY
        )
    ).first()

    if not db_component:
        raise HTTPException(status_code=404, detail="Component not found")

    # Update component
    db_component.name = component.name
    db_component.description = component.description
    db_component.configuration = {
        "placeholder_text": component.placeholder_text,
        "max_length": component.max_length
    }
    db_component.updated_at = get_current_timestamp()

    db.commit()
    db.refresh(db_component)

    return db_component_to_response(db_component)


@app.delete("/api/components/user-query/{component_id}")
async def delete_user_query_component(component_id: str, db: Session = Depends(get_db)):
    """
    Delete a User Query Component
    """
    try:
        component_uuid = uuid.UUID(component_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid component ID format")

    db_component = db.query(Component).filter(
        and_(
            Component.id == component_uuid,
            Component.component_type == ComponentTypeEnum.USER_QUERY
        )
    ).first()

    if not db_component:
        raise HTTPException(status_code=404, detail="Component not found")

    db.delete(db_component)
    db.commit()

    return {"message": "Component deleted successfully"}

# User Query Processing Endpoints


@app.post("/api/queries", response_model=UserQueryResponse)
async def submit_user_query(query_request: UserQueryRequest, db: Session = Depends(get_db)):
    """
    Submit a user query to a User Query Component
    """
    try:
        component_uuid = uuid.UUID(query_request.component_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid component ID format")

    # Validate component exists
    db_component = db.query(Component).filter(
        and_(
            Component.id == component_uuid,
            Component.component_type == ComponentTypeEnum.USER_QUERY
        )
    ).first()

    if not db_component:
        raise HTTPException(status_code=404, detail="Component not found")

    # Validate query length
    config = db_component.configuration or {}
    max_length = config.get("max_length", 1000)
    if len(query_request.query) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"Query exceeds maximum length of {max_length} characters"
        )

    # Create query record
    workflow_uuid = None
    if query_request.workflow_id:
        try:
            workflow_uuid = uuid.UUID(query_request.workflow_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid workflow ID format")

    db_query = Query(
        query=query_request.query,
        component_id=component_uuid,
        workflow_id=workflow_uuid,
        status=QueryStatusEnum.PENDING,
        context=query_request.context,
        result={
            "message": "Query received successfully",
            "query_processed": True,
            "ready_for_next_component": True
        }
    )

    db.add(db_query)
    db.commit()

    # For now, immediately mark as completed since this is the entry point
    db_query.status = QueryStatusEnum.COMPLETED
    db_query.processed_at = get_current_timestamp()

    db.commit()
    db.refresh(db_query)

    return db_query_to_response(db_query)


@app.get("/api/queries/{query_id}", response_model=UserQueryResponse)
async def get_query_status(query_id: str, db: Session = Depends(get_db)):
    """
    Get the status and result of a specific query
    """
    try:
        query_uuid = uuid.UUID(query_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid query ID format")

    db_query = db.query(Query).filter(Query.id == query_uuid).first()

    if not db_query:
        raise HTTPException(status_code=404, detail="Query not found")

    return db_query_to_response(db_query)


@app.get("/api/queries", response_model=List[UserQueryResponse])
async def list_queries(component_id: Optional[str] = None, workflow_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    List all queries, optionally filtered by component_id or workflow_id
    """
    query = db.query(Query)

    if component_id:
        try:
            component_uuid = uuid.UUID(component_id)
            query = query.filter(Query.component_id == component_uuid)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid component ID format")

    if workflow_id:
        try:
            workflow_uuid = uuid.UUID(workflow_id)
            query = query.filter(Query.workflow_id == workflow_uuid)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid workflow ID format")

    db_queries = query.all()
    return [db_query_to_response(q) for q in db_queries]

# Workflow Management Endpoints


@app.post("/api/workflows", response_model=WorkflowResponse)
async def create_workflow(workflow: WorkflowCreate, db: Session = Depends(get_db)):
    """
    Create a new workflow
    """
    db_workflow = Workflow(
        name=workflow.name,
        description=workflow.description,
        components=workflow.components,
        connections=[conn.dict() for conn in workflow.connections]
    )

    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)

    return db_workflow_to_response(db_workflow)


@app.get("/api/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """
    Get a specific workflow by ID
    """
    try:
        workflow_uuid = uuid.UUID(workflow_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid workflow ID format")

    db_workflow = db.query(Workflow).filter(
        Workflow.id == workflow_uuid).first()

    if not db_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return db_workflow_to_response(db_workflow)


@app.get("/api/workflows", response_model=List[WorkflowResponse])
async def list_workflows(db: Session = Depends(get_db)):
    """
    List all workflows
    """
    db_workflows = db.query(Workflow).filter(Workflow.is_active == True).all()
    return [db_workflow_to_response(workflow) for workflow in db_workflows]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
