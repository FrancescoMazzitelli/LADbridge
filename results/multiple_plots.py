import pandas as pd
import plotly.graph_objects as go
from statistics import mean
import kaleido
kaleido.get_chrome_sync()
# ================= CONFIG =================
LATENCY_FILES = {
    #"2 VMs": "dist-2/baseline/latencies.csv",
    #"4 VMs": "dist-4/baseline/latencies.csv",
    "8 VMs": "dist-8/delayed/latencies.csv",
    "Centralized": "master-llm/delayed/latencies.csv"
}
SCATTER_OUT = "latency_scatter_combined.pdf"
BOXPLOT_OUT = "latency_boxplot_combined.pdf"
BUBBLE_OUT = "latency_bubbles_combined.pdf"
BAR_OUT = "latency_bars_combined.pdf"
# ==========================================

def load_latencies(csv_path):
    df = pd.read_csv(csv_path)
    return df["latency"].tolist()

def plot_scatter_multi(latency_dict):
    fig = go.Figure()
    for i, (label, latencies) in enumerate(latency_dict.items()):
        x_vals = list(range(1, len(latencies)+1))
        color = f"rgba({50*i+50},100,{255-50*i},0.6)"
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=latencies,
            mode="markers",
            marker=dict(size=8, color=color),
            line=dict(color=color),
            name=label
        ))
    fig.update_layout(
        xaxis_title="Question index",
        yaxis_title="Latency (seconds)",
        template="plotly_white",
        font=dict(size=18),
        legend=dict(title="Legend")
    )
    fig.write_image(SCATTER_OUT)
    print(f"📊 Scatter plot saved to {SCATTER_OUT}")

def plot_boxplot_multi(latency_dict):
    fig = go.Figure()
    labels = list(latency_dict.keys())
    
    for i, (label, latencies) in enumerate(latency_dict.items()):
        avg_latency = mean(latencies)
        color = f"rgba({50*i+50},100,{255-50*i},0.6)"
        
        # Box plot with explicit x position
        fig.add_trace(go.Box(
            y=latencies,
            boxmean=False,
            name=label,
            marker_color=color,
            line=dict(width=1.5),
            x=[label] * len(latencies),  # Explicitly assign x to categorical position
            showlegend=False
        ))
        
        # Mean line inside the box (green)
        fig.add_shape(
            type="line",
            x0=i - 0.4,
            x1=i + 0.4,
            y0=avg_latency,
            y1=avg_latency,
            line=dict(color="lime", width=2),
            xref="x",
            yref="y"
        )
        
        # Annotation with mean value below x-axis
        fig.add_annotation(
            x=label,
            y=min(latencies) - (max(latencies) - min(latencies)) * 0.15,
            text=f"{avg_latency:.3f} s",
            showarrow=False,
            font=dict(color="black", size=18),
            align="center",
            bgcolor="rgba(200,200,200,0.5)",
            bordercolor="black",
            borderwidth=1
        )
    
    fig.update_layout(
        yaxis_title="Latency (seconds)",
        template="plotly_white",
        font=dict(size=18),
        margin=dict(b=120),
        showlegend=False,
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=labels
        )
    )
    fig.write_image(BOXPLOT_OUT)
    print(f"📦 Boxplot saved to {BOXPLOT_OUT}")

def plot_bubble_chart(latency_dict):
    fig = go.Figure()

    for i, (label, latencies) in enumerate(latency_dict.items()):
        x_vals = list(range(1, len(latencies) + 1))
        color = f"rgba({50*i+50},100,{255-50*i},0.6)"
        
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=latencies,
            mode="markers",
            marker=dict(size=10, color=color, line=dict(width=0.5, color="black")),
            name=label
        ))

    fig.update_layout(
        xaxis_title="Question index",
        yaxis_title="Latency (seconds)",
        template="plotly_white",
        font=dict(size=18),
        legend=dict(title="Legend")
    )

    fig.write_image(BUBBLE_OUT)
    print(f"🫧 Bubble chart saved to {BUBBLE_OUT}")

def plot_bar_chart(latency_dict):
    import numpy as np
    labels = list(latency_dict.keys())
    max_len = max(len(v) for v in latency_dict.values())
    x_vals = np.arange(1, max_len + 1)

    sorted_per_response = []
    for idx in range(max_len):
        response_vals = []
        for label in labels:
            if idx < len(latency_dict[label]):
                response_vals.append((label, latency_dict[label][idx]))
        response_vals.sort(key=lambda x: x[1], reverse=True)
        sorted_per_response.append(response_vals)

    series_dict = {label: [] for label in labels}
    for idx in range(max_len):
        for order, (label, value) in enumerate(sorted_per_response[idx]):
            series_dict[label].append(value)

    fig = go.Figure()

    median_values = {label: np.median(latency_dict[label]) for label in labels}
    sorted_labels = sorted(labels, key=lambda l: median_values[l], reverse=True)

    palette = [
        "rgba(31, 119, 180, 0.7)",   # blu
        "rgba(255, 127, 14, 0.7)",   # arancione
        "rgba(44, 160, 44, 0.7)",    # verde
        "rgba(214, 39, 40, 0.7)"     # rosso
    ]

    for i, label in enumerate(sorted_labels):
        color = palette[i % len(palette)]
        fig.add_trace(go.Bar(
            x=x_vals[:len(series_dict[label])],
            y=series_dict[label],
            name=label,
            marker_color=color
        ))

    fig.update_layout(
        xaxis_title="Response index",
        yaxis_title="Latency (seconds)",
        template="plotly_white",
        font=dict(size=18),
        barmode="overlay",   # ⬅️ barre sovrapposte
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="center",
            x=0.5,
            title=""
        ),
        margin=dict(b=120)
    )

    fig.write_image(BAR_OUT)
    print(f"📊 Bar chart saved to {BAR_OUT}")


def main():
    latency_dict = {label: load_latencies(path) for label, path in LATENCY_FILES.items()}
    #plot_scatter_multi(latency_dict)
    plot_boxplot_multi(latency_dict)
    #plot_bubble_chart(latency_dict)
    plot_bar_chart(latency_dict)
    print("\n✅ Combined plots generated successfully")

if __name__ == "__main__":
    main()