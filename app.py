from flask import Flask, request, jsonify, render_template
import requests
import google.generativeai as genai
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# Securely get API keys from environment
TIINGO_API_KEY = os.getenv("TIINGO_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Check if keys are loaded
if not TIINGO_API_KEY or not GEMINI_API_KEY:
    raise ValueError("API keys for Tiingo or Gemini not found. Please check your .env file.")

# Configure the Gemini API client
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

@app.route("/")
def index():
    """Serves the main HTML page."""
    return render_template("index.html")

@app.route("/api/stock", methods=["POST"])
def get_stock_info():
    """Fetches stock data from Tiingo and gets an AI analysis from Gemini."""
    data = request.json
    symbol = data.get("symbol")
    if not symbol:
        return jsonify({"error": "Stock symbol was not provided."}), 400

    # --- CRITICAL FIX ---
    # The Tiingo API key must be sent as a URL parameter, NOT an Authorization header.
    tiingo_url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices?token={TIINGO_API_KEY}"

    try:
        # Make the request to Tiingo without the incorrect header
        tiingo_response = requests.get(tiingo_url)
        tiingo_response.raise_for_status() # This will raise an exception for HTTP errors (like 401, 404)

        stock_data_list = tiingo_response.json()
        if not stock_data_list:
            return jsonify({"error": f"No data found for symbol '{symbol}'. Please check the symbol (e.g., 'AAPL' or 'TCS.NS')."}), 404

        # Get the most recent data point
        stock_data = stock_data_list[0]
        
        # --- IMPROVED PROMPT for better analysis ---
        prompt = f"""
        Analyze the following stock data for the symbol '{symbol}' and provide a detailed investment analysis.

        Latest Data:
        - Date: {stock_data.get('date', 'N/A').split('T')[0]}
        - Close Price: {stock_data.get('close', 'N/A')}
        - High: {stock_data.get('high', 'N/A')}
        - Low: {stock_data.get('low', 'N/A')}
        - Volume: {stock_data.get('volume', 'N/A')}

        Structure your response in markdown with these sections:
        1.  **Performance Summary:** Briefly summarize the day's performance.
        2.  **Market Context:** How does this data fit into the stock's recent history and the broader market?
        3.  **Investment Recommendation:** Give a clear, actionable recommendation (e.g., Strong Buy, Hold, Sell).
        4.  **Risk Analysis:** What are the key risks an investor should consider?
        """

        gemini_response = model.generate_content(prompt)

        return jsonify({
            "symbol": symbol,
            "stock_data": stock_data,
            "gemini_analysis": gemini_response.text
        })

    except requests.exceptions.HTTPError as http_err:
        # Handle specific HTTP errors from Tiingo (e.g., invalid key, symbol not found)
        error_detail = "Failed to fetch stock data. Check the symbol or your API key."
        if tiingo_response.status_code == 401:
            error_detail = "Authentication failed. Your Tiingo API key is invalid."
        return jsonify({"error": error_detail}), tiingo_response.status_code
    except Exception as e:
        # Handle other potential errors
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True)