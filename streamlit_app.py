"""
Credit Card Statement Parser & Analyzer
Main Streamlit Application
"""

import streamlit as st
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import io
from datetime import datetime
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.parsers.hdfc_parser import HDFCParser
from src.parsers.icici_parser import ICICIParser
from src.parsers.sbi_parser import SBIParser
from src.parsers.axis_parser import AxisParser
from src.parsers.kotak_parser import KotakParser
from src.utils import detect_bank, categorize_transactions, generate_insights, export_to_json, export_to_csv, export_to_excel
from src.ocr_gemini import extract_text_with_gemini

# Page configuration
st.set_page_config(
    page_title="Credit Card Statement Parser",
    page_icon="💳",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stat-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: bold;
        color: #1f77b4;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'parsed_data' not in st.session_state:
    st.session_state.parsed_data = None

def main():
    st.markdown('<div class="main-header">💳 Credit Card Statement Parser & Analyzer</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/bank-card-back-side.png", width=100)
        st.header("📤 Upload Statement")
        uploaded_file = st.file_uploader(
            "Choose your credit card statement PDF",
            type=['pdf'],
            help="Upload PDF statements from HDFC, ICICI, SBI, Axis, or Kotak"
        )
        
        st.markdown("---")
        st.subheader("Supported Banks")
        st.write("✅ HDFC Bank")
        st.write("✅ ICICI Bank")
        st.write("✅ SBI")
        st.write("✅ Axis Bank")
        st.write("✅ Kotak Mahindra")
        
        st.markdown("---")
        st.info("💡 **Tip:** The app automatically detects your bank and uses OCR for scanned PDFs")
    
    # Main content
    if uploaded_file is not None:
        process_statement(uploaded_file)
    else:
        show_welcome_screen()

def show_welcome_screen():
    st.markdown("""
        ## 🎯 Welcome to Credit Card Statement Parser!
        
        ### Features:
        - 📊 **Multi-Bank Support**: Parse statements from HDFC, ICICI, SBI, Axis, and Kotak
        - 🔍 **Auto Detection**: Automatically identifies your bank
        - 🤖 **AI OCR**: Uses Gemini API for scanned PDFs
        - 📈 **Smart Analytics**: Category-wise spending analysis
        - 💡 **Insights**: AI-powered spending insights
        - 📥 **Export Options**: Download as JSON, CSV, or Excel
        
        ### How to Use:
        1. Upload your credit card statement PDF using the sidebar
        2. The app will automatically detect your bank
        3. View your transactions, spending patterns, and insights
        4. Export your data in your preferred format
        
        ### Get Started:
        👈 Upload your statement PDF from the sidebar to begin!
    """)

def process_statement(uploaded_file):
    with st.spinner("🔄 Processing your statement..."):
        try:
            # Save uploaded file temporarily
            temp_file_path = f"temp_{uploaded_file.name}"
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Try to extract text using pdfplumber
            try:
                import pdfplumber
                text = ""
                with pdfplumber.open(temp_file_path) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() or ""
                
                # If text extraction fails, use Gemini OCR
                if not text.strip() or len(text) < 100:
                    st.warning("📷 PDF appears to be scanned. Using AI OCR...")
                    text = extract_text_with_gemini(temp_file_path)
            except:
                st.warning("📷 Using AI OCR for text extraction...")
                text = extract_text_with_gemini(temp_file_path)
            
            # Detect bank
            bank = detect_bank(text)
            st.success(f"🏦 Detected Bank: **{bank.upper()}**")
            
            # Parse based on bank
            parsers = {
                'hdfc': HDFCParser(),
                'icici': ICICIParser(),
                'sbi': SBIParser(),
                'axis': AxisParser(),
                'kotak': KotakParser()
            }
            
            parser = parsers.get(bank)
            if parser:
                parsed_data = parser.parse(text)
                
                # Categorize transactions
                if 'transactions' in parsed_data:
                    parsed_data['transactions'] = categorize_transactions(parsed_data['transactions'])
                
                # Generate insights
                parsed_data['insights'] = generate_insights(parsed_data)
                
                st.session_state.parsed_data = parsed_data
                display_results(parsed_data)
            else:
                st.error("❌ Bank not supported or could not be detected")
            
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
        except Exception as e:
            st.error(f"❌ Error processing statement: {str(e)}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

def display_results(data):
    st.markdown("---")
    st.header("📊 Statement Overview")
    
    # Key metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💳 Card Number", f"XXXX-{data.get('card_last_4', 'N/A')}")
    
    with col2:
        total_due = data.get('total_amount_due', 'N/A')
        st.metric("💰 Total Due", total_due)
    
    with col3:
        due_date = data.get('payment_due_date', 'N/A')
        st.metric("📅 Due Date", due_date)
    
    with col4:
        credit_limit = data.get('credit_limit', 'N/A')
        st.metric("🎯 Credit Limit", credit_limit)
    
    # Statement Period
    if 'statement_period' in data:
        period = data['statement_period']
        st.info(f"📆 Statement Period: **{period.get('from', 'N/A')} to {period.get('to', 'N/A')}**")
    
    # Transactions Table
    st.markdown("---")
    st.header("📝 Transactions")
    
    if 'transactions' in data and data['transactions']:
        df = pd.DataFrame(data['transactions'])
        
        # Display transaction table
        st.dataframe(df, use_container_width=True, height=400)
        
        # Analytics
        display_analytics(df)
    else:
        st.warning("No transactions found in the statement")
    
    # Insights
    if 'insights' in data and data['insights']:
        st.markdown("---")
        st.header("💡 Insights & Alerts")
        for insight in data['insights']:
            st.info(f"ℹ️ {insight}")
    
    # Rewards Points
    if 'rewards_points' in data:
        st.markdown("---")
        st.header("🎁 Rewards Summary")
        rewards = data['rewards_points']
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Earned", rewards.get('earned', 0))
        with col2:
            st.metric("Redeemed", rewards.get('redeemed', 0))
        with col3:
            st.metric("Balance", rewards.get('balance', 0))
    
    # Export options
    st.markdown("---")
    st.header("📥 Export Data")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        json_data = export_to_json(data)
        st.download_button(
            label="Download JSON",
            data=json_data,
            file_name=f"statement_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )
    
    with col2:
        csv_data = export_to_csv(data)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=f"statement_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col3:
        excel_data = export_to_excel(data)
        st.download_button(
            label="Download Excel",
            data=excel_data,
            file_name=f"statement_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def display_analytics(df):
    st.markdown("---")
    st.header("📈 Spending Analytics")
    
    # Filter only debit transactions for analysis
    debit_df = df[df['type'].str.lower() == 'debit'].copy()
    
    if len(debit_df) == 0:
        st.warning("No debit transactions found for analysis")
        return
    
    # Convert amount to numeric (remove ₹ and commas)
    debit_df['amount_numeric'] = debit_df['amount'].str.replace('₹', '').str.replace(',', '').astype(float)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Category-wise Spending")
        category_spending = debit_df.groupby('category')['amount_numeric'].sum().sort_values(ascending=False)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        colors = plt.cm.Set3(range(len(category_spending)))
        ax.pie(category_spending, labels=category_spending.index, autopct='%1.1f%%', colors=colors, startangle=90)
        ax.axis('equal')
        st.pyplot(fig)
        
        # Display category breakdown
        st.write("**Spending Breakdown:**")
        for cat, amount in category_spending.items():
            st.write(f"- {cat}: ₹{amount:,.2f}")
    
    with col2:
        st.subheader("📅 Daily Spending Trend")
        
        # Convert date to datetime
        debit_df['date_parsed'] = pd.to_datetime(debit_df['date'], format='%d-%b-%Y', errors='coerce')
        daily_spending = debit_df.groupby('date_parsed')['amount_numeric'].sum().sort_index()
        
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.bar(range(len(daily_spending)), daily_spending.values, color='#1f77b4', alpha=0.7)
        ax.set_xlabel('Transaction Date')
        ax.set_ylabel('Amount (₹)')
        ax.set_title('Daily Spending Pattern')
        plt.xticks(range(len(daily_spending)), [d.strftime('%d-%b') for d in daily_spending.index], rotation=45, ha='right')
        plt.tight_layout()
        st.pyplot(fig)
        
        # Top transactions
        st.write("**Top 5 Transactions:**")
        top_transactions = debit_df.nlargest(5, 'amount_numeric')[['date', 'description', 'amount']]
        for idx, row in top_transactions.iterrows():
            st.write(f"- {row['date']}: {row['description']} - {row['amount']}")

if __name__ == "__main__":
    main()