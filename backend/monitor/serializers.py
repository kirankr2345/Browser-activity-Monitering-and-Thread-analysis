from rest_framework import serializers
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


class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = '__all__'


class PerformanceMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceMetric
        fields = '__all__'


class ThreadMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThreadMetric
        fields = '__all__'


class WorkerThreadMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerThreadMetric
        fields = '__all__'


class MemoryMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemoryMetric
        fields = '__all__'


class NetworkMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkMetric
        fields = '__all__'


class ErrorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorLog
        fields = '__all__'


class UserActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserActivityLog
        fields = '__all__'
