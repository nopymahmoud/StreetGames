from django import forms
from django.core.exceptions import ValidationError
from .models import Partnership, PartnerAccount, PartnerPayment
from core.models import GameZone


class PartnershipForm(forms.ModelForm):
    """نموذج إدارة الشراكات"""
    
    class Meta:
        model = Partnership
        fields = ['zone', 'partner_name', 'partner_type', 'national_id', 'commercial_register',
                 'percentage', 'investment_amount', 'currency', 'start_date', 'end_date',
                 'share_expenses', 'expense_percentage', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'percentage': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100', 'class': 'form-control'}),
            'expense_percentage': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100', 'class': 'form-control'}),
            'investment_amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # تصفية المناطق حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            self.fields['zone'].queryset = user.userprofile.get_accessible_zones()

        # إضافة CSS classes
        for field_name, field in self.fields.items():
            if field_name == 'share_expenses':
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
    
    def clean_percentage(self):
        percentage = self.cleaned_data.get('percentage')
        if percentage and (percentage <= 0 or percentage > 100):
            raise ValidationError('يجب أن تكون النسبة بين 0 و 100')
        return percentage
    
    def clean_expense_percentage(self):
        expense_percentage = self.cleaned_data.get('expense_percentage')
        if expense_percentage and (expense_percentage < 0 or expense_percentage > 100):
            raise ValidationError('يجب أن تكون نسبة المصروفات بين 0 و 100')
        return expense_percentage
    
    def clean(self):
        cleaned_data = super().clean()
        zone = cleaned_data.get('zone')
        partner_name = cleaned_data.get('partner_name')
        
        # التحقق من عدم تكرار الشريك في نفس المنطقة
        if zone and partner_name:
            existing = Partnership.objects.filter(zone=zone, partner_name=partner_name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('يوجد شريك بنفس الاسم في هذه المنطقة')
        
        return cleaned_data


class PartnerPaymentForm(forms.ModelForm):
    """نموذج دفعات الشركاء"""

    class Meta:
        model = PartnerPayment
        fields = ['partnership', 'payment_date', 'amount', 'currency', 'payment_method',
                 'reference_number', 'notes']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'class': 'form-control'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # تصفية الشراكات حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            accessible_zones = user.userprofile.get_accessible_zones()
            self.fields['partnership'].queryset = Partnership.objects.filter(
                zone__in=accessible_zones,
                active=True
            ).select_related('zone')

        # قائمة العملات المسموحة
        from core.utils import get_supported_currencies
        self.fields['currency'] = forms.ChoiceField(
            choices=get_supported_currencies(),
            initial=self.instance.currency if self.instance and self.instance.pk else 'EGP',
            widget=forms.Select(attrs={'class': 'form-select'})
        )

        # إضافة CSS classes
        for name, field in self.fields.items():
            # أبقي الحقول select بحالتها
            if not isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs.update({'class': 'form-control'})

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise ValidationError('يجب أن يكون المبلغ أكبر من صفر')
        return amount


class PartnershipFilterForm(forms.Form):
    """نموذج تصفية الشراكات"""
    zone = forms.ModelChoiceField(
        queryset=GameZone.objects.filter(active=True),
        required=False,
        empty_label="جميع المناطق",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    partner_type = forms.ChoiceField(
        choices=[('', 'جميع الأنواع')] + Partnership.PARTNER_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    active = forms.ChoiceField(
        choices=[('', 'الكل'), ('true', 'نشط'), ('false', 'غير نشط')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # تصفية المناطق حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            self.fields['zone'].queryset = user.userprofile.get_accessible_zones()


class PartnerAccountFilterForm(forms.Form):
    """نموذج تصفية كشوف حسابات الشركاء"""
    partnership = forms.ModelChoiceField(
        queryset=Partnership.objects.filter(active=True),
        required=False,
        empty_label="جميع الشركاء",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    transaction_type = forms.ChoiceField(
        choices=[('', 'جميع الأنواع')] + PartnerAccount.TRANSACTION_TYPE_CHOICES,
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
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # تصفية الشراكات حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            accessible_zones = user.userprofile.get_accessible_zones()
            self.fields['partnership'].queryset = Partnership.objects.filter(
                zone__in=accessible_zones, 
                active=True
            ).select_related('zone')


class PartnerPaymentFilterForm(forms.Form):
    """نموذج تصفية دفعات الشركاء"""
    partnership = forms.ModelChoiceField(
        queryset=Partnership.objects.filter(active=True),
        required=False,
        empty_label="جميع الشركاء",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    payment_method = forms.ChoiceField(
        choices=[('', 'جميع الطرق')] + PartnerPayment.PAYMENT_METHOD_CHOICES,
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
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # تصفية الشراكات حسب صلاحيات المستخدم
        if user and hasattr(user, 'userprofile'):
            accessible_zones = user.userprofile.get_accessible_zones()
            self.fields['partnership'].queryset = Partnership.objects.filter(
                zone__in=accessible_zones, 
                active=True
            ).select_related('zone')
