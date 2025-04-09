from rest_framework.pagination import PageNumberPagination

class RootCommentPagination(PageNumberPagination):
    page_size = 5
    page_query_param = 'page'
    page_size_query_param = 'page_size'
    max_page_size = 100

class SubCommentPagination(PageNumberPagination):
    page_size = 5
    page_query_param = 'sub_page'
    page_size_query_param = 'sub_page_size'
    max_page_size = 20