# GenAI-Driven IT Incident Management System

## Project Overview

This project develops a self-service IT incident management platform powered by Generative AI (GenAI). It aims to streamline the incident reporting process by using a Large Language Model (LLM) to intelligently interact with users, gather detailed information, and leverage a knowledge base (KB) for efficient problem resolution. The system also includes an admin interface for incident tracking and knowledge base management.

## Problem Statement

Traditional IT service management often struggles with manual incident creation, incomplete user reports, and excessive back-and-forth between users and IT agents. This leads to slow resolution times and increased operational costs.

## Solution

Our system addresses these challenges by integrating:

*   **LLM-based Query Handling:** An AI chatbot guides users through incident creation, asking clarifying questions based on known issues.
*   **Structured Database:** Stores all incident details, conversation history, and status.
*   **Vectorized Knowledge Base (ChromaDB):** Contains historical cases and solution approaches, informing the LLM's interactions.
*   **Intuitive User Interface (React):** A simple web form for users to report incidents.
*   **Admin Dashboard (React):** Allows IT administrators to view, manage, and update incidents, and to enrich the knowledge base.

## Features

### User Interface
*   Natural language incident reporting.
*   AI-guided clarification process.
*   Real-time chat interaction with incident creation and status updates.
*   Display of active incident ID in the chat.

### Admin Dashboard
*   View all incidents with filters (status, ID).
*   Detailed view of individual incidents, including conversation history and initial KB context.
*   Ability to update incident status (Open, Pending Info, Pending Admin Review, Resolved).
*   Integrated Knowledge Base Editor to update `knowledge_base.txt`, triggering automatic re-vectorization.

### Backend & LLM Logic
*   FastAPI backend for robust API endpoints.
*   MongoDB for persistent storage of incident records.
*   ChromaDB as a vector store for the knowledge base, enabling semantic search.
*   Google Gemini Pro (via `langchain-google-genai`) for LLM capabilities.
*   Intelligent LLM prompt engineering to:
    *   Handle greetings and irrelevant queries.
    *   Perform one-time knowledge base retrieval per incident.
    *   Ask clarifying questions based on KB `Required Info`.
    *   Provide `Solution Steps` directly from KB entries.
    *   Detect and mark incident status changes (Pending Info, Pending Admin Review, Open, Resolved).
    *   Store conversation history with incidents.

 ### Workflow

1.  **User Query Intake:** User submits a natural language query via the User UI.
2.  **Incident Preprocessing:**
    *   A unique `Incident_ID` is generated.
    *   A new incident record is created in MongoDB with `Status: "Pending Info"`.
    *   **Initial KB Retrieval (One-Time):** The LLM performs a semantic search on ChromaDB using the initial user query. The relevant KB chunk content is stored within the incident record for consistent context throughout the incident's lifecycle.
3.  **Clarification (LLM-driven Q&A):**
    *   The LLM, guided by the stored KB context, identifies missing `Required Info`.
    *   It asks clarifying questions to the user.
    *   User responses update the incident's `additional_info` in MongoDB.
    *   The LLM validates user answers for relevance.
    *   Once sufficient information is gathered, the `Status` changes to `"Open"`, and `Solution Steps` (if available in the KB) are provided to the user. If no KB match was found initially, the `Status` becomes `"Pending Admin Review"`.
4.  **Knowledge Base Enrichment:** If an incident involves a new issue not covered by the KB, an Admin can document its resolution, which updates `knowledge_base.txt` and triggers re-vectorization in ChromaDB.
5.  **Admin Incident Retrieval & Management:** Admins can view, filter, and manage all incidents, updating their `Status` (e.g., to `"Resolved"`) in MongoDB.

## Technologies Used

*   **Frontend:** `React` with `Vite`
*   **Backend:** `FastAPI` (Python)
*   **Database:** `MongoDB`
*   **Vector Database:** `ChromaDB`
*   **LLM:** `Google Generative AI (Gemini Pro)` via `langchain-google-genai`
*   **Embedding Model:** `Sentence-Transformers (all-MiniLM-L6-v2)`
*   **Styling:** Basic CSS
*   **API Client:** `Axios`

## Getting Started

Follow these steps to set up and run the project locally.

### Prerequisites

*   Python 3.9+
*   Node.js (LTS recommended) & npm
*   MongoDB (local installation or cloud service like MongoDB Atlas)
*   A Google API Key for Generative AI (Gemini Pro)

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd genai-incident-management
```

### 2. Backend Setup

Navigate to the `backend` directory:

```bash
cd backend
```

#### Install Python Dependencies

```bash
pip install -r requirements.txt
```

#### Configure Environment Variables

Create a `.env` file in the `backend` directory and add your configurations:

```env
MONGO_DETAILS="mongodb://localhost:27017/" # Or your MongoDB Atlas connection string
DB_NAME="incident_db"
GOOGLE_API_KEY="YOUR_GOOGLE_GEMINI_API_KEY" # Replace with your actual API key
CHROMA_PATH="./chroma_db"
KB_FILE_PATH="knowledge_base.txt"
```

#### Prepare Knowledge Base File

Ensure the `knowledge_base.txt` file exists in the `backend` directory with your incident resolution knowledge. An example structure is provided in the repository. The application will automatically read, chunk, and vectorize this file into ChromaDB on startup.

#### Run the Backend

```bash
uvicorn main:app --reload --port 8000
```

The backend API will be accessible at `http://localhost:8000`. You should see messages in the console indicating the knowledge base being loaded and vectorized.

