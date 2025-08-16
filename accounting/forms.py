from django import forms
from django.core.exceptions import ValidationError
from .models import DailyRevenue, ChartOfAccounts, JournalEntry
from .expense_models import Expense
from core.models import GameZone


class DailyRevenueForm(forms.ModelForm):
    """نموذج إدخال الإيرادات اليومية"""

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # العملات الموحدة
        try:
            from core.utils import get_supported_currencies
            self.fields['currency'].choices = get_supported_currencies()
        except Exception:
            self.fields['currency'].choices = [('EGP','جنيه مصري'), ('USD','دولار أمريكي'), ('EUR','يورو'), ('GBP','جنيه استرليني')]
        # تصفية المناطق حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            self.fields['zone'].queryset = user.userprofile.get_accessible_zones()

    class Meta:
        model = DailyRevenue
        fields = ['zone', 'date', 'amount', 'currency', 'payment_method', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # العملات الموحدة
        try:
            from core.utils import get_supported_currencies
            self.fields['currency'].choices = get_supported_currencies()
        except Exception:
            self.fields['currency'].choices = [('EGP','جنيه مصري'), ('USD','دولار أمريكي'), ('EUR','يورو'), ('GBP','جنيه استرليني')]

        # تصفية المناطق حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            self.fields['zone'].queryset = user.userprofile.get_accessible_zones()

        # إضافة CSS classes
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise ValidationError('يجب أن يكون المبلغ أكبر من صفر')
        return amount


class ExpenseForm(forms.ModelForm):
    """نموذج إدخال المصروفات"""
    
    class Meta:
        model = Expense
        fields = ['zone', 'date', 'category', 'description', 'amount', 'currency', 
                 'charge_partners', 'receipt_number', 'supplier', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'supplier': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # تحميل العملات ديناميكياً
        try:
            from core.utils import get_supported_currencies
            self.fields['currency'].choices = get_supported_currencies()
        except Exception:
            self.fields['currency'].choices = [('EGP','جنيه مصري'), ('USD','دولار أمريكي'), ('EUR','يورو'), ('GBP','جنيه استرليني')]

        # تصفية المناطق حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            self.fields['zone'].queryset = user.userprofile.get_accessible_zones()

        # إضافة CSS classes
        for field_name, field in self.fields.items():
            if field_name == 'charge_partners':
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise ValidationError('يجب أن يكون المبلغ أكبر من صفر')
        return amount


class ChartOfAccountsForm(forms.ModelForm):
    """نموذج إدارة دليل الحسابات"""
    
    class Meta:
        model = ChartOfAccounts
        fields = ['account_code', 'account_name', 'account_type', 'parent_account', 
                 'balance_type', 'opening_balance', 'currency', 'active']
        widgets = {
            'account_code': forms.TextInput(attrs={'class': 'form-control'}),
            'account_name': forms.TextInput(attrs={'class': 'form-control'}),
            'opening_balance': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # إضافة CSS classes
        for field_name, field in self.fields.items():
            if field_name == 'active':
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
    
    def clean_account_code(self):
        account_code = self.cleaned_data.get('account_code')
        if account_code:
            # التحقق من عدم تكرار رقم الحساب
            existing = ChartOfAccounts.objects.filter(account_code=account_code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('رقم الحساب موجود مسبقاً')
        return account_code


class RevenueFilterForm(forms.Form):
    """نموذج تصفية الإيرادات"""
    zone = forms.ModelChoiceField(
        queryset=GameZone.objects.filter(active=True),
        required=False,
        empty_label="جميع المناطق",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    currency = forms.ChoiceField(
        choices=[('', 'جميع العملات'), ('EGP', 'جنيه مصري'), ('USD', 'دولار أمريكي'), ('EUR', 'يورو')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # تصفية المناطق حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            self.fields['zone'].queryset = user.userprofile.get_accessible_zones()


class ExpenseFilterForm(forms.Form):
    """نموذج تصفية المصروفات"""
    zone = forms.ModelChoiceField(
        queryset=GameZone.objects.filter(active=True),
        required=False,
        empty_label="جميع المناطق",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    category = forms.ChoiceField(
        choices=[('', 'جميع الفئات')] + Expense.CATEGORY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    currency = forms.ChoiceField(
        choices=[('', 'جميع العملات'), ('EGP', 'جنيه مصري'), ('USD', 'دولار أمريكي'), ('EUR', 'يورو'), ('GBP', 'جنيه استرليني')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # تصفية المناطق حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            self.fields['zone'].queryset = user.userprofile.get_accessible_zones()
