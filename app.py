import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import re
from dotenv import load_dotenv

# Configure page
st.set_page_config(
    page_title="AI Credit Card Statement Analyzer",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load environment variables
load_dotenv()

# Get Gemini API key from .env file
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("⚠️ Gemini API key not found! Please set GEMINI_API_KEY in your .env file.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

# Initialize session state
if 'all_statements' not in st.session_state:
    st.session_state.all_statements = []
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'last_upload_count' not in st.session_state:
    st.session_state.last_upload_count = 0

def parse_amount(amount_str):
    """Extract numeric value from any currency string"""
    numeric_str = re.sub(r'[^\d.-]', '', str(amount_str))
    try:
        return float(numeric_str)
    except:
        return 0.0

def extract_data_from_file(uploaded_file, file_index, total_files):
    """Send PDF/Image to Gemini and extract structured data"""
    try:
        uploaded_file.seek(0)
        file_data = uploaded_file.read()
        
        file_type = uploaded_file.type
        if not file_type:
            if uploaded_file.name.lower().endswith('.pdf'):
                file_type = "application/pdf"
            elif uploaded_file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                file_type = f"image/{uploaded_file.name.split('.')[-1].lower()}"
        
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = """
        Extract structured financial data from this credit card statement (PDF or Image).
        
        Return ONLY a valid JSON object with the following structure (no markdown, no code blocks):
        {
          "issuer": "Bank Name",
          "customer_name": "Customer Name",
          "card_type": "Card Type",
          "card_last_4": "last 4 digits",
          "statement_period": {
            "from": "DD-MMM-YYYY",
            "to": "DD-MMM-YYYY"
          },
          "payment_due_date": "DD-MMM-YYYY",
          "credit_limit": "Amount with currency",
          "available_credit_limit": "Amount with currency",
          "total_amount_due": "Amount with currency",
          "minimum_amount_due": "Amount with currency",
          "transactions": [
            {
              "date": "DD-MMM-YYYY",
              "description": "Transaction description",
              "amount": "Amount with currency",
              "type": "Debit or Credit",
              "category": "Category name"
            }
          ],
          "insights": [
            "Insight 1",
            "Insight 2",
            "Insight 3"
          ]
        }
        
        Important:
        - For transactions, categorize them into: Food & Dining, Shopping, Transport, Travel, Entertainment, Groceries, Bills & Utilities, Payment, Other
        - Extract ALL transactions from the statement
        - Provide at least 3-5 meaningful insights about spending patterns
        - Return ONLY the JSON, no additional text or markdown
        """
        
        file_part = {
            "mime_type": file_type,
            "data": file_data
        }
        
        response = model.generate_content([prompt, file_part])
        response_text = response.text.strip()
        
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        response_text = response_text.strip()
        data = json.loads(response_text)
        data['filename'] = uploaded_file.name
        
        return data, None
    
    except json.JSONDecodeError as e:
        return None, f"JSON parsing error in {uploaded_file.name}: {str(e)}"
    except Exception as e:
        return None, f"Error processing {uploaded_file.name}: {str(e)}"

def create_aggregate_category_chart(all_statements):
    """Create pie chart for combined spending across all cards"""
    all_transactions = []
    for stmt in all_statements:
        if 'transactions' in stmt:
            for txn in stmt['transactions']:
                if txn.get('type', '').lower() == 'debit':
                    all_transactions.append({
                        'category': txn.get('category', 'Other'),
                        'amount': parse_amount(txn.get('amount', '0'))
                    })
    
    if not all_transactions:
        return None
    
    df = pd.DataFrame(all_transactions)
    category_spending = df.groupby('category')['amount'].sum().reset_index()
    category_spending = category_spending.sort_values('amount', ascending=False)
    
    fig = px.pie(
        category_spending,
        values='amount',
        names='category',
        title='Combined Spending by Category',
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=400)
    
    return fig

def create_card_comparison_chart(all_statements):
    """Create bar chart comparing spending across cards"""
    card_data = []
    for stmt in all_statements:
        card_name = f"{stmt.get('issuer', 'Unknown')} *{stmt.get('card_last_4', '****')}"
        total_due = parse_amount(stmt.get('total_amount_due', '0'))
        credit_limit = parse_amount(stmt.get('credit_limit', '0'))
        
        card_data.append({
            'Card': card_name,
            'Total Due': total_due,
            'Credit Limit': credit_limit,
            'Utilization %': (total_due / credit_limit * 100) if credit_limit > 0 else 0
        })
    
    df = pd.DataFrame(card_data)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Total Due',
        x=df['Card'],
        y=df['Total Due'],
        marker_color='#FF6B6B'
    ))
    fig.add_trace(go.Bar(
        name='Credit Limit',
        x=df['Card'],
        y=df['Credit Limit'],
        marker_color='#4ECDC4'
    ))
    
    fig.update_layout(
        title='Card-wise Comparison',
        barmode='group',
        height=400,
        xaxis_title='Cards',
        yaxis_title='Amount'
    )
    
    return fig

