import pandas as pd
import numpy as np
import plotly.graph_objects as go
from statistics import mean
import kaleido
kaleido.get_chrome_sync()
# ================= CONFIG =================
LATENCY_FILES = {
    #"2 VMs": "dist-2/baseline/latencies.csv",
    #"4 VMs": "dist-4/baseline/latencies.csv",
    "8 VMs": "dist-8/baseline/latencies.csv",
    #"Centralized": "master-llm/delayed/latencies.csv"
}
SCATTER_OUT = "latency_scatter_combined.pdf"
BOXPLOT_OUT = "latency_boxplot_combined.pdf"
BUBBLE_OUT = "latency_bubbles_combined.pdf"
BAR_OUT = "latency_bars_combined.pdf"
# ==========================================

def load_latencies(csv_path):
    df = pd.read_csv(csv_path)
    return df["latency_s"].tolist()

def calculate_qos_metrics(latencies, label):
    lat = np.array(latencies)
    n = len(lat)
    total_time = np.sum(lat)
    avg_time = np.mean(lat)
    std_time = np.std(lat)
    p50 = np.percentile(lat, 50)
    p95 = np.percentile(lat, 95)
    p99 = np.percentile(lat, 99)
    min_time = np.min(lat)
    max_time = np.max(lat)
    outliers_p95 = np.sum(lat > p95) / n * 100
    throughput = n / total_time if total_time > 0 else float('inf')

    print(f"\n📊 QoS Metrics for {label}:")
    print(f"  Total workflow time: {total_time:.3f} s")
    print(f"  Average step time: {avg_time:.3f} s")
    print(f"  Std deviation: {std_time:.3f} s")
    print(f"  Min latency: {min_time:.3f} s")
    print(f"  Max latency: {max_time:.3f} s")
    print(f"  p50 latency: {p50:.3f} s")
    print(f"  p95 latency: {p95:.3f} s")
    print(f"  p99 latency: {p99:.3f} s")
    print(f"  % steps above p95: {outliers_p95:.2f}%")
    print(f"  Throughput: {throughput:.3f} workflows/sec")

def plot_latency_curves(latency_dict, log_y=True):
    fig = go.Figure()

    for i, (label, latencies) in enumerate(latency_dict.items()):
        lat = np.array(latencies)
        x = np.arange(1, len(lat) + 1)

        # cumulative statistics
        median = np.array([np.median(lat[:k]) for k in x])
        q25 = np.array([np.percentile(lat[:k], 25) for k in x])
        q75 = np.array([np.percentile(lat[:k], 75) for k in x])
        p95 = np.array([np.percentile(lat[:k], 95) for k in x])
        minv   = np.array([np.min(lat[:k]) for k in x])
        maxv   = np.array([np.max(lat[:k]) for k in x])

        base_color = f"rgb({50*i+60},100,{255-40*i})"
        band_color = f"rgba({50*i+60},100,{255-40*i},0.15)"

        legend_group = label  # one group per system

        # IQR band (hidden from legend)
        fig.add_trace(go.Scatter(
            x=x,
            y=q25,
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
            legendgroup=legend_group
        ))

        fig.add_trace(go.Scatter(
            x=x,
            y=q75,
            fill="tonexty",
            fillcolor=band_color,
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
            legendgroup=legend_group
        ))

        # Median (main legend entry)
        fig.add_trace(go.Scatter(
            x=x,
            y=median,
            mode="lines",
            line=dict(color=base_color, width=3),
            name=label,
            legendgroup=legend_group,
            showlegend=True
        ))

        # 95th percentile (grouped, no legend entry)
        fig.add_trace(go.Scatter(
            x=x,
            y=p95,
            mode="lines",
            line=dict(color=base_color, width=1.5, dash="dash"),
            showlegend=False,
            legendgroup=legend_group
        ))

        # Min
        fig.add_trace(go.Scatter(
            x=x,
            y=minv,
            mode="lines",
            line=dict(color=base_color, width=1, dash="dot"),
            showlegend=False,
            legendgroup=legend_group,
            hoverinfo="skip"
        ))

        # Max
        fig.add_trace(go.Scatter(
            x=x,
            y=maxv,
            mode="lines",
            line=dict(color=base_color, width=1, dash="dot"),
            showlegend=False,
            legendgroup=legend_group,
            hoverinfo="skip"
        ))

    fig.update_layout(
        xaxis_title="Question index",
        yaxis_title="Latency (seconds)",
        template="simple_white",
        font=dict(size=18),

        # LEGEND SETTINGS
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="center",
            x=0.5,
            title=None
        ),

        plot_bgcolor="white",
        paper_bgcolor="white",

        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.05)"
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.05)",
            type="log" if log_y else "linear"
        )
    )

    fig.write_image(SCATTER_OUT)
    print(f"📈 Latency curves saved to {SCATTER_OUT}")


