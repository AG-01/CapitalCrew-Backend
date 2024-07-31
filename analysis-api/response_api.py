from flask import Flask, request, jsonify
import requests
import os
from groq import Groq

app = Flask(__name__)

# Load Groq API key from environment variable
try:
    GROQ_API_KEY = os.environ['GROQ_API_KEY']
    client = Groq(api_key=GROQ_API_KEY)
except KeyError as e:
    print(f"Environment variable {e} not set. Please check your environment configuration.")

def fetch_stock_info(symbol):
    api_url = f"https://api.cloudquote.io/fcon/getQuote.json?symbol={symbol}&T=ek75s25rzz4"
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json().get('rows')[0]
    else:
        return None

def generate_article(symbol, stock_info, time_period):
    article = ""
    change_percent = round(stock_info.get('ChangePercent', 0), 3)
    
    try:
        if time_period == "Mid-day":
            open_price = round(stock_info.get("Open"), 3)
            open_present_prompt = " " if not open_price else f"opened today at ${open_price}"
            prompt = f"Write an engaging informative article in 100 words about the stock XYZ {open_present_prompt}, currently trading at ${round(stock_info.get('Price', 0), 3)}, previous session close price was ${round(stock_info.get('PrevClose', 0), 3)}, current volume is {stock_info.get('Volume', 0)}"
            if change_percent > 0:
                prompt += f" and change percent from market open till now is {change_percent}"
        elif time_period == "Pre-market-bullish":
            prompt = f"Write an engaging informative article in 100 words about the stock XYZ that opened at bullish price ${round(stock_info.get('AfterHoursPrice', 0), 3)}, previous session close price was ${round(stock_info.get('PrevClose', 0), 3)}, current volume is {stock_info.get('Volume', 0)}"
            change_percent = (round(stock_info.get('AfterHoursPrice', 0), 3) / round(stock_info.get('PrevClose', 0), 3) - 1) * 100
            if change_percent > 0:
                prompt += f" and change percent from market open till now is {change_percent}. "
            if change_percent > 20:
                prompt += f"Article should sound like exciting announcement "
        elif time_period == "Pre-market-bearish":
            prompt = f"Write an engaging informative article in 100 words about the stock XYZ that opened at bearish price ${round(stock_info.get('AfterHoursPrice', 0), 3)}, previous session close price was ${round(stock_info.get('PrevClose', 0), 3)}, current volume is {stock_info.get('Volume', 0)}"
            change_percent = (round(stock_info.get('AfterHoursPrice', 0), 3) / round(stock_info.get('PrevClose', 0), 3) - 1) * 100
            if change_percent < 0:
                prompt += f" and change percent from market open till now is {change_percent}. "
            if change_percent < -20:
                prompt += f"Article should sound like announcement for major stock fall"
        elif time_period == "Post-market":
            open_price = round(stock_info.get("Open"), 3)
            open_present_prompt = " " if not open_price else f"opened today at ${open_price}"
            change_percent = round(stock_info.get("ChangePercent", 0), 3)
            change_percent_prompt = "showed bullish movement " if change_percent > 0 else "showed bearish movement" if change_percent < 0 else ""
            prompt = f"Write an informative article in 100 words about the stock XYZ {open_present_prompt}, {change_percent_prompt}, closed at price ${round(stock_info.get('Price', 'N/A'), 3)}"
            prompt += f" and change in percent from market open till now is {change_percent}. "
            if change_percent < -10:
                prompt += f"Article should sound like announcement for major stock fall"
            if change_percent > 20:
                prompt += f"Article should sound like exciting announcement "

        company_name = stock_info.get('Name', 'N/A')
        exchange = stock_info.get('ExchangeShortName', 'N/A').upper()

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a financial analyst"},
                {"role": "user", "content": prompt},
                {"role": "user", "content": "Do not mention any trading symbol information"}
            ],
            model="llama-3.1-70b-versatile",
        )

        article = chat_completion.choices[0].message.content

        article = article.replace('XYZ', f' {company_name}({exchange}:{symbol}) ')
        article = article.replace('XYZ stock', f' {company_name}({exchange}:{symbol}) ')
        article = article.replace('xyz', f' {company_name}({exchange}:{symbol}) ')
        article = article.replace('stock XYZ', f' {company_name}({exchange}:{symbol}) ')
        article = article.replace('stock xyz', f' {company_name}({exchange}:{symbol}) ')
        article = article.replace('The stock of company, XYZ', f' {company_name}({exchange}:{symbol}) ')
        article = article.replace('The company, XYZ', f' {company_name}({exchange}:{symbol}) ')

        return article
    except Exception as e:
        print(f"An error occurred while generating the article: {e}")
        return None

@app.route('/generate_article', methods=['POST'])
def api_generate_article():
    data = request.json
    symbol = data.get('symbol')
    time_period = data.get('time_period')

    if not symbol or not time_period:
        return jsonify({"error": "Missing required parameters"}), 400

    stock_info = fetch_stock_info(symbol)
    if not stock_info:
        return jsonify({"error": "Failed to fetch stock information"}), 404

    article = generate_article(symbol, stock_info, time_period)
    if not article:
        return jsonify({"error": "Failed to generate article"}), 500

    response = {
        "symbol": symbol,
        "name": stock_info.get('Name', 'N/A'),
        "price": round(stock_info.get('Price', 'N/A'), 3),
        "prev_close": round(stock_info.get('PrevClose', 'N/A'), 3),
        "volume": stock_info.get('Volume', 'N/A'),
        "exchange": stock_info.get('ExchangeShortName', 'N/A').upper(),
        "change_percent": round(stock_info.get('ChangePercent', 'N/A'), 3),
        "time_period": time_period,
        "article": article
    }

    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True, port = 3001)