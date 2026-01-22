# 🪙 Gold Arbitrage Panel

**Gold Arbitrage Panel** is a comprehensive financial analysis tool designed to track real-time gold prices and identify arbitrage opportunities across different markets.

This Python-based application specifically focuses on comparing **Gold Certificates** (Sertifika) against **Physical Gold** and other variations, calculating the spread to help users make informed investment decisions. It features a fully mobile-responsive interface for monitoring markets on the go.

## 🚀 Key Features

* **Real-Time Data Tracking:** Fetches live gold price data from various financial sources and exchanges.
* **Arbitrage Analysis:** Automatically calculates the spread between Buying and Selling prices to highlight profitable gaps.
* **Asset Comparison:** Detailed comparison between **Gold Certificates**, **Physical Gold**, and **Bank Rates**.
* **Mobile-Ready Interface:** Optimized UI for seamless usage on both desktop and mobile devices.
* **Instant Alerts:** (Optional) Visual indicators for high-margin opportunities.

## 🛠️ Installation & Usage

Follow these steps to set up the project locally:

```bash
# 1. Clone the repository
git clone [https://github.com/akifkeklik/gold-arbitrage-panel.git](https://github.com/akifkeklik/gold-arbitrage-panel.git)
cd gold-arbitrage-panel

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python app.py

📂 Project Structure
app.py: The main application entry point and user interface logic.
services.py: Backend services responsible for data scraping, API handling, and arbitrage calculations.
requirements.txt: List of all Python dependencies required to run the project.
