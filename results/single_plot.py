import pandas as pd
import plotly.graph_objects as go
from statistics import mean
import kaleido

kaleido.get_chrome_sync()

# ================= CONFIG =================
LATENCY_CSV = "latencies.csv"
SCATTER_OUT = "latency_scatter.pdf"
BOXPLOT_OUT = "latency_boxplot.pdf"
# ==========================================


def load_latencies(csv_path):
    df = pd.read_csv(csv_path)
    return df["latency"].tolist()


def format_x_labels(indices):
    """
    Etichette verticali con cifre ravvicinate
    """
    labels = []
    for i in indices:
        s = str(i)
        if len(s) > 1:
            s = "".join(
                f"<span style='line-height:0.8'>{c}</span><br>"
                for c in s
            )[:-4]
        labels.append(s)
    return labels


def plot_scatter(latencies):
    x_vals = list(range(1, len(latencies) + 1))
    x_labels = format_x_labels(x_vals)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x_vals,
        y=latencies,
        mode="markers+lines",
        marker=dict(size=8),
        name="Plan generation latency"
    ))

    fig.update_layout(
        xaxis_title="Question index",
        yaxis_title="Latency (seconds)",
        xaxis=dict(
            tickmode="array",
            tickvals=x_vals,
            ticktext=x_labels,
            tickangle=0
        ),
        template="plotly_white",
        font=dict(size=18)
    )

    fig.write_image(SCATTER_OUT)
    print(f"📊 Scatter plot saved to {SCATTER_OUT}")


def plot_boxplot(latencies):
    avg_latency = mean(latencies)

    fig = go.Figure()
    fig.add_trace(go.Box(
        y=latencies,
        boxmean=False,
        name="Latency distribution"
    ))

    fig.add_hline(
        y=avg_latency,
        line_dash="dash",
        line_color="black"
    )

    fig.add_annotation(
        text=f"Mean = {avg_latency:.3f} s",
        x=1.02,
        y=avg_latency,
        xref="paper",
        yref="y",
        showarrow=False,
        font=dict(size=18),
        align="left",
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor="black",
        borderwidth=1
    )

    fig.update_layout(
        yaxis_title="Latency (seconds)",
        template="plotly_white",
        margin=dict(r=120),
        font=dict(size=18)
    )

    fig.write_image(BOXPLOT_OUT)
    print(f"📦 Boxplot saved to {BOXPLOT_OUT}")


def main():
    latencies = load_latencies(LATENCY_CSV)
    plot_scatter(latencies)
    plot_boxplot(latencies)
    print("\n✅ Plots generated successfully")


if __name__ == "__main__":
    main()
