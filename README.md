# PrizePicks vs Pinnacle Odds Comparison

This web application compares player props between PrizePicks and Pinnacle, calculating no-vig odds to help find the best value bets.

## Features

- Real-time comparison of player props between PrizePicks and Pinnacle
- No-vig odds calculations
- Responsive design for all devices
- Auto-refreshing data every minute

## Prerequisites

- Python 3.8+
- Node.js 16+
- Chrome browser (for web scraping)
- ChromeDriver (matching your Chrome version)

## Setup

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Start the backend server:
   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

## Usage

1. Open your browser and navigate to `http://localhost:5173`
2. The application will automatically fetch and display the latest prop comparisons
3. Data refreshes every minute automatically

## Notes

- The application uses Selenium for web scraping, so Chrome must be installed
- Make sure ChromeDriver is in your system PATH
- The backend runs on port 8000, and the frontend runs on port 5173 by default

## Security Considerations

- This is a development version. For production:
  - Implement proper authentication
  - Add rate limiting
  - Configure CORS properly
  - Use environment variables for sensitive data
  - Add error handling and logging # cursorAIOddsjam
