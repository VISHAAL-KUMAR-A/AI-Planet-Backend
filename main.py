from fastapi import FastAPI, HTTPException, Depends, Query
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
import json
import openai
import requests
from contextlib import asynccontextmanager

# Import database components
from database import get_db, init_db, Component, Query, Workflow, ComponentTypeEnum, QueryStatusEnum

# Load environment variables
load_dotenv()

# Lifespan event handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown (if needed)

# Initialize FastAPI app
app = FastAPI(
    title="AI Workflow Builder API",
    description="No-Code/Low-Code web application for creating intelligent workflows",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# Knowledge Base Component Models
class KnowledgeBaseComponentCreate(BaseModel):
    name: str = Field(..., description="Name of the knowledge base component")
    description: Optional[str] = Field(
        None, description="Description of the component")
    embedding_model: str = Field(
        "text-embedding-ada-002", description="OpenAI embedding model to use")
    max_documents: Optional[int] = Field(
        100, description="Maximum number of documents to store")
    chunk_size: Optional[int] = Field(
        1000, description="Size of text chunks for processing")


# LLM Engine Component Models
class LLMEngineComponentCreate(BaseModel):
    name: str = Field(..., description="Name of the LLM engine component")
    description: Optional[str] = Field(
        None, description="Description of the component")
    model: str = Field("gpt-3.5-turbo", description="LLM model to use")
    temperature: float = Field(
        0.7, description="Temperature for LLM responses")
    max_tokens: Optional[int] = Field(
        1000, description="Maximum tokens in response")
    system_prompt: Optional[str] = Field(
        "You are a helpful assistant.", description="System prompt for the LLM")
    use_web_search: bool = Field(
        False, description="Enable web search via SerpAPI")


# Output Component Models
class OutputComponentCreate(BaseModel):
    name: str = Field(..., description="Name of the output component")
    description: Optional[str] = Field(
        None, description="Description of the component")
    response_format: str = Field(
        "text", description="Format of the output (text, json, markdown)")
    include_sources: bool = Field(
        True, description="Include source information in output")


# Workflow Execution Models
class WorkflowExecutionRequest(BaseModel):
    workflow_id: str = Field(..., description="ID of the workflow to execute")
    query: str = Field(..., min_length=1, max_length=2000,
                       description="User query to process")
    context: Optional[Dict[str, Any]] = Field(
        None, description="Additional context")


class WorkflowExecutionResponse(BaseModel):
    execution_id: str
    workflow_id: str
    query: str
    status: QueryStatus
    result: Optional[Dict[str, Any]]
    execution_steps: List[Dict[str, Any]]
    created_at: datetime
    completed_at: Optional[datetime]


# Chat Models
class ChatMessage(BaseModel):
    role: str = Field(...,
                      description="Role of the message sender (user, assistant)")
    content: str = Field(..., description="Content of the message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatSessionRequest(BaseModel):
    workflow_id: str = Field(...,
                             description="ID of the workflow to use for chat")
    session_id: Optional[str] = Field(
        None, description="Existing session ID to continue")


class ChatMessageRequest(BaseModel):
    session_id: str = Field(..., description="Chat session ID")
    message: str = Field(..., min_length=1, max_length=2000,
                         description="User message")


class ChatResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    workflow_id: str
    created_at: datetime


class ChatQueryRequest(BaseModel):
    workflow_id: str = Field(...,
                             description="Workflow ID to use for processing")
    message: str = Field(..., description="User message")

# Helper functions


def generate_id() -> str:
    return str(uuid.uuid4())


def get_current_timestamp() -> datetime:
    return datetime.utcnow()


# Workflow execution helper functions
def get_workflow_components_in_order(workflow: Workflow, db: Session) -> List[Component]:
    """Get workflow components in execution order based on connections"""
    if not workflow.components or not workflow.connections:
        return []

    # Simple implementation: find the user_query component first, then follow connections
    component_ids = [uuid.UUID(comp_id) for comp_id in workflow.components]
    components = db.query(Component).filter(
        Component.id.in_(component_ids)).all()

    # Find user query component as starting point
    user_query_comp = next(
        (c for c in components if c.component_type == ComponentTypeEnum.USER_QUERY), None)
    if not user_query_comp:
        return []

    ordered_components = [user_query_comp]

    # Follow connections to build execution order
    connections = workflow.connections or []
    current_id = str(user_query_comp.id)

    while True:
        next_connection = next((conn for conn in connections if conn.get(
            'from_component_id') == current_id), None)
        if not next_connection:
            break

        next_id = next_connection.get('to_component_id')
        next_comp = next((c for c in components if str(c.id) == next_id), None)
        if next_comp and next_comp not in ordered_components:
            ordered_components.append(next_comp)
            current_id = next_id
        else:
            break

    return ordered_components


def execute_llm_component(component: Component, query: str, context: Optional[str] = None) -> Dict[str, Any]:
    """Execute LLM component logic"""
    config = component.configuration or {}

    try:
        # Get OpenAI API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"error": "OpenAI API key not configured", "success": False}

        # Build messages
        messages = []
        system_prompt = config.get(
            "system_prompt", "You are a helpful assistant.")
        messages.append({"role": "system", "content": system_prompt})

        if context:
            messages.append(
                {"role": "system", "content": f"Context: {context}"})

        messages.append({"role": "user", "content": query})

        # Call OpenAI API
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=config.get("model", "gpt-3.5-turbo"),
            messages=messages,
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 1000)
        )

        return {
            "success": True,
            "response": response.choices[0].message.content,
            "model": config.get("model", "gpt-3.5-turbo"),
            "tokens_used": response.usage.total_tokens if response.usage else 0
        }

    except Exception as e:
        return {"error": str(e), "success": False}


