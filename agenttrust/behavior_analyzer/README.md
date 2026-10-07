# Behavior Analyzer

A high-end, production-grade Python module for detecting anomalous behavior in multi-agent AI systems.

## Features
- **6 specialized detectors** (Statistical, ML, Temporal, Frequency, Parameter, Delegation)
- **Plugin/Strategy architecture** (`DetectorRegistry`)
- **Welford's online algorithm** for memory-efficient baseline updates
- **Isolation Forest** (scikit-learn) for multi-dimensional anomaly detection
- **Weighted ensemble scoring**
- **Swappable storage backends** (In-Memory, Redis)

## Demo
Run the interactive demo to simulate normal and anomalous agent behavior:
```bash
python -m behavior_analyzer.demo
```

## Testing
```bash
pytest behavior_analyzer/tests/ -v
```
