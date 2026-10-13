"""
Machine Learning Risk Prediction Engine for Browser Telemetry.
Uses Scikit-Learn to evaluate session metrics and predict:
- Crash Risk (High/Medium/Low)
- Main Thread Freeze Probability
- Memory Leakage Anomalies
- Slow Page Degradation
"""

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier


class BrowserRiskPredictor:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BrowserRiskPredictor, cls).__new__(cls)
            cls._instance._initialize_model()
        return cls._instance

    def _initialize_model(self):
        """
        Train a synthetic baseline model with realistic browser stress distributions.
        Features vector:
        [
          0: avg_page_load_ms,
          1: max_thread_block_ms,
          2: long_tasks_count,
          3: used_heap_mb,
          4: heap_growth_rate_mb,
          5: api_error_rate_pct,
          6: unhandled_error_count,
          7: worker_count
        ]
        """
        np.random.seed(42)
        n_samples = 600

        # Class 0: Low Risk (Healthy browser session)
        healthy_features = np.column_stack([
            np.random.normal(900, 200, n_samples // 3),    # load time ~900ms
            np.random.normal(30, 15, n_samples // 3),      # thread block ~30ms
            np.random.poisson(1, n_samples // 3),          # ~1 long task
            np.random.normal(45, 10, n_samples // 3),      # heap ~45MB
            np.random.normal(0.5, 0.5, n_samples // 3),    # heap growth ~0.5MB
            np.random.uniform(0, 5, n_samples // 3),       # api err 0-5%
            np.random.poisson(0.2, n_samples // 3),        # ~0 errors
            np.random.randint(1, 4, n_samples // 3)        # 1-3 workers
        ])
        healthy_labels = np.zeros(n_samples // 3)

        # Class 1: Medium Risk (Degraded responsiveness)
        medium_features = np.column_stack([
            np.random.normal(2500, 400, n_samples // 3),   # load time ~2.5s
            np.random.normal(180, 50, n_samples // 3),     # thread block ~180ms
            np.random.poisson(6, n_samples // 3),          # ~6 long tasks
            np.random.normal(120, 25, n_samples // 3),     # heap ~120MB
            np.random.normal(8.0, 3.0, n_samples // 3),    # heap growth ~8MB
            np.random.uniform(5, 20, n_samples // 3),      # api err 5-20%
            np.random.poisson(2, n_samples // 3),          # ~2 errors
            np.random.randint(0, 3, n_samples // 3)        # 0-2 workers
        ])
        medium_labels = np.ones(n_samples // 3)

        # Class 2: High Risk (Imminent freeze/crash/out of memory)
        high_features = np.column_stack([
            np.random.normal(5500, 1200, n_samples // 3),  # load time ~5.5s
            np.random.normal(650, 180, n_samples // 3),    # thread block ~650ms+
            np.random.poisson(18, n_samples // 3),         # ~18 long tasks
            np.random.normal(280, 50, n_samples // 3),     # heap ~280MB+
            np.random.normal(28.0, 8.0, n_samples // 3),   # rapid heap leak
            np.random.uniform(25, 75, n_samples // 3),     # api err 25-75%
            np.random.poisson(8, n_samples // 3),          # ~8+ errors
            np.random.randint(0, 2, n_samples // 3)        # 0 workers (overloaded main thread)
        ])
        high_labels = np.full(n_samples // 3, 2)

        X = np.vstack([healthy_features, medium_features, high_features])
        X = np.clip(X, a_min=0, a_max=None)
        y = np.concatenate([healthy_labels, medium_labels, high_labels])

        self.classifier = RandomForestClassifier(n_estimators=60, max_depth=6, random_state=42)
        self.classifier.fit(X, y)
        self.feature_names = [
            "Page Load Time",
            "Thread Block Duration",
            "Long Tasks Count",
            "Used JS Heap",
            "Heap Growth Rate",
            "API Failure Rate",
            "Uncaught Error Count",
            "Worker Threads"
        ]

    def predict(self, metrics: dict) -> dict:
        """
        Evaluate session telemetry and generate risk forecast.
        metrics keys:
        - page_load_time (float)
        - max_thread_block (float)
        - long_task_count (int)
        - used_heap (float)
        - heap_growth (float)
        - api_error_rate (float)
        - error_count (int)
        - worker_count (int)
        """
        vector = np.array([[
            max(0.0, float(metrics.get("page_load_time", 1200.0))),
            max(0.0, float(metrics.get("max_thread_block", 25.0))),
            max(0, int(metrics.get("long_task_count", 0))),
            max(0.0, float(metrics.get("used_heap", 35.0))),
            max(0.0, float(metrics.get("heap_growth", 0.0))),
            max(0.0, min(100.0, float(metrics.get("api_error_rate", 0.0)))),
            max(0, int(metrics.get("error_count", 0))),
            max(0, int(metrics.get("worker_count", 1))),
        ]])

        probs = self.classifier.predict_proba(vector)[0]
        # Classes: 0 -> Low, 1 -> Medium, 2 -> High
        p_low = float(probs[0])
        p_med = float(probs[1]) if len(probs) > 1 else 0.0
        p_high = float(probs[2]) if len(probs) > 2 else 0.0

        if p_high >= 0.40 or (p_high + p_med) > 0.70:
            risk_level = "High Risk"
            badge_color = "red"
        elif p_med >= 0.35 or p_high >= 0.20:
            risk_level = "Medium Risk"
            badge_color = "amber"
        else:
            risk_level = "Low Risk"
            badge_color = "green"

        crash_prob_pct = round((p_high * 0.7 + p_med * 0.25) * 100, 1)

        # Freeze probability based on thread blocks & long tasks
        block_val = float(metrics.get("max_thread_block", 0))
        long_tasks = int(metrics.get("long_task_count", 0))
        freeze_score = min(100.0, (block_val / 6.0) + (long_tasks * 4.5))
        freeze_prob_pct = round(freeze_score, 1)

        # Memory Leak warning
        heap_growth = float(metrics.get("heap_growth", 0))
        used_heap = float(metrics.get("used_heap", 0))
        leak_warning = heap_growth > 12.0 or (used_heap > 200.0 and heap_growth > 4.0)

        # Page performance classification
        load_time = float(metrics.get("page_load_time", 0))
        if load_time > 4000:
            page_class = "Critical Bottleneck"
        elif load_time > 2000:
            page_class = "Slow Page Warning"
        elif load_time > 1000:
            page_class = "Moderate Latency"
        else:
            page_class = "Optimal Performance"

        # Actionable recommendations
        recommendations = []
        if block_val > 150:
            recommendations.append(f"Main thread frozen for {int(block_val)}ms. Offload synchronous JSON/array parsing to Web Workers.")
        if leak_warning:
            recommendations.append(f"Heap grew by {round(heap_growth, 1)}MB. Check retainers, lingering event handlers, and cache arrays.")
        if float(metrics.get("api_error_rate", 0)) > 15:
            recommendations.append("Elevated network error rate (>15%). Review API gateway health and circuit-breaker thresholds.")
        if int(metrics.get("error_count", 0)) > 3:
            recommendations.append(f"{metrics.get('error_count')} unhandled runtime errors caught. Inspect Error Analysis tab stack traces.")
        if not recommendations:
            recommendations.append("Browser execution is stable within sub-50ms main-thread budgets.")

        # Top risk factor calculation
        importances = self.classifier.feature_importances_
        weighted_factors = vector[0] * importances
        top_factor_idx = int(np.argmax(weighted_factors))
        top_risk_factor = self.feature_names[top_factor_idx]

        return {
            "risk_level": risk_level,
            "badge_color": badge_color,
            "crash_probability": crash_prob_pct,
            "freeze_probability": freeze_prob_pct,
            "memory_leak_warning": leak_warning,
            "heap_growth_delta_mb": round(heap_growth, 2),
            "page_classification": page_class,
            "top_risk_factor": top_risk_factor,
            "recommendations": recommendations,
            "confidence_score": round(max(p_low, p_med, p_high) * 100, 1),
            "probabilities": {
                "low": round(p_low * 100, 1),
                "medium": round(p_med * 100, 1),
                "high": round(p_high * 100, 1)
            }
        }


# Singleton accessor
ai_predictor = BrowserRiskPredictor()
