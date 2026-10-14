🎨 DrawTogether — Real-Time Multiplayer Drawing & Guessing Game

DrawTogether is a real-time multiplayer drawing and guessing game where players take turns drawing secret words while other players try to guess them before time runs out. Players earn points for correct guesses and compete on a live scoreboard.

✨ Features

Create and Join Rooms: Create a game room and invite friends using a unique room code.

Multiplayer Gameplay: Connect multiple players to the same room.

Real-Time Drawing: Share drawing strokes between connected players using WebSockets.

Secret Word Guessing: The drawer receives a secret word while other players attempt to guess it.

Live Chat: Display guesses and game notifications in real time.

Scoring System: Award points for correct guesses and display player rankings.

Round-Based Gameplay: Configure the number of rounds for a game.

Drawing Tools: Choose colors, adjust brush size, and clear the canvas.

Game Results: Display final scores, rankings, and the winner.

Responsive Interface: A modern dark-themed interface built with React and Material UI.

🛠️ Tech Stack

Frontend

React.js

TypeScript

Vite

Material UI (MUI)

React Router

Axios

WebSockets

Backend

Python

FastAPI

SQLAlchemy

Pydantic

Alembic

JWT Authentication

WebSockets

SlowAPI for rate limiting

Database and Tools

MySQL

Git and GitHub

Visual Studio Code

🏗️ Project Structure

realtime-drawing-game/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── main.py
│   ├── alembic/
│   └── requirements.txt
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── game/
│   │   │   ├── lobby/
│   │   │   └── results/
│   │   ├── pages/
│   │   ├── types/
│   │   └── App.tsx
│   ├── .env
│   └── package.json
│
└── README.md

⚙️ Prerequisites

Install the following before running the project:

Python 3.12

Node.js and npm

MySQL 8.0

Git

🚀 Getting Started

1. Clone the Repository

git clone https://github.com/YOUR_USERNAME/realtime-drawing-game.git
cd realtime-drawing-game

Replace YOUR_USERNAME with your GitHub username and update the repository URL if your repository has a different name.

2. Set Up the Backend

Open a terminal in the project root and navigate to the backend:

cd backend

Create and activate a virtual environment.

Windows — Git Bash:

python -m venv .venv
source .venv/Scripts/activate

Install the backend dependencies:

pip install -r requirements.txt

3. Configure Environment Variables

Configure the database connection string, JWT secret, and other required settings using the environment-variable names expected by your backend configuration.

For example, your configuration may include:

DATABASE_URL=mysql+pymysql://USERNAME:PASSWORD@localhost:3306/draw_together
SECRET_KEY=replace_with_a_secure_random_secret

Use the actual variable names required by your backend/app/core/config.py. Do not commit real passwords, JWT secrets, or access tokens to GitHub.

Create the database in MySQL if your application does not create it automatically.

4. Apply Database Migrations

From the backend directory, run:

alembic upgrade head

5. Start the Backend Server

From the backend directory, run:

uvicorn app.main:app --reload

The backend API will be available at:

API base URL: http://127.0.0.1:8000/api/v1

Swagger API documentation: http://127.0.0.1:8000/docs

6. Set Up the Frontend

Open a second terminal and navigate to the frontend directory:

cd frontend

Install the dependencies:

npm install

Create or update the frontend .env file:

VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1

Start the development server:

npm run dev

Open the local URL shown in the terminal, usually:

http://localhost:5173

🎮 How to Play

Open DrawTogether in your browser.

Click Create Room, enter your player name, and select the number of rounds.

Share the generated room code with your friends.

Other players select Join Room and enter the room code.

Players mark themselves ready in the lobby.

Start the game when the required players are ready.

The assigned drawer draws the secret word on the canvas.

Other players submit guesses through the chat panel.

Correct guesses earn points, and the scoreboard displays player rankings.

At the end of the game, view the final results and winner.

🔌 Real-Time Communication

The application uses WebSockets to exchange live game events between connected players.

The WebSocket endpoint follows this pattern:

/ws/rooms/{room_code}?player_id={player_id}&token={access_token}

Events support game interactions such as drawing strokes, clearing the canvas, submitting guesses, updating player presence, and communicating game-state changes.

🔐 Security

JWT-based player authentication.

Protected player operations.

Server-side validation of drawing and guessing events.

Rate limiting on selected API endpoints.

Environment-based configuration for sensitive credentials.

🧪 Build the Frontend

To verify the frontend TypeScript and production build:

cd frontend
npm run build