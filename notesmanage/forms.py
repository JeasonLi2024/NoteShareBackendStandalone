# from django import forms
# from .models import Note
# from django_ckeditor_5.widgets import CKEditor5Widget
#
#
# class NoteForm(forms.ModelForm):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields["body"].required = False
#
    # title = forms.CharField(label='文章标题', max_length=200, required=True,
    #                         widget=forms.TextInput(attrs={"placeholder": "在这里输入标题", 'style': 'width: 500px;'}), )
#     class Meta:
#         model = Note
#         fields = [
#             'title', 'content', 'file', 'category', 'is_private',
#             'is_pinned', 'cover_image', 'note_image', 'note_video', 'body'
#         ]
#         widgets = {
#             'body': CKEditor5Widget(
#             attrs={"class": "django_ckeditor_5"}, config_name="extends"
#         )
#
#     }
from django import forms

from django_ckeditor_5.widgets import CKEditor5Widget
from .models import Note


class CommentForm(forms.ModelForm):
      """Form for comments to the article."""

      def __init__(self, *args, **kwargs):
          super().__init__(*args, **kwargs)
          self.fields["body"].required = False

      title = forms.CharField(label='文章标题', max_length=200, required=True,
                              widget=forms.TextInput(
                                  attrs={"placeholder": "在这里输入标题", 'style': 'width: 500px;'}), )
      content = forms.CharField(label='内容概要', max_length=200, required=True,
                              widget=forms.TextInput(
                                  attrs={"placeholder": "在这里输入概要", 'style': 'width: 500px;'}), )
      class Meta:
          model = Note
          # fields = ("author", "body")
          fields = [
              'title', 'content', 'file', 'category', 'is_private',
              'is_pinned', 'cover_image', 'note_image', 'note_video', 'body'
          ]
          widgets = {
              "body": CKEditor5Widget(
                  attrs={"class": "django_ckeditor_5"}, config_name="extends"
              )
          }