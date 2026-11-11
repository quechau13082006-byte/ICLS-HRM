"""Form dùng chung của toàn dự án."""
from django import forms


class BootstrapForm(forms.Form):
    """Form tự gắn class Bootstrap cho từng ô nhập, và thêm `is-invalid` cho ô có lỗi.

    Nhờ vậy template chỉ cần vẽ từng trường bằng `core/_truong_form.html`,
    lỗi hiện ngay dưới trường (màu đỏ) theo đúng yêu cầu của §10.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for ten, truong in self.fields.items():
            widget = truong.widget
            if isinstance(widget, forms.CheckboxInput):
                kieu = 'form-check-input'
            elif isinstance(widget, forms.Select):
                kieu = 'form-select'
            else:
                kieu = 'form-control'
            widget.attrs['class'] = (widget.attrs.get('class', '') + ' ' + kieu).strip()

    def full_clean(self):
        super().full_clean()
        # Sau khi kiểm tra xong, đánh dấu ô nào có lỗi để Bootstrap tô đỏ
        for ten in self.errors:
            if ten in self.fields:
                self.fields[ten].widget.attrs['class'] += ' is-invalid'
