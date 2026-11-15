"""Step 3 risk model configuration.

The canonical rules live in health_data.py (parsed from the monitoring
spec); this module re-exports them under the name assessmentEngine.py
imports so the scoring module stays decoupled from the data file layout.
"""

from health_data import RISK_MODELS

__all__ = ["RISK_MODELS"]
