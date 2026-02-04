import csv
import requests
import json
import os
from datetime import datetime
import pandas as pd
import time
import threading

# ================= CONFIG =================
BASE_URL = "http://localhost:5500/api/control/invoke"
CSV_FILE = "questions.csv"
PDF_FILE = "paper033.pdf"
OUTPUT_FILE = "results.txt"
LATENCY_CSV = "latencies.csv"
TIMEOUT = 3600
SAMPLING_INTERVAL = 0.2

NODE_EXPORTERS = {
    "node1": "http://172.31.20.20:8080/metrics",
    "node2": "http://172.31.20.12:8080/metrics",
    "node3": "http://172.31.20.13:8080/metrics",
    "node4": "http://172.31.20.14:8080/metrics",
    "node5": "http://172.31.20.15:8080/metrics",
    "node6": "http://172.31.20.16:8080/metrics",
    "node7": "http://172.31.20.17:8080/metrics",
    "node8": "http://172.31.20.18:8080/metrics"
}
# ==========================================

# ---------- Helpers ----------

def load_questions(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return [row["question"] for row in csv.DictReader(f)]

def invoke_controller(question, pdf_path):
    with open(pdf_path, "rb") as pdf_file:
        files = {"file": (os.path.basename(pdf_path), pdf_file, "application/pdf")}
        data = {"input": question}
        response = requests.post(BASE_URL, files=files, data=data, timeout=TIMEOUT)

    req_bytes = len(response.request.body or b"")
    resp_bytes = len(response.content)
    return response, req_bytes, resp_bytes

def fetch_node_metrics(url):
    r = requests.get(url, timeout=3600)
    r.raise_for_status()
    metrics = {}
    for line in r.text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        metric, value = line.rsplit(" ", 1)
        try:
            metrics[metric] = float(value)
        except ValueError:
            pass
    return metrics

def sample_node_metrics(buffers, stop_event):
    """Esegue il polling dei metrics per tutti i nodi finché stop_event non è settato."""
    while not stop_event.is_set():
        for node, url in NODE_EXPORTERS.items():
            try:
                buffers[node].append(fetch_node_metrics(url))
            except Exception as e:
                print(f"[WARN] {node}: metrics read failed: {e}")
        time.sleep(SAMPLING_INTERVAL)

# ---------- Aggregazioni ----------

def compute_avg_mem(snapshots):
    vals = [s["node_memory_Active_bytes"] for s in snapshots if "node_memory_Active_bytes" in s]
    return sum(vals) / len(vals) if vals else 0.0

def compute_cpu_top_percent(snapshots, duration):
    """
    CPU top-style per nodo:
    100% = 1 core pieno
    250% = 2.5 core
    """
    if duration <= 0 or len(snapshots) < 2:
        return 0.0

    total_cpu_seconds = 0.0
    for i in range(1, len(snapshots)):
        prev, curr = snapshots[i - 1], snapshots[i]
        for k, v in curr.items():
            if not k.startswith("node_cpu_seconds_total") or 'mode="idle"' in k:
                continue
            delta = v - prev.get(k, v)
            if delta > 0:
                total_cpu_seconds += delta

    return (total_cpu_seconds / duration) * 100.0

def compute_network_rates(snapshots, duration):
    if duration <= 0 or len(snapshots) < 2:
        return 0.0, 0.0

    rx0 = sum(v for k, v in snapshots[0].items() if k.startswith("node_network_receive_bytes_total"))
    rx1 = sum(v for k, v in snapshots[-1].items() if k.startswith("node_network_receive_bytes_total"))
    tx0 = sum(v for k, v in snapshots[0].items() if k.startswith("node_network_transmit_bytes_total"))
    tx1 = sum(v for k, v in snapshots[-1].items() if k.startswith("node_network_transmit_bytes_total"))

    return (rx1 - rx0) / duration, (tx1 - tx0) / duration

# ---------- Output ----------

def write_result(f, idx, question, latency, per_node_usage, cluster_usage):
    f.write(f"\n{'=' * 80}\n")
    f.write(f"Question #{idx}\n{question}\n\n")
    f.write(f"Latency (s): {latency:.3f}\n\n")

    f.write("Resource usage per node:\n")
    for node, usage in per_node_usage.items():
        f.write(f"- {node}: CPU {usage['cpu_percent_top']:.2f}%, "
                f"Mem {usage['mem_bytes'] / 1e9:.2f} GB, "
                f"RX {usage['rx_bytes_per_s']:.2f} B/s, "
                f"TX {usage['tx_bytes_per_s']:.2f} B/s\n")

    f.write("\nCluster aggregate usage:\n")
    f.write(f"CPU (sum cores%): {cluster_usage['cpu_percent_top']:.2f}%\n")
    f.write(f"Memory: {cluster_usage['mem_bytes'] / 1e9:.2f} GB\n")
    f.write(f"Network RX: {cluster_usage['rx_bytes_per_s']:.2f} B/s\n")
    f.write(f"Network TX: {cluster_usage['tx_bytes_per_s']:.2f} B/s\n")

def save_latencies_csv(latencies, usages):
    rows = []
    for i, (lat, usage) in enumerate(zip(latencies, usages), start=1):
        row = {"question_idx": i, "latency_s": lat}
        row.update(usage)
        rows.append(row)
    pd.DataFrame(rows).to_csv(LATENCY_CSV, index=False)
    print(f"✅ Saved {LATENCY_CSV}")

# ---------- MAIN ----------

def main():
    questions = load_questions(CSV_FILE)
    latencies, usages = [], []

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Run at {datetime.now().isoformat()}\n")
        f.write(f"Total questions: {len(questions)}\n")

        for i, q in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] Processing")

            # Setup snapshot buffers per nodo
            snapshots = {node: [] for node in NODE_EXPORTERS}
            stop = threading.Event()
            t = threading.Thread(target=sample_node_metrics, args=(snapshots, stop))
            t.start()

            start = time.time()
            response, req_b, resp_b = invoke_controller(q, PDF_FILE)
            latency = time.time() - start

            stop.set()
            t.join()

            # Calcola metriche per nodo
            per_node_usage = {}
            for node, node_snapshots in snapshots.items():
                per_node_usage[node] = {
                    "cpu_percent_top": compute_cpu_top_percent(node_snapshots, latency),
                    "mem_bytes": compute_avg_mem(node_snapshots),
                    "rx_bytes_per_s": compute_network_rates(node_snapshots, latency)[0],
                    "tx_bytes_per_s": compute_network_rates(node_snapshots, latency)[1],
                }

            # Aggrega cluster-level
            cluster_usage = {
                "cpu_percent_top": sum(u["cpu_percent_top"] for u in per_node_usage.values()),
                "mem_bytes": sum(u["mem_bytes"] for u in per_node_usage.values()),
                "rx_bytes_per_s": sum(u["rx_bytes_per_s"] for u in per_node_usage.values()),
                "tx_bytes_per_s": sum(u["tx_bytes_per_s"] for u in per_node_usage.values()),
            }

            # Scrive risultati
            write_result(f, i, q, latency, per_node_usage, cluster_usage)

            # Salva latenza + cluster-level per CSV
            usage_csv = {
                "cluster_cpu_percent_top": cluster_usage["cpu_percent_top"],
                "cluster_mem_bytes": cluster_usage["mem_bytes"],
                "cluster_rx_bytes_per_s": cluster_usage["rx_bytes_per_s"],
                "cluster_tx_bytes_per_s": cluster_usage["tx_bytes_per_s"],
                "request_bytes": req_b,
                "response_bytes": resp_b,
            }
            latencies.append(latency)
            usages.append(usage_csv)

    save_latencies_csv(latencies, usages)
    print("✅ Experiment completed")

if __name__ == "__main__":
    main()