def plot_two_latency_curves(latency_dict, log_y=True):
    fig = go.Figure()

    colors = [
        ("rgb(31,119,180)", "rgba(31,119,180,0.15)"),  # blue
        ("rgb(214,39,40)",  "rgba(214,39,40,0.15)")   # red
    ]

    for i, (label, latencies) in enumerate(latency_dict.items()):
        lat = np.array(latencies)
        x = np.arange(1, len(lat) + 1)

        # cumulative statistics
        median = np.array([np.median(lat[:k]) for k in x])
        q25    = np.array([np.percentile(lat[:k], 25) for k in x])
        q75    = np.array([np.percentile(lat[:k], 75) for k in x])
        p95    = np.array([np.percentile(lat[:k], 95) for k in x])
        minv   = np.array([np.min(lat[:k]) for k in x])
        maxv   = np.array([np.max(lat[:k]) for k in x])

        base_color, band_color = colors[i]
        legend_group = label

        # IQR band
        fig.add_trace(go.Scatter(
            x=x,
            y=q25,
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
            legendgroup=legend_group
        ))

        fig.add_trace(go.Scatter(
            x=x,
            y=q75,
            fill="tonexty",
            fillcolor=band_color,
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
            legendgroup=legend_group
        ))

        # Median
        fig.add_trace(go.Scatter(
            x=x,
            y=median,
            mode="lines",
            line=dict(color=base_color, width=3),
            name=label,
            legendgroup=legend_group,
            showlegend=True
        ))

        # 95th percentile
        fig.add_trace(go.Scatter(
            x=x,
            y=p95,
            mode="lines",
            line=dict(color=base_color, width=1.5, dash="dash"),
            showlegend=False,
            legendgroup=legend_group
        ))

        # Min
        fig.add_trace(go.Scatter(
            x=x,
            y=minv,
            mode="lines",
            line=dict(color=base_color, width=1, dash="dot"),
            showlegend=False,
            legendgroup=legend_group,
            hoverinfo="skip"
        ))

        # Max
        fig.add_trace(go.Scatter(
            x=x,
            y=maxv,
            mode="lines",
            line=dict(color=base_color, width=1, dash="dot"),
            showlegend=False,
            legendgroup=legend_group,
            hoverinfo="skip"
        ))

    fig.update_layout(
        xaxis_title="Question index",
        yaxis_title="Latency (seconds)",
        template="simple_white",
        font=dict(size=18),

        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="center",
            x=0.5,
            title=None
        ),

        xaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.05)",
            type="log" if log_y else "linear"
        )
    )

    fig.write_image(SCATTER_OUT)
    print(f"📈 Latency curves saved to {SCATTER_OUT}")


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
    
    for label, latencies in latency_dict.items():
        calculate_qos_metrics(latencies, label)
    
    #plot_latency_curves(latency_dict)
    #plot_two_latency_curves(latency_dict)
    #plot_boxplot_multi(latency_dict)
    #plot_bubble_chart(latency_dict)
    #plot_bar_chart(latency_dict)
    print("\n✅ Combined plots generated successfully")

if __name__ == "__main__":
    main()