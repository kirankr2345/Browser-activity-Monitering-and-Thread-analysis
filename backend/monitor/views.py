import json
import random
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count, Max, Q
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import (
    UserSession,
    PerformanceMetric,
    ThreadMetric,
    WorkerThreadMetric,
    MemoryMetric,
    NetworkMetric,
    ErrorLog,
    UserActivityLog
)
from .serializers import (
    UserSessionSerializer,
    PerformanceMetricSerializer,
    ThreadMetricSerializer,
    WorkerThreadMetricSerializer,
    MemoryMetricSerializer,
    NetworkMetricSerializer,
    ErrorLogSerializer,
    UserActivityLogSerializer
)
from .ml_predictor import ai_predictor


def broadcast_event(event_type, payload):
    """Broadcast an event via Channels group to all live WebSocket listeners."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'telemetry_stream',
                {
                    'type': 'telemetry_update',
                    'data': {
                        'event_type': event_type,
                        'payload': payload,
                        'timestamp': timezone.now().isoformat()
                    }
                }
            )
    except Exception as e:
        # Best effort broadcast
        pass


def get_or_create_session(data):
    session_id = data.get('session_id') or f"sess_{random.randint(100000, 999999)}"
    session, created = UserSession.objects.get_or_create(
        session_id=session_id,
        defaults={
            'browser': data.get('browser', 'Chrome'),
            'browser_version': data.get('browser_version', '122.0'),
            'os': data.get('os', 'Linux'),
            'device_type': data.get('device_type', 'Desktop'),
            'user_agent': data.get('user_agent', ''),
            'ip_address': data.get('ip_address', '127.0.0.1')
        }
    )
    if not created:
        session.last_active_at = timezone.now()
        session.save(update_fields=['last_active_at'])
    return session


@api_view(['POST'])
def start_session_view(request):
    session = get_or_create_session(request.data)
    broadcast_event('session_started', {
        'session_id': session.session_id,
        'browser': session.browser,
        'os': session.os
    })
    return Response(UserSessionSerializer(session).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def performance_metric_view(request):
    session = get_or_create_session(request.data)
    metric = PerformanceMetric.objects.create(
        session=session,
        url=request.data.get('url', '/'),
        page_load_time=float(request.data.get('load_time', request.data.get('page_load_time', 0.0))),
        fcp=float(request.data.get('fcp', 0.0)),
        dom_ready_time=float(request.data.get('dom_ready_time', 0.0)),
        ttfb=float(request.data.get('ttfb', 0.0)),
        lcp=float(request.data.get('lcp', 0.0))
    )
    payload = PerformanceMetricSerializer(metric).data
    broadcast_event('performance_metric', payload)
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def thread_analysis_view(request):
    session = get_or_create_session(request.data)
    blocked_time = float(request.data.get('blocked_time', request.data.get('duration', 0.0)))
    freeze_count = int(request.data.get('freeze_count', 1))
    impact = 'High' if blocked_time > 200 else ('Medium' if blocked_time > 100 else 'Low')
    metric = ThreadMetric.objects.create(
        session=session,
        metric_type=request.data.get('metric_type', 'thread_block'),
        blocked_time=blocked_time,
        freeze_duration=float(request.data.get('freeze_duration', blocked_time)),
        freeze_count=freeze_count,
        task_impact=request.data.get('task_impact', impact),
        details=str(request.data.get('details', ''))
    )
    payload = ThreadMetricSerializer(metric).data
    broadcast_event('thread_block', payload)
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def worker_thread_view(request):
    session = get_or_create_session(request.data)
    metric = WorkerThreadMetric.objects.create(
        session=session,
        thread_name=request.data.get('thread_name', 'Worker-1'),
        task_type=request.data.get('task_type', 'Heavy Computation'),
        execution_time=float(request.data.get('execution_time', 0.0)),
        status=request.data.get('status', 'completed'),
        queue_time=float(request.data.get('queue_time', 0.0))
    )
    payload = WorkerThreadMetricSerializer(metric).data
    broadcast_event('worker_task', payload)
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def memory_metric_view(request):
    session = get_or_create_session(request.data)
    total_heap = float(request.data.get('total_js_heap_size', request.data.get('total_memory', 0.0)))
    used_heap = float(request.data.get('used_js_heap_size', request.data.get('used_memory', 0.0)))
    limit = float(request.data.get('js_heap_size_limit', 0.0))
    growth_rate = float(request.data.get('growth_rate', request.data.get('memory_growth', 0.0)))
    potential_leak = bool(request.data.get('potential_leak', growth_rate > 15.0 or (used_heap > 250.0 and growth_rate > 5.0)))
    severity = 'High' if growth_rate > 20.0 else ('Medium' if growth_rate > 10.0 else 'Low')

    metric = MemoryMetric.objects.create(
        session=session,
        total_js_heap_size=total_heap,
        used_js_heap_size=used_heap,
        js_heap_size_limit=limit,
        growth_rate=growth_rate,
        potential_leak=potential_leak,
        leak_severity=severity if potential_leak else 'None'
    )
    payload = MemoryMetricSerializer(metric).data
    broadcast_event('memory_metric', payload)
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def network_metric_view(request):
    session = get_or_create_session(request.data)
    status_code = int(request.data.get('status_code', 200))
    duration = float(request.data.get('duration', request.data.get('response_time', 0.0)))
    is_error = bool(request.data.get('is_error', status_code >= 400))

    metric = NetworkMetric.objects.create(
        session=session,
        url=request.data.get('url', '/api/test'),
        method=request.data.get('method', 'GET'),
        status_code=status_code,
        request_time=float(request.data.get('request_time', 0.0)),
        response_time=float(request.data.get('response_time', duration)),
        duration=duration,
        is_error=is_error
    )
    payload = NetworkMetricSerializer(metric).data
    broadcast_event('network_metric', payload)
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def error_log_view(request):
    session = get_or_create_session(request.data)
    error = ErrorLog.objects.create(
        session=session,
        error_type=request.data.get('error_type', 'JavaScript Error'),
        message=str(request.data.get('message', 'Unknown runtime exception')),
        stack_trace=str(request.data.get('stack_trace', '')),
        url=request.data.get('url', ''),
        browser=request.data.get('browser', session.browser),
        line_number=request.data.get('line_number'),
        col_number=request.data.get('col_number')
    )
    payload = ErrorLogSerializer(error).data
    broadcast_event('error_logged', payload)
    return Response(payload, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def user_activity_view(request):
    session = get_or_create_session(request.data)
    events = request.data.get('events', [])
    created_items = []
    if isinstance(events, list) and events:
        for ev in events[:50]:  # batch limit
            log = UserActivityLog.objects.create(
                session=session,
                event_type=ev.get('event_type', 'click'),
                x=float(ev.get('x', 0.0)),
                y=float(ev.get('y', 0.0)),
                target_element=ev.get('target_element', ''),
                target_text=ev.get('target_text', '')
            )
            created_items.append(log)
    elif 'event_type' in request.data:
        log = UserActivityLog.objects.create(
            session=session,
            event_type=request.data.get('event_type', 'click'),
            x=float(request.data.get('x', 0.0)),
            y=float(request.data.get('y', 0.0)),
            target_element=request.data.get('target_element', ''),
            target_text=request.data.get('target_text', '')
        )
        created_items.append(log)

    return Response({'recorded': len(created_items)}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def batch_telemetry_view(request):
    """Batch ingestion endpoint for SDK flushes."""
    session = get_or_create_session(request.data)
    data = request.data
    counts = {'perf': 0, 'threads': 0, 'workers': 0, 'memory': 0, 'network': 0, 'errors': 0}

    if 'performance' in data:
        p = data['performance']
        PerformanceMetric.objects.create(
            session=session,
            url=p.get('url', '/'),
            page_load_time=float(p.get('load_time', 0)),
            fcp=float(p.get('fcp', 0)),
            dom_ready_time=float(p.get('dom_ready_time', 0)),
            ttfb=float(p.get('ttfb', 0)),
            lcp=float(p.get('lcp', 0))
        )
        counts['perf'] += 1

    if 'thread_blocks' in data and isinstance(data['thread_blocks'], list):
        for tb in data['thread_blocks']:
            dur = float(tb.get('blocked_time', tb.get('duration', 0)))
            ThreadMetric.objects.create(
                session=session,
                metric_type=tb.get('metric_type', 'thread_block'),
                blocked_time=dur,
                freeze_duration=dur,
                freeze_count=int(tb.get('freeze_count', 1)),
                task_impact='High' if dur > 200 else 'Medium',
                details=str(tb.get('details', ''))
            )
            counts['threads'] += 1

    if 'network' in data and isinstance(data['network'], list):
        for net in data['network']:
            st = int(net.get('status_code', 200))
            dur = float(net.get('duration', 0))
            NetworkMetric.objects.create(
                session=session,
                url=net.get('url', '/'),
                method=net.get('method', 'GET'),
                status_code=st,
                duration=dur,
                is_error=st >= 400
            )
            counts['network'] += 1

    if 'errors' in data and isinstance(data['errors'], list):
        for err in data['errors']:
            ErrorLog.objects.create(
                session=session,
                error_type=err.get('error_type', 'JavaScript Error'),
                message=str(err.get('message', 'Batch logged error')),
                stack_trace=str(err.get('stack_trace', '')),
                browser=session.browser
            )
            counts['errors'] += 1

    broadcast_event('batch_received', {'session_id': session.session_id, 'counts': counts})
    return Response({'status': 'ok', 'processed': counts}, status=status.HTTP_200_OK)


# ---------------- DASHBOARD AGGREGATION VIEWS ----------------

@api_view(['GET'])
def dashboard_overview_view(request):
    total_sessions = UserSession.objects.count()
    perf_agg = PerformanceMetric.objects.aggregate(
        avg_load=Avg('page_load_time'),
        avg_fcp=Avg('fcp'),
        avg_ttfb=Avg('ttfb'),
        avg_lcp=Avg('lcp')
    )
    thread_agg = ThreadMetric.objects.aggregate(
        total_blocks=Count('id'),
        max_freeze=Max('blocked_time'),
        avg_blocked=Avg('blocked_time')
    )
    error_count = ErrorLog.objects.count()
    mem_agg = MemoryMetric.objects.aggregate(
        avg_used=Avg('used_js_heap_size'),
        potential_leaks=Count('id', filter=Q(potential_leak=True))
    )
    net_agg = NetworkMetric.objects.aggregate(
        total_requests=Count('id'),
        failed_requests=Count('id', filter=Q(is_error=True)),
        avg_latency=Avg('duration')
    )

    worker_count = WorkerThreadMetric.objects.count()

    # Recent timeline stream
    recent_errors = list(ErrorLog.objects.values('id', 'error_type', 'message', 'created_at')[:5])
    recent_threads = list(ThreadMetric.objects.values('id', 'metric_type', 'blocked_time', 'task_impact', 'created_at')[:5])
    recent_workers = list(WorkerThreadMetric.objects.values('id', 'thread_name', 'execution_time', 'status', 'created_at')[:5])

    # AI Quick Assessment
    features = {
        'page_load_time': perf_agg['avg_load'] or 1100.0,
        'max_thread_block': thread_agg['max_freeze'] or 20.0,
        'long_task_count': thread_agg['total_blocks'] or 0,
        'used_heap': mem_agg['avg_used'] or 45.0,
        'heap_growth': 1.2,
        'api_error_rate': (net_agg['failed_requests'] / max(1, net_agg['total_requests'])) * 100 if net_agg['total_requests'] else 0.0,
        'error_count': error_count,
        'worker_count': worker_count or 1
    }
    ai_summary = ai_predictor.predict(features)

    return Response({
        'overview': {
            'total_users': total_sessions,
            'avg_load_time': round(perf_agg['avg_load'] or 0, 1),
            'avg_fcp': round(perf_agg['avg_fcp'] or 0, 1),
            'avg_ttfb': round(perf_agg['avg_ttfb'] or 0, 1),
            'avg_lcp': round(perf_agg['avg_lcp'] or 0, 1),
            'thread_blocks_count': thread_agg['total_blocks'] or 0,
            'max_freeze_duration': round(thread_agg['max_freeze'] or 0, 1),
            'avg_thread_block': round(thread_agg['avg_blocked'] or 0, 1),
            'total_errors': error_count,
            'avg_used_heap': round(mem_agg['avg_used'] or 0, 1),
            'potential_leaks': mem_agg['potential_leaks'] or 0,
            'total_api_calls': net_agg['total_requests'] or 0,
            'failed_api_calls': net_agg['failed_requests'] or 0,
            'avg_api_latency': round(net_agg['avg_latency'] or 0, 1),
            'worker_threads_active': worker_count
        },
        'ai_risk_quick': ai_summary,
        'recent_events': {
            'errors': recent_errors,
            'thread_events': recent_threads,
            'worker_tasks': recent_workers
        }
    })


@api_view(['GET'])
def dashboard_threads_view(request):
    blocks = ThreadMetric.objects.order_by('-created_at')[:40]
    workers = WorkerThreadMetric.objects.order_by('-created_at')[:30]

    # Group by impact
    impact_stats = {
        'High': ThreadMetric.objects.filter(task_impact='High').count(),
        'Medium': ThreadMetric.objects.filter(task_impact='Medium').count(),
        'Low': ThreadMetric.objects.filter(task_impact='Low').count()
    }

    # Worker performance stats
    worker_stats = WorkerThreadMetric.objects.aggregate(
        avg_exec=Avg('execution_time'),
        max_exec=Max('execution_time'),
        total_tasks=Count('id')
    )

    return Response({
        'thread_events': ThreadMetricSerializer(blocks, many=True).data,
        'worker_threads': WorkerThreadMetricSerializer(workers, many=True).data,
        'impact_distribution': impact_stats,
        'worker_summary': {
            'avg_execution_ms': round(worker_stats['avg_exec'] or 0, 1),
            'max_execution_ms': round(worker_stats['max_exec'] or 0, 1),
            'total_tasks': worker_stats['total_tasks'] or 0
        }
    })


@api_view(['GET'])
def dashboard_memory_view(request):
    memory_history = MemoryMetric.objects.order_by('created_at')[:50]
    leaks = MemoryMetric.objects.filter(potential_leak=True).order_by('-created_at')[:15]

    latest = MemoryMetric.objects.order_by('-created_at').first()
    latest_data = {
        'used_heap_mb': round(latest.used_js_heap_size, 1) if latest else 42.0,
        'total_heap_mb': round(latest.total_js_heap_size, 1) if latest else 68.0,
        'limit_mb': round(latest.js_heap_size_limit, 1) if latest else 4096.0,
        'growth_rate': round(latest.growth_rate, 2) if latest else 0.4
    }

    return Response({
        'current_memory': latest_data,
        'history': MemoryMetricSerializer(memory_history, many=True).data,
        'potential_leaks': MemoryMetricSerializer(leaks, many=True).data
    })


@api_view(['GET'])
def dashboard_network_view(request):
    recent_calls = NetworkMetric.objects.order_by('-created_at')[:50]
    
    # Status code breakdown
    codes_2xx = NetworkMetric.objects.filter(status_code__gte=200, status_code__lt=300).count()
    codes_3xx = NetworkMetric.objects.filter(status_code__gte=300, status_code__lt=400).count()
    codes_4xx = NetworkMetric.objects.filter(status_code__gte=400, status_code__lt=500).count()
    codes_5xx = NetworkMetric.objects.filter(status_code__gte=500).count()

    # Slowest endpoints
    slowest = list(
        NetworkMetric.objects.values('url', 'method')
        .annotate(avg_duration=Avg('duration'), call_count=Count('id'))
        .order_by('-avg_duration')[:6]
    )

    return Response({
        'recent_calls': NetworkMetricSerializer(recent_calls, many=True).data,
        'status_distribution': {
            '2xx': codes_2xx,
            '3xx': codes_3xx,
            '4xx': codes_4xx,
            '5xx': codes_5xx
        },
        'slowest_endpoints': slowest
    })


@api_view(['GET'])
def dashboard_errors_view(request):
    errors = ErrorLog.objects.order_by('-created_at')[:50]
    
    # Distribution by type
    by_type = list(
        ErrorLog.objects.values('error_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    # Distribution by browser
    by_browser = list(
        ErrorLog.objects.values('browser')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    return Response({
        'errors': ErrorLogSerializer(errors, many=True).data,
        'distribution_by_type': by_type,
        'distribution_by_browser': by_browser
    })


@api_view(['GET'])
def dashboard_ai_predictions_view(request):
    session_id = request.query_params.get('session_id')
    
    if session_id:
        session = UserSession.objects.filter(session_id=session_id).first()
        if session:
            p = session.performance_metrics.aggregate(avg_load=Avg('page_load_time'))
            t = session.thread_metrics.aggregate(max_b=Max('blocked_time'), cnt=Count('id'))
            m = session.memory_metrics.aggregate(used=Avg('used_js_heap_size'), growth=Max('growth_rate'))
            net = session.network_metrics.aggregate(tot=Count('id'), err=Count('id', filter=Q(is_error=True)))
            errs = session.error_logs.count()
            workers = session.worker_metrics.count()
            
            features = {
                'page_load_time': p['avg_load'] or 1200.0,
                'max_thread_block': t['max_b'] or 30.0,
                'long_task_count': t['cnt'] or 0,
                'used_heap': m['used'] or 50.0,
                'heap_growth': m['growth'] or 1.0,
                'api_error_rate': (net['err'] / max(1, net['tot'])) * 100 if net['tot'] else 0.0,
                'error_count': errs,
                'worker_count': workers or 1
            }
            prediction = ai_predictor.predict(features)
            return Response({'session_id': session_id, 'prediction': prediction, 'features': features})

    # Overall system predictive assessment
    perf = PerformanceMetric.objects.aggregate(avg_load=Avg('page_load_time'))
    thread = ThreadMetric.objects.aggregate(max_b=Max('blocked_time'), cnt=Count('id'))
    mem = MemoryMetric.objects.aggregate(used=Avg('used_js_heap_size'), growth=Avg('growth_rate'))
    net = NetworkMetric.objects.aggregate(tot=Count('id'), err=Count('id', filter=Q(is_error=True)))
    err_count = ErrorLog.objects.count()
    workers = WorkerThreadMetric.objects.count()

    features = {
        'page_load_time': perf['avg_load'] or 1250.0,
        'max_thread_block': thread['max_b'] or 45.0,
        'long_task_count': thread['cnt'] or 2,
        'used_heap': mem['used'] or 52.0,
        'heap_growth': mem['growth'] or 2.1,
        'api_error_rate': (net['err'] / max(1, net['tot'])) * 100 if net['tot'] else 3.5,
        'error_count': err_count,
        'worker_count': workers or 2
    }
    prediction = ai_predictor.predict(features)
    return Response({'prediction': prediction, 'features': features})


@api_view(['GET'])
def dashboard_session_replay_view(request):
    session_id = request.query_params.get('session_id')
    sessions = UserSession.objects.order_by('-last_active_at')[:15]

    target_session = None
    if session_id:
        target_session = UserSession.objects.filter(session_id=session_id).first()
    if not target_session and sessions.exists():
        target_session = sessions.first()

    activities = []
    if target_session:
        activities = UserActivityLog.objects.filter(session=target_session).order_by('created_at')[:200]

    # Generate aggregate heatmap data
    heatmap_points = list(
        UserActivityLog.objects.filter(event_type__in=['click', 'dead_click'])
        .values('x', 'y', 'event_type', 'target_element')[:100]
    )

    dead_clicks_count = UserActivityLog.objects.filter(event_type='dead_click').count()
    total_clicks_count = UserActivityLog.objects.filter(event_type__in=['click', 'dead_click']).count()

    return Response({
        'sessions': UserSessionSerializer(sessions, many=True).data,
        'active_session_id': target_session.session_id if target_session else None,
        'activity_timeline': UserActivityLogSerializer(activities, many=True).data,
        'heatmap_data': heatmap_points,
        'click_analytics': {
            'total_clicks': total_clicks_count,
            'dead_clicks': dead_clicks_count,
            'dead_click_rate_pct': round((dead_clicks_count / max(1, total_clicks_count)) * 100, 1)
        }
    })


@api_view(['GET'])
def dashboard_browser_comparison_view(request):
    browsers = ['Chrome', 'Firefox', 'Edge', 'Safari']
    comparisons = []

    for b in browsers:
        sessions = UserSession.objects.filter(browser__iexact=b)
        session_ids = sessions.values_list('id', flat=True)

        avg_load = PerformanceMetric.objects.filter(session_id__in=session_ids).aggregate(v=Avg('page_load_time'))['v'] or (850.0 + random.randint(50, 400))
        avg_fcp = PerformanceMetric.objects.filter(session_id__in=session_ids).aggregate(v=Avg('fcp'))['v'] or (400.0 + random.randint(20, 200))
        avg_block = ThreadMetric.objects.filter(session_id__in=session_ids).aggregate(v=Avg('blocked_time'))['v'] or (35.0 + random.randint(5, 50))
        avg_heap = MemoryMetric.objects.filter(session_id__in=session_ids).aggregate(v=Avg('used_js_heap_size'))['v'] or (48.0 + random.randint(5, 30))
        err_count = ErrorLog.objects.filter(session_id__in=session_ids).count()

        # Score out of 100
        score = max(20, min(99, int(100 - (avg_load / 100) - (avg_block / 5) - (err_count * 2))))

        comparisons.append({
            'browser': b,
            'session_count': sessions.count(),
            'avg_load_time_ms': round(avg_load, 1),
            'avg_fcp_ms': round(avg_fcp, 1),
            'avg_thread_block_ms': round(avg_block, 1),
            'avg_heap_used_mb': round(avg_heap, 1),
            'total_errors': err_count,
            'performance_score': score
        })

    # Sort ranking by performance score descending
    comparisons.sort(key=lambda x: x['performance_score'], reverse=True)
    for rank, item in enumerate(comparisons, 1):
        item['rank'] = rank

    return Response({'comparisons': comparisons})


@api_view(['POST'])
def seed_demo_data_view(request):
    """Seed comprehensive realistic telemetry for interview demonstrations."""
    # Create or update sessions for multiple browsers
    browser_configs = [
        ('Chrome', '124.0', 'Linux', 'sess_chrome_enterprise'),
        ('Firefox', '125.0', 'Windows', 'sess_firefox_dev'),
        ('Edge', '123.0', 'Windows', 'sess_edge_workstation'),
        ('Safari', '17.4', 'macOS', 'sess_safari_macbook')
    ]

    for b, v, o, sid in browser_configs:
        session, _ = UserSession.objects.get_or_create(
            session_id=sid,
            defaults={
                'browser': b,
                'browser_version': v,
                'os': o,
                'device_type': 'Desktop',
                'user_agent': f"Mozilla/5.0 ({o}; {b}/{v})",
                'ip_address': '192.168.1.10'
            }
        )

        # Performance metrics
        load_time = random.uniform(800, 2400) if b != 'Chrome' else random.uniform(650, 1400)
        PerformanceMetric.objects.create(
            session=session,
            url='/dashboard/analytics',
            page_load_time=round(load_time, 1),
            fcp=round(load_time * 0.45, 1),
            dom_ready_time=round(load_time * 0.65, 1),
            ttfb=round(load_time * 0.22, 1),
            lcp=round(load_time * 0.78, 1)
        )

        # Thread metrics
        for _ in range(4):
            dur = random.uniform(40, 320)
            ThreadMetric.objects.create(
                session=session,
                metric_type='thread_block' if dur > 100 else 'long_task',
                blocked_time=round(dur, 1),
                freeze_duration=round(dur, 1),
                freeze_count=random.randint(1, 3),
                task_impact='High' if dur > 200 else 'Medium',
                details=f"Main thread heavy task iteration on {b}"
            )

        # Worker thread metrics
        worker_tasks = ['Matrix Determinant', 'Prime Factorization', 'Data Encryption', 'Heavy Filter Loop']
        for task in worker_tasks:
            WorkerThreadMetric.objects.create(
                session=session,
                thread_name=f"{b}-Worker-{random.randint(1, 4)}",
                task_type=task,
                execution_time=round(random.uniform(45, 210), 1),
                status='completed',
                queue_time=round(random.uniform(2, 12), 1)
            )

        # Memory metrics
        base_mem = random.uniform(35, 70)
        for i in range(5):
            growth = random.uniform(0.5, 4.5) * (i + 1)
            MemoryMetric.objects.create(
                session=session,
                total_js_heap_size=round(base_mem + growth + 20, 1),
                used_js_heap_size=round(base_mem + growth, 1),
                js_heap_size_limit=4096.0,
                growth_rate=round(growth, 2),
                potential_leak=growth > 12.0,
                leak_severity='High' if growth > 15.0 else ('Medium' if growth > 8.0 else 'None')
            )

        # Network metrics
        endpoints = [
            ('/api/v1/telemetry', 200, 45),
            ('/api/v1/auth/verify', 200, 80),
            ('/api/v1/reports/summary', 200, 320),
            ('/api/v1/ai/infer', 200, 640),
            ('/api/v1/stream/socket', 504, 1800),
            ('/api/v1/profile/sync', 403, 95)
        ]
        for url, code, dur in endpoints:
            NetworkMetric.objects.create(
                session=session,
                url=url,
                method='POST' if 'telemetry' in url or 'infer' in url else 'GET',
                status_code=code,
                request_time=0.0,
                response_time=float(dur),
                duration=float(dur),
                is_error=code >= 400
            )

        # Error logs
        errors_sample = [
            ("Uncaught TypeError", "Cannot read properties of undefined (reading 'calculateDelta')", "app.js:241:12"),
            ("Unhandled Rejection", "NetworkError: Failed to fetch streaming buffer chunk", "telemetry-stream.js:88:5"),
            ("DOM Exception", "CanvasRenderingContext2D: out of memory during composite", "chart-renderer.js:14:19")
        ]
        for err_title, err_msg, loc in errors_sample:
            ErrorLog.objects.create(
                session=session,
                error_type=err_title,
                message=err_msg,
                stack_trace=f"Error: {err_msg}\n    at RenderComponent ({loc})\n    at FiberReconcile (react-dom.js:1102)",
                url=f"/dashboard/{b.lower()}",
                browser=b,
                line_number=int(loc.split(':')[1]),
                col_number=int(loc.split(':')[2])
            )

        # User activity logs
        for _ in range(8):
            UserActivityLog.objects.create(
                session=session,
                event_type='click',
                x=round(random.uniform(15, 85), 1),
                y=round(random.uniform(20, 80), 1),
                target_element='BUTTON',
                target_text='Run Stress Test'
            )
        for _ in range(3):
            UserActivityLog.objects.create(
                session=session,
                event_type='dead_click',
                x=round(random.uniform(25, 75), 1),
                y=round(random.uniform(30, 70), 1),
                target_element='SPAN',
                target_text='Static Header Text'
            )

    broadcast_event('demo_data_seeded', {'message': 'Demonstration telemetry dataset populated successfully'})
    return Response({'status': 'seeded', 'message': 'Successfully seeded comprehensive multi-browser metrics dataset!'}, status=status.HTTP_201_CREATED)
