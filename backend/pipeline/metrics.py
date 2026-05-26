from prometheus_client import Counter, Gauge, Histogram

# Gauges: current counts by status
videos_by_status = Gauge(
    "shorts_factory_videos_by_status",
    "Number of videos in each status",
    ["status"],
)

# Histograms: duration of each pipeline step in seconds
pipeline_step_duration = Histogram(
    "shorts_factory_pipeline_step_duration_seconds",
    "Duration of each pipeline step",
    ["step"],
    buckets=[1, 5, 15, 30, 60, 120, 300, 600],
)

# Counters: accumulated cost per step
pipeline_step_cost = Counter(
    "shorts_factory_pipeline_step_cost_usd_total",
    "Accumulated API cost per pipeline step in USD",
    ["step"],
)

# Counter: total videos completed / failed
videos_completed = Counter("shorts_factory_videos_completed_total", "Total completed videos")
videos_failed = Counter("shorts_factory_videos_failed_total", "Total failed videos")