def create_individual_category_chart(statement):
    """Create pie chart for individual card spending"""
    transactions = statement.get('transactions', [])
    debit_txns = [txn for txn in transactions if txn.get('type', '').lower() == 'debit']
    
    if not debit_txns:
        return None
    
    category_data = {}
    for txn in debit_txns:
        category = txn.get('category', 'Other')
        amount = parse_amount(txn.get('amount', '0'))
        category_data[category] = category_data.get(category, 0) + amount
    
    df = pd.DataFrame(list(category_data.items()), columns=['category', 'amount'])
    df = df.sort_values('amount', ascending=False)
    
    fig = px.pie(
        df,
        values='amount',
        names='category',
        title='Spending by Category',
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=350)
    
    return fig

# Custom CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
    }
    .comparison-table {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header"><h1>💳 AI Credit Card Portfolio Analyzer</h1><p>Powered by Google Gemini AI</p></div>', unsafe_allow_html=True)

# File uploader
st.markdown("### 📤 Upload Credit Card Statements")
st.markdown("*Upload multiple statements from same or different banks*")

uploaded_files = st.file_uploader(
    "Choose files",
    type=['pdf', 'png', 'jpg', 'jpeg'],
    accept_multiple_files=True,
    help="Upload multiple credit card statements in PDF or image format",
    label_visibility="collapsed"
)

# Process files
if uploaded_files:
    current_upload_count = len(uploaded_files)
    
    # Check if new files were uploaded
    if current_upload_count != st.session_state.last_upload_count:
        st.session_state.last_upload_count = current_upload_count
        st.session_state.all_statements = []
        st.session_state.processing_complete = False
    
    # Process if not already done
    if not st.session_state.processing_complete:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"🤖 Analyzing statement {idx + 1} of {len(uploaded_files)}: {uploaded_file.name}")
            progress_bar.progress((idx) / len(uploaded_files))
            
            data, error = extract_data_from_file(uploaded_file, idx + 1, len(uploaded_files))
            
            if error:
                st.error(f"❌ {error}")
            else:
                st.session_state.all_statements.append(data)
        
        progress_bar.progress(100)
        status_text.text(f"✅ Successfully analyzed {len(st.session_state.all_statements)} of {len(uploaded_files)} statements!")
        st.session_state.processing_complete = True
        st.rerun()

