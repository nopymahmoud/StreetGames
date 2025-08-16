from django import forms
from .models import Supplier, PurchaseBill, PurchaseBillLine, PurchaseReturn, PurchaseReturnLine
from accounting.models import ChartOfAccounts


def _currency_choices():
    try:
        from core.utils import get_supported_currencies
        return get_supported_currencies()
    except Exception:
        return [('EGP','جنيه مصري'), ('USD','دولار أمريكي'), ('EUR','يورو'), ('GBP','جنيه استرليني')]


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name','code','phone','email','address','currency']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['currency'] = forms.ChoiceField(choices=_currency_choices())
        self.fields['currency'].widget.attrs.update({'class': 'form-select'})


class PurchaseBillLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseBillLine
        fields = ['account','description','qty','unit_price']


class PurchaseBillForm(forms.ModelForm):
    class Meta:
        model = PurchaseBill
        fields = ['zone','supplier','bill_number','bill_date','currency','tax_amount','other_costs','notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['currency'] = forms.ChoiceField(choices=_currency_choices())
        self.fields['currency'].widget.attrs.update({'class': 'form-select'})


class PurchaseReturnLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseReturnLine
        fields = ['account','description','qty','unit_price']


class PurchaseReturnForm(forms.ModelForm):
    class Meta:
        model = PurchaseReturn
        fields = ['zone','supplier','bill','return_number','return_date','currency']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['currency'] = forms.ChoiceField(choices=_currency_choices())
        self.fields['currency'].widget.attrs.update({'class': 'form-select'})

