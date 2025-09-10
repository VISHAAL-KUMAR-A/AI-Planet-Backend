# AI Workflow Builder - Backend

A No-Code/Low-Code web application backend for creating intelligent workflows using FastAPI.

## Features

### User Query Component
- Create and manage user query components
- Submit queries to components
- Track query status and results
- Workflow integration support

## Setup Instructions

### Prerequisites
- Python 3.8+
- pip

### Installation

1. **Clone the repository** (if not already done)
```bash
cd AI-Planet-Backend
```

2. **Create and activate virtual environment**
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Environment Setup**
Make sure your `.env` file contains the necessary environment variables:
```
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_URL=postgresql://username:password@host:port/database_name
SECRET_KEY=your_secret_key_here_change_in_production
```

5. **Initialize Database**
Before running the application for the first time, initialize the database:
```bash
python init_db.py
```

To reset the database (if needed):
```bash
python init_db.py --reset
```

### Running the Application

1. **Initialize the database** (first time only)
```bash
python init_db.py
```

2. **Start the FastAPI server**
```bash
python main.py
```
Or using uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

3. **Access the API**
- API Base URL: `http://localhost:8000`
- Interactive API Documentation: `http://localhost:8000/docs`
- ReDoc Documentation: `http://localhost:8000/redoc`

## API Endpoints

### Health Check
- `GET /` - Root endpoint
- `GET /health` - Health check

### User Query Component Management
- `POST /api/components/user-query` - Create a new user query component
- `GET /api/components/user-query` - List all user query components
- `GET /api/components/user-query/{component_id}` - Get specific component
- `PUT /api/components/user-query/{component_id}` - Update component
- `DELETE /api/components/user-query/{component_id}` - Delete component

### Query Processing
- `POST /api/queries` - Submit a user query
- `GET /api/queries/{query_id}` - Get query status and results
- `GET /api/queries` - List all queries (with optional filters)

### Workflow Management
- `POST /api/workflows` - Create a new workflow
- `GET /api/workflows` - List all workflows
- `GET /api/workflows/{workflow_id}` - Get specific workflow

## Data Models

### UserQueryComponentCreate
```json
{
  "name": "string",
  "description": "string (optional)",
  "placeholder_text": "string (optional)",
  "max_length": "integer (optional)"
}
```

### UserQueryRequest
```json
{
  "query": "string (required)",
  "component_id": "string (required)",
  "workflow_id": "string (optional)",
  "context": "object (optional)"
}
```

## Database

The application now uses PostgreSQL database with the following features:
- **Components Table**: Stores user query components and their configurations
- **Queries Table**: Stores all user queries and their processing status
- **Workflows Table**: Stores workflow definitions and connections
- **UUID Primary Keys**: All entities use UUID for better scalability
- **JSON Configuration**: Component-specific settings stored as JSON

## Development Notes

- ✅ **Database Integration**: Now using PostgreSQL instead of in-memory storage
- ✅ **Data Persistence**: All data is now persisted to the database
- ✅ **UUID Support**: All entities use UUID for primary keys
- CORS is configured to allow all origins (configure properly for production)
- Environment variables should be properly secured in production

## Database Management

**Initialize Database:**
```bash
python init_db.py
```

**Reset Database (WARNING: Deletes all data):**
```bash
python init_db.py --reset
```