def execute_knowledge_base_component(component: Component, query: str) -> Dict[str, Any]:
    """Execute Knowledge Base component logic (placeholder for now)"""
    config = component.configuration or {}

    # For now, return a mock response since we haven't implemented embeddings yet
    return {
        "success": True,
        "context": f"Retrieved context for query: {query[:50]}...",
        "documents_found": 0,
        "note": "Knowledge base functionality will be implemented when document upload is available"
    }


def execute_output_component(component: Component, data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Output component logic"""
    config = component.configuration or {}

    # Format the output based on configuration
    response_format = config.get("response_format", "text")
    include_sources = config.get("include_sources", True)

    result = {
        "success": True,
        "format": response_format,
        "content": data.get("response", "No response generated"),
    }

    if include_sources and "context" in data:
        result["sources"] = data.get("context", "No sources available")

    return result

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


# Component Creation Endpoints for all types
@app.post("/api/components/knowledge-base")
async def create_knowledge_base_component(component: KnowledgeBaseComponentCreate, db: Session = Depends(get_db)):
    """Create a new Knowledge Base Component"""
    config = {
        "embedding_model": component.embedding_model,
        "max_documents": component.max_documents,
        "chunk_size": component.chunk_size
    }

    db_component = Component(
        name=component.name,
        description=component.description,
        component_type=ComponentTypeEnum.KNOWLEDGE_BASE,
        configuration=config
    )

    db.add(db_component)
    db.commit()
    db.refresh(db_component)

    return {"id": str(db_component.id), "name": db_component.name, "type": "knowledge_base", "created_at": db_component.created_at}


@app.post("/api/components/llm-engine")
async def create_llm_engine_component(component: LLMEngineComponentCreate, db: Session = Depends(get_db)):
    """Create a new LLM Engine Component"""
    config = {
        "model": component.model,
        "temperature": component.temperature,
        "max_tokens": component.max_tokens,
        "system_prompt": component.system_prompt,
        "use_web_search": component.use_web_search
    }

    db_component = Component(
        name=component.name,
        description=component.description,
        component_type=ComponentTypeEnum.LLM_ENGINE,
        configuration=config
    )

    db.add(db_component)
    db.commit()
    db.refresh(db_component)

    return {"id": str(db_component.id), "name": db_component.name, "type": "llm_engine", "created_at": db_component.created_at}


@app.post("/api/components/output")
async def create_output_component(component: OutputComponentCreate, db: Session = Depends(get_db)):
    """Create a new Output Component"""
    config = {
        "response_format": component.response_format,
        "include_sources": component.include_sources
    }

    db_component = Component(
        name=component.name,
        description=component.description,
        component_type=ComponentTypeEnum.OUTPUT,
        configuration=config
    )

    db.add(db_component)
    db.commit()
    db.refresh(db_component)

    return {"id": str(db_component.id), "name": db_component.name, "type": "output", "created_at": db_component.created_at}


@app.get("/api/components")
async def list_all_components(db: Session = Depends(get_db)):
    """List all components grouped by type"""
    components = db.query(Component).all()

    result = {
        "user_query": [],
        "knowledge_base": [],
        "llm_engine": [],
        "output": []
    }

    for comp in components:
        comp_data = {
            "id": str(comp.id),
            "name": comp.name,
            "description": comp.description,
            "configuration": comp.configuration,
            "created_at": comp.created_at
        }

        if comp.component_type == ComponentTypeEnum.USER_QUERY:
            result["user_query"].append(comp_data)
        elif comp.component_type == ComponentTypeEnum.KNOWLEDGE_BASE:
            result["knowledge_base"].append(comp_data)
        elif comp.component_type == ComponentTypeEnum.LLM_ENGINE:
            result["llm_engine"].append(comp_data)
        elif comp.component_type == ComponentTypeEnum.OUTPUT:
            result["output"].append(comp_data)

    return result


# Workflow Execution API - THE CORE MISSING PIECE
@app.post("/api/workflows/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(request: WorkflowExecutionRequest, db: Session = Depends(get_db)):
    """
    Execute a workflow with a user query - THIS IS THE KEY API YOUR FRONTEND NEEDS
    """
    try:
        workflow_uuid = uuid.UUID(request.workflow_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid workflow ID format")

    # Get workflow
    workflow = db.query(Workflow).filter(Workflow.id == workflow_uuid).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Get components in execution order
    components = get_workflow_components_in_order(workflow, db)
    if not components:
        raise HTTPException(
            status_code=400, detail="Invalid workflow: no valid component chain found")

    # Create execution record
    execution_id = generate_id()
    execution_steps = []
    current_data = {"query": request.query, "context": request.context}

    try:
        # Execute each component in order
        for i, component in enumerate(components):
            step_start = get_current_timestamp()

            if component.component_type == ComponentTypeEnum.USER_QUERY:
                # User query component just passes the query through
                step_result = {
                    "success": True,
                    "query_received": current_data["query"],
                    "message": "Query received and validated"
                }

            elif component.component_type == ComponentTypeEnum.KNOWLEDGE_BASE:
                # Execute knowledge base component
                step_result = execute_knowledge_base_component(
                    component, current_data["query"])
                if step_result.get("success"):
                    current_data["context"] = step_result.get("context", "")

            elif component.component_type == ComponentTypeEnum.LLM_ENGINE:
                # Execute LLM component
                context = current_data.get("context")
                step_result = execute_llm_component(
                    component, current_data["query"], context)
                if step_result.get("success"):
                    current_data["response"] = step_result.get("response", "")

            elif component.component_type == ComponentTypeEnum.OUTPUT:
                # Execute output component
                step_result = execute_output_component(component, current_data)

            else:
                step_result = {
                    "error": f"Unknown component type: {component.component_type}", "success": False}

            # Record execution step
            execution_steps.append({
                "component_id": str(component.id),
                "component_name": component.name,
                "component_type": component.component_type.value,
                "step_number": i + 1,
                "started_at": step_start.isoformat(),
                "completed_at": get_current_timestamp().isoformat(),
                "result": step_result,
                "success": step_result.get("success", False)
            })

            # Stop execution if step failed
            if not step_result.get("success", False):
                break

        # Determine final status
        final_status = QueryStatus.COMPLETED if all(
            step.get("success", False) for step in execution_steps) else QueryStatus.FAILED

        # Create response
        response = WorkflowExecutionResponse(
            execution_id=execution_id,
            workflow_id=request.workflow_id,
            query=request.query,
            status=final_status,
            result=current_data,
            execution_steps=execution_steps,
            created_at=get_current_timestamp(),
            completed_at=get_current_timestamp() if final_status == QueryStatus.COMPLETED else None
        )

        return response

    except Exception as e:
        # Handle execution errors
        raise HTTPException(
            status_code=500, detail=f"Workflow execution failed: {str(e)}")


# Workflow Validation API
@app.post("/api/workflows/{workflow_id}/validate")
async def validate_workflow(workflow_id: str, db: Session = Depends(get_db)):
    """
    Validate if a workflow is properly configured for execution
    """
    try:
        workflow_uuid = uuid.UUID(workflow_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid workflow ID format")

    workflow = db.query(Workflow).filter(Workflow.id == workflow_uuid).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    issues = []

    # Check if workflow has components
    if not workflow.components:
        issues.append("Workflow has no components")

    # Check if workflow has connections
    if not workflow.connections:
        issues.append("Workflow has no connections")

    # Get components and validate chain
    components = get_workflow_components_in_order(workflow, db)

    # Check for required component types
    component_types = [comp.component_type for comp in components]

    if ComponentTypeEnum.USER_QUERY not in component_types:
        issues.append("Workflow must have a User Query component")

    if ComponentTypeEnum.OUTPUT not in component_types:
        issues.append("Workflow must have an Output component")

    # Check for valid execution chain
    if len(components) < 2:
        issues.append("Workflow must have at least 2 connected components")

    is_valid = len(issues) == 0

    return {
        "valid": is_valid,
        "issues": issues,
        "component_count": len(components),
        "execution_order": [{"id": str(comp.id), "name": comp.name, "type": comp.component_type.value} for comp in components]
    }


# Chat Interface APIs
@app.post("/api/chat/start", response_model=ChatResponse)
async def start_chat_session(request: ChatSessionRequest, db: Session = Depends(get_db)):
    """
    Start a new chat session with a workflow
    """
    try:
        workflow_uuid = uuid.UUID(request.workflow_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid workflow ID format")

    # Validate workflow exists
    workflow = db.query(Workflow).filter(Workflow.id == workflow_uuid).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Create new session ID if not provided
    session_id = request.session_id or generate_id()

    # Initialize chat with welcome message
    welcome_message = ChatMessage(
        role="assistant",
        content=f"Hello! I'm ready to help you using the '{workflow.name}' workflow. What would you like to know?",
        timestamp=get_current_timestamp()
    )

    return ChatResponse(
        session_id=session_id,
        messages=[welcome_message],
        workflow_id=request.workflow_id,
        created_at=get_current_timestamp()
    )


@app.post("/api/chat/{session_id}/message", response_model=ChatResponse)
async def send_chat_message(session_id: str, request: ChatMessageRequest, db: Session = Depends(get_db)):
    """
    Send a message in a chat session and get AI response via workflow execution
    """
    if request.session_id != session_id:
        raise HTTPException(status_code=400, detail="Session ID mismatch")

    # For now, we'll use a simple approach where we store chat context in memory
    # In production, you'd want to store chat history in the database

    try:
        # Get the workflow ID from a previous chat session (you might want to store this)
        # For this example, we'll assume it's passed or stored somewhere
        # In a real implementation, you'd query the database for the chat session

        # Since we don't have chat session storage yet, we'll require the workflow_id to be passed
        # This is a simplified implementation

        return {"error": "Chat session storage not implemented yet. Use /api/workflows/execute directly for now."}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Chat processing failed: {str(e)}")


# Enhanced Chat API that works with current system
@app.post("/api/chat/query")
async def chat_with_workflow(
    request: ChatQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to a workflow and get a conversational response
    This API combines workflow execution with chat-like interaction
    """
    try:
        # Execute the workflow with the message
        execution_request = WorkflowExecutionRequest(
            workflow_id=request.workflow_id,
            query=request.message
        )

        execution_result = await execute_workflow(execution_request, db)

        # Format response in chat-like manner
        if execution_result.status == QueryStatus.COMPLETED:
            # Extract the final response from the workflow execution
            final_response = execution_result.result.get(
                "response", "I couldn't generate a response.")

            return {
                "session_id": execution_result.execution_id,
                "user_message": request.message,
                "ai_response": final_response,
                "status": "success",
                "workflow_used": request.workflow_id,
                "execution_steps": len(execution_result.execution_steps),
                "timestamp": execution_result.created_at
            }
        else:
            # Handle failed execution
            error_details = []
            for step in execution_result.execution_steps:
                if not step.get("success", True):
                    error_details.append(
                        f"Step {step.get('step_number')}: {step.get('result', {}).get('error', 'Unknown error')}")

            return {
                "session_id": execution_result.execution_id,
                "user_message": request.message,
                "ai_response": "I encountered an error while processing your request.",
                "status": "error",
                "error_details": error_details,
                "timestamp": execution_result.created_at
            }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Chat processing failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
