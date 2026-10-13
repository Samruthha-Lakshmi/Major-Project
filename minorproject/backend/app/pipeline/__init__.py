"""The eight pipeline stages, from raw bytes to a publication-ready HTML report."""

STAGES = [
    ("ingest", "Ingestion & Validation", "Load the dataset and verify schema and types"),
    ("preprocess", "Preprocessing", "Handle missing values, duplicates and outliers"),
    ("eda", "Exploratory Analysis", "Profile structure, distributions and relationships"),
    ("stats", "Statistical Analysis", "Descriptive and inferential tests with FDR control"),
    ("insights", "Insight & Anomaly Detection", "Rank significant findings, flag anomalies"),
    ("viz", "Visualization", "Recommend and build a chart for each finding"),
    ("narrative", "Narrative Generation", "Turn validated findings into news copy"),
    ("report", "HTML Report", "Assemble the publication-ready news report"),
]
