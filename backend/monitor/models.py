from django.db import models


class UserSession(models.Model):
    session_id = models.CharField(max_length=128, unique=True, db_index=True)
    browser = models.CharField(max_length=64, default='Chrome')
    browser_version = models.CharField(max_length=64, blank=True, default='')
    os = models.CharField(max_length=64, default='Linux')
    device_type = models.CharField(max_length=64, default='Desktop')
    user_agent = models.TextField(blank=True, default='')
    ip_address = models.CharField(max_length=64, blank=True, default='127.0.0.1')
    created_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.session_id} ({self.browser} on {self.os})"


class PerformanceMetric(models.Model):
    session = models.ForeignKey(UserSession, related_name='performance_metrics', on_delete=models.CASCADE)
    url = models.CharField(max_length=512, default='/')
    page_load_time = models.FloatField(default=0.0)  # ms
    fcp = models.FloatField(default=0.0)             # First Contentful Paint ms
    dom_ready_time = models.FloatField(default=0.0)  # ms
    ttfb = models.FloatField(default=0.0)            # Time to First Byte ms
    lcp = models.FloatField(default=0.0)             # Largest Contentful Paint ms
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ThreadMetric(models.Model):
    session = models.ForeignKey(UserSession, related_name='thread_metrics', on_delete=models.CASCADE)
    metric_type = models.CharField(max_length=32, default='thread_block')  # 'thread_block' | 'long_task'
    blocked_time = models.FloatField(default=0.0)                          # ms
    freeze_duration = models.FloatField(default=0.0)                       # ms
    freeze_count = models.IntegerField(default=1)
    task_impact = models.CharField(max_length=64, default='High')          # High, Medium, Low
    details = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class WorkerThreadMetric(models.Model):
    session = models.ForeignKey(UserSession, related_name='worker_metrics', on_delete=models.CASCADE)
    thread_name = models.CharField(max_length=128)
    task_type = models.CharField(max_length=128, default='computation')
    execution_time = models.FloatField(default=0.0)  # ms
    status = models.CharField(max_length=32, default='completed')  # running, completed, error
    queue_time = models.FloatField(default=0.0)      # ms
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class MemoryMetric(models.Model):
    session = models.ForeignKey(UserSession, related_name='memory_metrics', on_delete=models.CASCADE)
    total_js_heap_size = models.FloatField(default=0.0)  # MB
    used_js_heap_size = models.FloatField(default=0.0)   # MB
    js_heap_size_limit = models.FloatField(default=0.0)  # MB
    growth_rate = models.FloatField(default=0.0)         # MB delta
    potential_leak = models.BooleanField(default=False)
    leak_severity = models.CharField(max_length=32, default='None')  # None, Low, Medium, High
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class NetworkMetric(models.Model):
    session = models.ForeignKey(UserSession, related_name='network_metrics', on_delete=models.CASCADE)
    url = models.CharField(max_length=512)
    method = models.CharField(max_length=16, default='GET')
    status_code = models.IntegerField(default=200)
    request_time = models.FloatField(default=0.0)
    response_time = models.FloatField(default=0.0)
    duration = models.FloatField(default=0.0)            # ms
    is_error = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ErrorLog(models.Model):
    session = models.ForeignKey(UserSession, related_name='error_logs', on_delete=models.CASCADE)
    error_type = models.CharField(max_length=64, default='JavaScript Error')
    message = models.TextField()
    stack_trace = models.TextField(blank=True, default='')
    url = models.CharField(max_length=512, blank=True, default='')
    browser = models.CharField(max_length=64, blank=True, default='')
    line_number = models.IntegerField(null=True, blank=True)
    col_number = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class UserActivityLog(models.Model):
    session = models.ForeignKey(UserSession, related_name='activity_logs', on_delete=models.CASCADE)
    event_type = models.CharField(max_length=32)  # 'click', 'move', 'scroll', 'dead_click'
    x = models.FloatField(default=0.0)            # percentage (0-100)
    y = models.FloatField(default=0.0)            # percentage (0-100)
    target_element = models.CharField(max_length=128, blank=True, default='')
    target_text = models.CharField(max_length=256, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