### 3. Frontend Setup

Open a new terminal and navigate to the `frontend` directory:

```bash
cd ../frontend
```

#### Install Node.js Dependencies

```bash
npm install
```

#### Run the Frontend

```bash
npm run dev
```

The frontend application will open in your browser, typically at `http://localhost:5173`.

## Usage

### User Interface

1.  Open your browser to `http://localhost:5173`.
2.  Type your IT-related problem or query into the input field and press Enter.
3.  The AI will respond, either greeting you, clarifying the issue, providing solution steps, or informing you about the incident creation.
4.  The "Active Incident ID" will be displayed above the chat window once an IT incident is initiated.
5.  If you say "bye" or "thanks", the incident will be marked as Resolved, and the session will clear.

### Admin Dashboard

1.  Switch to the "Admin UI" tab in the frontend.
2.  **Knowledge Base Editor:**
    *   The current content of `knowledge_base.txt` is displayed.
    *   You can edit this content directly to add new use cases, required info, or solution steps.
    *   Click "Update Knowledge Base" to save changes and re-index ChromaDB, making the new knowledge instantly available to the LLM.
3.  **Incidents List:**
    *   View a table of all incidents.
    *   Filter incidents by their `Status` (Pending Info, Pending Admin Review, Open, Resolved).
    *   Click "View Details" to see the full conversation history, user demand, status, and the initial KB context that was used for the incident.
    *   You can manually change an incident's status using the dropdown or the "Resolve"/"Reopen" buttons.

## Project Structure

```
├── genai-incident-management/
│   ├── backend/
│   │   ├── main.py               # FastAPI application entry point, includes startup/shutdown logic
│   │   ├── config.py             # Configuration for MongoDB, LLM API key, ChromaDB paths
│   │   ├── models.py             # Pydantic models for request/response bodies and DB schemas
│   │   ├── db/
│   │   │   ├── mongodb.py        # MongoDB connection and CRUD operations for incidents
│   │   │   └── chromadb.py       # ChromaDB connection, KB loading, chunking, embedding, and search
│   │   ├── services/
│   │   │   ├── llm_service.py    # LLM integration (Google Generative AI), prompt engineering, session history
│   │   │   └── kb_service.py     # Knowledge Base file management (read/write knowledge_base.txt, trigger re-vectorization)
│   │   ├── routes/
│   │   │   ├── user_routes.py    # API endpoints for user interactions (chat, incident creation/update)
│   │   │   └── admin_routes.py   # API endpoints for admin interactions (incident list/details, KB update)
│   │   ├── knowledge_base.txt    # The primary text file containing all incident knowledge
│   │   └── requirements.txt      # Python dependencies
│   │
│   └── frontend/
│       ├── package.json          # Frontend dependencies
│       ├── vite.config.js        # Vite configuration, including proxy for backend API
│       ├── public/
│       │   └── index.html        # HTML entry point
│       ├── src/
│       │   ├── main.jsx          # React app entry point
│       │   ├── App.jsx           # Main App component, handles tab switching (User/Admin)
│       │   ├── components/
│       │   │   ├── Header.jsx        # Component for User/Admin tab navigation
│       │   │   ├── ChatWindow.jsx    # Displays chat messages
│       │   │   └── MessageInput.jsx  # Input field for user messages
│       │   ├── pages/
│       │   │   ├── UserUI.jsx        # User-facing incident reporting interface
│       │   │   └── AdminDashboard.jsx # Admin interface for incident and KB management
│       │   ├── services/
│       │   │   └── api.js            # Axios-based service for communicating with backend API
│       │   └── index.css           # Global styles for the application
```

## Future Enhancements

*   **User Authentication:** Implement user login for both user and admin roles.
*   **Real-time Updates:** Use WebSockets for real-time chat updates in the User UI and incident list updates in the Admin Dashboard.
*   **More Sophisticated KB Retrieval:** Implement re-ranking or conversational retrieval over time within an incident if needed, while still leveraging the initial context.
*   **Multi-Modal LLM:** Explore using multi-modal LLMs for users to upload screenshots of errors.
*   **Incident Assignment:** Allow admins to assign incidents to specific IT agents.
*   **Notifications:** Implement email or in-app notifications for incident status changes.
*   **Dockerization:** Containerize the application using Docker for easier deployment.
*   **Testing:** Add unit and integration tests for both frontend and backend.

---

Feel free to contribute, open issues, or suggest improvements!
```