# Display results
if st.session_state.all_statements:
    all_statements = st.session_state.all_statements
    
    st.divider()
    
    # Portfolio Overview
    st.header("📊 Portfolio Overview")
    
    # Calculate aggregate metrics
    total_cards = len(all_statements)
    total_due = sum(parse_amount(stmt.get('total_amount_due', '0')) for stmt in all_statements)
    total_credit = sum(parse_amount(stmt.get('credit_limit', '0')) for stmt in all_statements)
    total_available = sum(parse_amount(stmt.get('available_credit_limit', '0')) for stmt in all_statements)
    avg_utilization = (total_due / total_credit * 100) if total_credit > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Cards", total_cards)
    with col2:
        st.metric("Combined Due", f"₹{total_due:,.2f}")
    with col3:
        st.metric("Total Credit Limit", f"₹{total_credit:,.2f}")
    with col4:
        st.metric("Avg Utilization", f"{avg_utilization:.1f}%")
    
    st.divider()
    
    # Aggregate Analytics
    st.header("📈 Aggregate Analytics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_agg_category = create_aggregate_category_chart(all_statements)
        if fig_agg_category:
            st.plotly_chart(fig_agg_category, use_container_width=True)
    
    with col2:
        fig_comparison = create_card_comparison_chart(all_statements)
        if fig_comparison:
            st.plotly_chart(fig_comparison, use_container_width=True)
    
    st.divider()
    
    # Card Comparison Table
    st.header("🔄 Card Comparison")
    
    comparison_data = []
    for stmt in all_statements:
        comparison_data.append({
            'Issuer': stmt.get('issuer', 'N/A'),
            'Card Type': stmt.get('card_type', 'N/A'),
            'Last 4 Digits': stmt.get('card_last_4', 'N/A'),
            'Total Due': stmt.get('total_amount_due', 'N/A'),
            'Credit Limit': stmt.get('credit_limit', 'N/A'),
            'Due Date': stmt.get('payment_due_date', 'N/A'),
            'Utilization': f"{(parse_amount(stmt.get('total_amount_due', '0')) / parse_amount(stmt.get('credit_limit', '1')) * 100):.1f}%" if parse_amount(stmt.get('credit_limit', '0')) > 0 else 'N/A'
        })
    
    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # Individual Card Details (Tabs)
    st.header("💳 Individual Card Details")
    
    # Create tabs for each card
    tab_names = [f"{stmt.get('issuer', 'Card')} *{stmt.get('card_last_4', '****')}" for stmt in all_statements]
    tabs = st.tabs(tab_names)
    
    for idx, tab in enumerate(tabs):
        with tab:
            stmt = all_statements[idx]
            
            # Card Information
            st.subheader("💳 Card Information")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Issuer", stmt.get('issuer', 'N/A'))
                st.metric("Card Type", stmt.get('card_type', 'N/A'))
            
            with col2:
                st.metric("Card Number", f"**** {stmt.get('card_last_4', 'N/A')}")
                st.metric("Customer", stmt.get('customer_name', 'N/A'))
            
            with col3:
                period = stmt.get('statement_period', {})
                st.metric("Statement Period", f"{period.get('from', 'N/A')} to {period.get('to', 'N/A')}")
                st.metric("Due Date", stmt.get('payment_due_date', 'N/A'))
            
            with col4:
                st.metric("Credit Limit", stmt.get('credit_limit', 'N/A'))
                st.metric("Available Limit", stmt.get('available_credit_limit', 'N/A'))
            
            # Financial Summary
            st.subheader("💰 Financial Summary")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Amount Due", stmt.get('total_amount_due', 'N/A'))
            
            with col2:
                st.metric("Minimum Amount Due", stmt.get('minimum_amount_due', 'N/A'))
            
            with col3:
                credit_limit_val = parse_amount(stmt.get('credit_limit', '0'))
                total_due_val = parse_amount(stmt.get('total_amount_due', '0'))
                
                if credit_limit_val > 0:
                    utilization = (total_due_val / credit_limit_val) * 100
                    st.metric("Credit Utilization", f"{utilization:.1f}%")
                else:
                    st.metric("Credit Utilization", "N/A")
            
            # Insights
            st.subheader("💡 AI Insights")
            insights = stmt.get('insights', [])
            if insights:
                for i, insight in enumerate(insights, 1):
                    st.info(f"**{i}.** {insight}")
            
            # Category Chart
            st.subheader("📊 Spending Analysis")
            col1, col2 = st.columns(2)
            
            with col1:
                fig_category = create_individual_category_chart(stmt)
                if fig_category:
                    st.plotly_chart(fig_category, use_container_width=True)
            
            with col2:
                # Transaction summary
                transactions = stmt.get('transactions', [])
                total_txns = len(transactions)
                debit_txns = len([t for t in transactions if t.get('type', '').lower() == 'debit'])
                credit_txns = len([t for t in transactions if t.get('type', '').lower() == 'credit'])
                
                st.metric("Total Transactions", total_txns)
                st.metric("Debit Transactions", debit_txns)
                st.metric("Credit Transactions", credit_txns)
            
            # Transactions Table
            st.subheader("📝 All Transactions")
            if transactions:
                df_txns = pd.DataFrame(transactions)
                st.dataframe(
                    df_txns,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "date": st.column_config.TextColumn("Date", width="medium"),
                        "description": st.column_config.TextColumn("Description", width="large"),
                        "amount": st.column_config.TextColumn("Amount", width="small"),
                        "type": st.column_config.TextColumn("Type", width="small"),
                        "category": st.column_config.TextColumn("Category", width="medium")
                    }
                )
    
    st.divider()
    
    # Export Options
    st.header("💾 Export Data")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export all statements as JSON
        all_data_json = json.dumps(all_statements, indent=2, ensure_ascii=False)
        st.download_button(
            label="📥 Download All (JSON)",
            data=all_data_json,
            file_name="all_statements.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col2:
        # Export all transactions as CSV
        all_transactions = []
        for stmt in all_statements:
            card_id = f"{stmt.get('issuer', 'Unknown')} *{stmt.get('card_last_4', '****')}"
            for txn in stmt.get('transactions', []):
                txn_copy = txn.copy()
                txn_copy['card'] = card_id
                all_transactions.append(txn_copy)
        
        if all_transactions:
            df_all_txns = pd.DataFrame(all_transactions)
            csv_data = df_all_txns.to_csv(index=False, encoding='utf-8')
            st.download_button(
                label="📥 Download Transactions (CSV)",
                data=csv_data,
                file_name="all_transactions.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col3:
        # Export comparison table
        csv_comparison = df_comparison.to_csv(index=False, encoding='utf-8')
        st.download_button(
            label="📥 Download Comparison (CSV)",
            data=csv_comparison,
            file_name="card_comparison.csv",
            mime="text/csv",
            use_container_width=True
        )

elif not uploaded_files:
    # Welcome screen
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 🤖 AI-Powered")
        st.markdown("Advanced Gemini AI extracts data with high accuracy from any credit card statement")
    
    with col2:
        st.markdown("### 📊 Portfolio View")
        st.markdown("Analyze multiple cards together with aggregate insights and comparisons")
    
    with col3:
        st.markdown("### 💾 Easy Export")
        st.markdown("Download your data in JSON or CSV format for further analysis")
    
    st.markdown("---")
    
    st.markdown("### 📋 What We Extract:")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        - ✅ Card details (issuer, type, number)
        - ✅ Billing period and due dates
        - ✅ Credit limit and utilization
        - ✅ Total and minimum payment due
        """)
    
    with col2:
        st.markdown("""
        - ✅ All transactions with dates
        - ✅ Automatic category classification
        - ✅ Spending trends and patterns
        - ✅ Personalized financial insights
        """)
    
    st.markdown("---")
    st.info("👆 Upload multiple credit card statements to get started with your portfolio analysis!")

# Footer
st.divider()
st.markdown(
    "<div style='text-align: center; color: gray; padding: 2rem;'>Built with ❤️ using Streamlit and Google Gemini AI</div>",
    unsafe_allow_html=True
)