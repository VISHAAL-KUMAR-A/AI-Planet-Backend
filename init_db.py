#!/usr/bin/env python3
"""
Database initialization script for AI Workflow Builder
This script creates the database tables and performs initial setup
"""

from database import init_db, drop_tables, create_tables
import os
import sys
from dotenv import load_dotenv

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def main():
    """Initialize the database"""
    print("🚀 Initializing AI Workflow Builder Database...")

    # Load environment variables
    load_dotenv()

    # Check if DATABASE_URL is set
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment variables")
        print("Please check your .env file")
        return 1

    print(f"📡 Connecting to database...")

    try:
        # Initialize database (create tables)
        init_db()
        print("✅ Database tables created successfully!")
        print("🎉 Database initialization completed!")
        return 0

    except Exception as e:
        print(f"❌ ERROR: Failed to initialize database: {str(e)}")
        return 1


def reset_db():
    """Reset the database (drop and recreate all tables)"""
    print("⚠️  RESETTING AI Workflow Builder Database...")
    print("This will DELETE ALL DATA!")

    # Load environment variables
    load_dotenv()

    try:
        # Drop all tables
        print("🗑️  Dropping existing tables...")
        drop_tables()

        # Create tables again
        print("🏗️  Creating fresh tables...")
        create_tables()

        print("✅ Database reset completed!")
        return 0

    except Exception as e:
        print(f"❌ ERROR: Failed to reset database: {str(e)}")
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        sys.exit(reset_db())
    else:
        sys.exit(main())
