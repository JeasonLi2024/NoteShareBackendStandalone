from django_filters import FilterSet, filters
from .models import User


class UserInfoFilter(FilterSet):
    name = filters.CharFilter(field_name='username', lookup_expr='icontains')

    class Meta:
        model = User
        fields = ('username',)