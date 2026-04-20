import streamlit as st
from engine import SentinelRAGEngine
from privacy import anonymize_text
import pandas as pd
import plotly.graph_objects as go
import io

st.set_page_config(page_title="SentinelRAG Compliance Screening", layout="wide")

# Sidebar
st.sidebar.title("System Overview")
st.sidebar.markdown("""
SentinelRAG Compliance Engine

Pipeline:
1. Knowledge Graph Lookup  
2. Hybrid Retrieval (Vector + BM25)  
3. Adaptive Cross-Encoder  
4. Deterministic Matching  
5. Structured Decision Output  

Resolution Modes:
- GRAPH  
- HYBRID_FAST  
- HYBRID_RERANK  
""")

# Load Engine Once
@st.cache_resource
def load_engine():
    return SentinelRAGEngine()

engine = load_engine()

st.title("SentinelRAG Compliance Screening")

# ----------------------------
# SINGLE SCREENING SECTION
# ----------------------------
st.header("Single Entity Screening")

query = st.text_input("Enter Entity Name or Identifier")

if st.button("Screen Entity"):

    if not query.strip():
        st.warning("Please enter a valid query.")
    else:
        result = engine.screen(query)

        decision = result["decision"]
        entity_number = result["entity_number"]
        confidence = result["confidence"]
        reason = result["reason"]
        latency = result.get("latency", {})
        mode = result.get("mode", "N/A")

        if decision == "MATCH":
            st.success("Match Detected")
        else:
            st.error("No Match Detected")

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Entity Number", entity_number if entity_number else "N/A")
            st.metric("Confidence Score", f"{confidence:.2f}")
            st.metric("Resolution Mode", mode)

        with col2:
            st.subheader("Decision Rationale")
            st.write(reason)

        if latency:
            st.subheader("Latency Breakdown")
            fig = go.Figure(
                data=[go.Bar(
                    x=list(latency.keys()),
                    y=list(latency.values())
                )]
            )
            fig.update_layout(
                title="Latency Breakdown (milliseconds)",
                xaxis_title="Pipeline Stage",
                yaxis_title="Time (ms)"
            )
            st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# BULK SCREENING SECTION
# ----------------------------
st.header("Bulk Screening (CSV Upload)")

redact_bulk_output = st.checkbox(
    "Redact PII in bulk results/download",
    value=False,
    help="Uses Presidio when ENABLE_PII_REDACTION is enabled."
)

uploaded_file = st.file_uploader(
    "Upload CSV file with a column named 'query'",
    type=["csv"]
)

if uploaded_file is not None:

    try:
        df = pd.read_csv(uploaded_file)

        if "query" not in df.columns:
            st.error("CSV must contain a column named 'query'")
        else:
            st.info(f"Loaded {len(df)} records.")

            results = []

            with st.spinner("Processing bulk screening..."):
                for q in df["query"]:
                    result = engine.screen(str(q))
                    results.append({
                        "query": q,
                        "decision": result["decision"],
                        "entity_number": result["entity_number"],
                        "confidence": result["confidence"],
                        "mode": result.get("mode", ""),
                        "latency_ms": result.get("latency", {}).get("total_ms", 0)
                    })

            results_df = pd.DataFrame(results)

            if redact_bulk_output and "query" in results_df.columns:
                results_df["query"] = results_df["query"].astype(str).apply(anonymize_text)

            st.subheader("Bulk Screening Results")
            st.dataframe(results_df, use_container_width=True)

            # Download Button
            csv_buffer = io.StringIO()
            results_df.to_csv(csv_buffer, index=False)

            st.download_button(
                label="Download Results as CSV",
                data=csv_buffer.getvalue(),
                file_name="sentinelrag_results.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.error(f"Error processing file: {e}")