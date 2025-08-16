from django import forms
from .models import Hotel, GameZone, GameType, Warehouse


class HotelForm(forms.ModelForm):
    class Meta:
        model = Hotel
        fields = [
            'name', 'location', 'manager', 'active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'manager': forms.Select(attrs={'class': 'form-select'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class GameZoneForm(forms.ModelForm):
    class Meta:
        model = GameZone
        fields = [
            'hotel', 'name', 'code', 'area', 'monthly_rent', 'currency', 'manager',
            'active', 'opening_date', 'revenue_account', 'expense_account'
        ]
        widgets = {
            'hotel': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'monthly_rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency': forms.TextInput(attrs={'class': 'form-control'}),
            'manager': forms.Select(attrs={'class': 'form-select'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'opening_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'revenue_account': forms.TextInput(attrs={'class': 'form-control'}),
            'expense_account': forms.TextInput(attrs={'class': 'form-control'}),
        }


class GameTypeForm(forms.ModelForm):
    class Meta:
        model = GameType
        fields = [
            'name', 'code', 'category', 'active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = [
            'name', 'code', 'location', 'warehouse_type', 'manager', 'active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'warehouse_type': forms.Select(attrs={'class': 'form-select'}),
            'manager': forms.Select(attrs={'class': 'form-select'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

