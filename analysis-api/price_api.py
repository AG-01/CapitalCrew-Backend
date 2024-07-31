from flask import Flask, request, jsonify
import requests
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from matplotlib.dates import DateFormatter
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()
API_KEY = os.getenv("API_KEY")
BASE_URL_AGGS = "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2023-01-09/"
BASE_URL_OC = "https://api.polygon.io/v1/open-close/AAPL/"

@app.route('/plot', methods=['GET'])
def plot():
    try:
        # Get today's date and subtract one day for the end_date
        end_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        api_url = f"{BASE_URL_AGGS}{end_date}"

        # Make the API request
        params = {
            "adjusted": "true",
            "sort": "asc",
            "apiKey": API_KEY
        }

        response = requests.get(api_url, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors

        data = response.json()

        # Extract the results
        results = data['results']

        # Create a DataFrame
        df = pd.DataFrame(results)

        # Convert timestamp to datetime
        df['t'] = pd.to_datetime(df['t'], unit='ms')

        # Set the datetime as index
        df.set_index('t', inplace=True)

        # Create the plot
        plt.figure(figsize=(12, 6))
        plt.plot(df.index, df['c'], label='Closing Price')
        plt.plot(df.index, df['h'], label='High Price')
        plt.plot(df.index, df['l'], label='Low Price')

        # Customize the plot
        plt.title(f"Stock Prices for AAPL")
        plt.xlabel('Date')
        plt.ylabel('Price (USD)')
        plt.legend()

        # Format x-axis dates
        plt.gca().xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()  # Rotate and align the tick labels

        # Save plot to a bytes buffer
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()

        return jsonify({'image_url': f'data:image/png;base64,{plot_url}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/prices', methods=['GET'])
def get_prices():
    try:
        # Get today's date and subtract one day for the date
        date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        api_url = f"{BASE_URL_OC}{date}?adjusted=true&apiKey={API_KEY}"

        # Make the API request
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        data = response.json()
        high = data.get('high')
        low = data.get('low')
        close = data.get('close')
        result = {
            'high': high,
            'low': low,
            'close': close
        }
        return jsonify(result)
    except requests.exceptions.HTTPError as http_err:
        return jsonify({'error': f"HTTP error occurred: {http_err}"}), response.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=3000)
