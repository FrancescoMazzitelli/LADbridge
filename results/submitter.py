import csv
import requests
import json
import os
from datetime import datetime
from statistics import mean
import pandas as pd
import plotly.graph_objects as go
import kaleido
kaleido.get_chrome_sync()


# ================= CONFIG =================
BASE_URL = "http://localhost:5500/api/control/invoke"
CSV_FILE = "questions.csv"
PDF_FILE = "paper033.pdf"
OUTPUT_FILE = "results.txt"
LATENCY_CSV = "latencies.csv"
SCATTER_OUT = "latency_scatter.pdf"
BOXPLOT_OUT = "latency_boxplot.pdf"
TIMEOUT = 3600
# ==========================================


def load_questions(csv_path):
    questions = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append(row["question"])
    return questions


def invoke_controller(question, pdf_path):
    with open(pdf_path, "rb") as pdf_file:
        files = {
            "file": (os.path.basename(pdf_path), pdf_file, "application/pdf")
        }
        data = {
            "input": question
        }

        response = requests.post(
            BASE_URL,
            files=files,
            data=data,
            timeout=TIMEOUT
        )

    return response


def write_result(f, idx, question, response):
    f.write(f"\n{'='*80}\n")
    f.write(f"Question #{idx}\n")
    f.write(f"Question:\n{question}\n\n")

    if response.status_code != 200:
        f.write(f"[ERROR] HTTP {response.status_code}\n")
        f.write(response.text + "\n")
        return None

    try:
        result_json = response.json()
    except Exception:
        f.write("[ERROR] Response is not JSON\n")
        f.write(response.text + "\n")
        return None

    plan = result_json.get("execution_plan")
    results = result_json.get("execution_results")
    latency = result_json.get("plan_generation_latency")

    f.write(f"Plan generation latency (s): {latency}\n\n")

    f.write("Execution Plan:\n")
    f.write(json.dumps(plan, indent=2, ensure_ascii=False))
    f.write("\n\n")

    f.write("Execution Results:\n")
    f.write(json.dumps(results, indent=2, ensure_ascii=False))
    f.write("\n")

    return latency


# ================= PLOTTING =================

def save_latencies_csv(latencies):
    df = pd.DataFrame({"latency": latencies})
    df.to_csv(LATENCY_CSV, index=False)
    print(f"✅ Latencies saved to {LATENCY_CSV}")


def plot_scatter(latencies):
    x_vals = list(range(1, len(latencies) + 1))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_vals,
        y=latencies,
        mode="markers+lines",
        marker=dict(size=8),
        name="Plan generation latency"
    ))

    fig.update_layout(
        title="Plan Generation Latency per Question",
        xaxis_title="Question index",
        yaxis_title="Latency (seconds)",
        xaxis=dict(tickmode="array", tickvals=x_vals),
        template="plotly_white"
    )

    fig.write_image(SCATTER_OUT)
    print(f"📊 Scatter plot saved to {SCATTER_OUT}")


def plot_boxplot(latencies):
    avg_latency = mean(latencies)

    fig = go.Figure()
    fig.add_trace(go.Box(
        y=latencies,
        boxmean=True,
        name="Latency distribution"
    ))

    fig.add_annotation(
        text=f"Mean latency = {avg_latency:.3f} s",
        x=0.5,
        y=avg_latency,
        xref="paper",
        yref="y",
        showarrow=False,
        font=dict(size=12),
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black"
    )

    fig.update_layout(
        title="Distribution of Plan Generation Latencies",
        yaxis_title="Latency (seconds)",
        template="plotly_white"
    )

    fig.write_image(BOXPLOT_OUT)
    print(f"📦 Boxplot saved to {BOXPLOT_OUT}")


# ================= MAIN =================

def main():
    if not os.path.exists(PDF_FILE):
        raise FileNotFoundError(f"PDF not found: {PDF_FILE}")

    questions = load_questions(CSV_FILE)
    latencies = []
    #responses = []

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("Execution results\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Total questions: {len(questions)}\n")

        for idx, question in enumerate(questions, start=1):
            print(f"[{idx}/{len(questions)}] Processing question...")
            try:
                response = invoke_controller(question, PDF_FILE)
                latency = write_result(f, idx, question, response)
                if latency is not None:
                    latencies.append(latency)
                #if response is not None:
                    #responses.append(response)
            except Exception as e:
                f.write(f"\n[EXCEPTION] {str(e)}\n")

    save_latencies_csv(latencies)
    plot_scatter(latencies)
    plot_boxplot(latencies)

    print("\n✅ Experiment completed successfully")


if __name__ == "__main__":
    main()
