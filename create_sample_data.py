#!/usr/bin/env python3
"""
Create sample data for testing the AI Workflow Builder API
"""

import requests
import json
from typing import Dict, Any

# API base URL
BASE_URL = "http://localhost:8000"


def create_component(endpoint: str, data: Dict[str, Any]) -> str:
    """Create a component and return its ID"""
    response = requests.post(f"{BASE_URL}{endpoint}", json=data)
    response.raise_for_status()
    result = response.json()
    print(
        f"✅ Created {endpoint.split('/')[-1]}: {result['name']} (ID: {result['id']})")
    return result['id']


def create_workflow(data: Dict[str, Any]) -> str:
    """Create a workflow and return its ID"""
    response = requests.post(f"{BASE_URL}/api/workflows", json=data)
    response.raise_for_status()
    result = response.json()
    print(f"✅ Created workflow: {result['name']} (ID: {result['id']})")
    return result['id']


def main():
    print("🚀 Creating sample data for AI Workflow Builder...")

    try:
        # 1. Create User Query Component
        user_query_id = create_component("/api/components/user-query", {
            "name": "User Input",
            "description": "Accepts user questions and queries",
            "placeholder_text": "Ask me anything...",
            "max_length": 1000
        })

        # 2. Create Knowledge Base Component
        knowledge_base_id = create_component("/api/components/knowledge-base", {
            "name": "Knowledge Base",
            "description": "Retrieves relevant information from documents",
            "embedding_model": "text-embedding-ada-002",
            "max_documents": 100,
            "chunk_size": 1000
        })

        # 3. Create LLM Engine Component
        llm_engine_id = create_component("/api/components/llm-engine", {
            "name": "AI Assistant",
            "description": "GPT-powered response generator",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 1000,
            "system_prompt": "You are a helpful AI assistant. Provide clear, accurate, and helpful responses.",
            "use_web_search": False
        })

        # 4. Create Output Component
        output_id = create_component("/api/components/output", {
            "name": "Response Output",
            "description": "Formats and displays the final response",
            "response_format": "text",
            "include_sources": True
        })

        # 5. Create Simple Q&A Workflow (User Query -> LLM Engine -> Output)
        simple_workflow_id = create_workflow({
            "name": "Simple Q&A Workflow",
            "description": "Basic question answering without knowledge base",
            "components": [user_query_id, llm_engine_id, output_id],
            "connections": [
                {"from_component_id": user_query_id,
                    "to_component_id": llm_engine_id},
                {"from_component_id": llm_engine_id, "to_component_id": output_id}
            ]
        })

        # 6. Create another User Query Component for the full workflow
        user_query_2_id = create_component("/api/components/user-query", {
            "name": "Advanced User Input",
            "description": "Accepts complex user questions",
            "placeholder_text": "Ask me about uploaded documents...",
            "max_length": 2000
        })

        # 7. Create Full Workflow (User Query -> Knowledge Base -> LLM Engine -> Output)
        full_workflow_id = create_workflow({
            "name": "Full RAG Workflow",
            "description": "Complete workflow with knowledge base integration",
            "components": [user_query_2_id, knowledge_base_id, llm_engine_id, output_id],
            "connections": [
                {"from_component_id": user_query_2_id,
                    "to_component_id": knowledge_base_id},
                {"from_component_id": knowledge_base_id,
                    "to_component_id": llm_engine_id},
                {"from_component_id": llm_engine_id, "to_component_id": output_id}
            ]
        })

        print("\n🎉 Sample data created successfully!")
        print("\n📋 Test these workflows:")
        print(f"   Simple Q&A: {simple_workflow_id}")
        print(f"   Full RAG:   {full_workflow_id}")

        print("\n🧪 Test with these Postman requests:")
        print(f"""
POST {BASE_URL}/api/workflows/execute
{{
  "workflow_id": "{simple_workflow_id}",
  "query": "What is the capital of France?"
}}

POST {BASE_URL}/api/chat/query
{{
  "workflow_id": "{simple_workflow_id}",
  "message": "Hello, how are you?"
}}
        """)

    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating sample data: {e}")
        print("Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
