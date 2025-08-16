from decimal import Decimal
import csv
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.forms import modelformset_factory
from django.http import HttpResponse

from .models import (
    Supplier, SupplierAccount,
    PurchaseBill, PurchaseBillLine,
    PurchaseReturn, PurchaseReturnLine,
    post_purchase_bill, unpost_purchase_bill,
    post_purchase_return, unpost_purchase_return,
)
from .forms import SupplierForm, PurchaseBillForm, PurchaseBillLineForm, PurchaseReturnForm, PurchaseReturnLineForm


# Suppliers
@login_required
def suppliers_list(request):
    suppliers = Supplier.objects.all().order_by('name')
    return render(request, 'purchases/suppliers_list.html', {'suppliers': suppliers})


@login_required
def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            sup = form.save(commit=False)
            sup.created_by = request.user
            sup.save()
            messages.success(request, 'تم إضافة المورد بنجاح')
            return redirect('purchases:suppliers_list')
    else:
        form = SupplierForm()
    return render(request, 'purchases/supplier_form.html', {'form': form})


@login_required
def supplier_edit(request, pk):
    sup = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=sup)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تعديل المورد بنجاح')
            return redirect('purchases:suppliers_list')
    else:
        form = SupplierForm(instance=sup)
    return render(request, 'purchases/supplier_form.html', {'form': form})


@login_required
def supplier_delete(request, pk):
    sup = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        sup.delete()
        messages.success(request, 'تم حذف المورد')
        return redirect('purchases:suppliers_list')
    return render(request, 'purchases/confirm_delete.html', {'object': sup, 'name': sup.name})


# Purchase Bills
@login_required
def bills_list(request):
    bills = PurchaseBill.objects.select_related('supplier').order_by('-bill_date', '-id')
    return render(request, 'purchases/bills_list.html', {'bills': bills})


@login_required
@transaction.atomic
def bill_create(request):
    LineFormSet = modelformset_factory(PurchaseBillLine, form=PurchaseBillLineForm, extra=2, can_delete=True)
    if request.method == 'POST':
        form = PurchaseBillForm(request.POST)
        formset = LineFormSet(request.POST, queryset=PurchaseBillLine.objects.none())
        if form.is_valid() and formset.is_valid():
            bill = form.save(commit=False)
            bill.created_by = request.user
            bill.save()
            for lf in formset.save(commit=False):
                lf.bill = bill
                lf.save()
            post_purchase_bill(bill, request.user)
            messages.success(request, 'تم إنشاء الفاتورة وترحيلها محاسبياً')
            return redirect('purchases:bills_list')
    else:
        form = PurchaseBillForm()
        formset = LineFormSet(queryset=PurchaseBillLine.objects.none())
    return render(request, 'purchases/bill_form.html', {'form': form, 'formset': formset})


@login_required
@transaction.atomic
def bill_edit(request, pk):
    bill = get_object_or_404(PurchaseBill, pk=pk)
    LineFormSet = modelformset_factory(PurchaseBillLine, form=PurchaseBillLineForm, extra=0, can_delete=True)
    if request.method == 'POST':
        form = PurchaseBillForm(request.POST, instance=bill)
        formset = LineFormSet(request.POST, queryset=PurchaseBillLine.objects.filter(bill=bill))
        if form.is_valid() and formset.is_valid():
            unpost_purchase_bill(bill)
            form.save()
            # احفظ السطور (إضافة/تعديل/حذف)
            instances = formset.save(commit=False)
            # علّم المحذوف
            for obj in formset.deleted_objects:
                obj.delete()
            for lf in instances:
                lf.bill = bill
                lf.save()
            post_purchase_bill(bill, request.user)
            messages.success(request, 'تم تعديل الفاتورة وإعادة ترحيلها')
            return redirect('purchases:bills_list')
    else:
        form = PurchaseBillForm(instance=bill)
        formset = LineFormSet(queryset=PurchaseBillLine.objects.filter(bill=bill))
    return render(request, 'purchases/bill_form.html', {'form': form, 'formset': formset, 'bill': bill})


@login_required
@transaction.atomic
def bill_delete(request, pk):
    bill = get_object_or_404(PurchaseBill, pk=pk)
    if request.method == 'POST':
        unpost_purchase_bill(bill)
        bill.delete()
        messages.success(request, 'تم حذف الفاتورة وإلغاء أثرها المحاسبي')
        return redirect('purchases:bills_list')
    return render(request, 'purchases/confirm_delete.html', {'object': bill, 'name': bill.bill_number})


# Purchase Returns
@login_required
def returns_list(request):
    rets = PurchaseReturn.objects.select_related('supplier').order_by('-return_date', '-id')
    return render(request, 'purchases/returns_list.html', {'returns': rets})


@login_required
@transaction.atomic
def return_create(request):
    LineFormSet = modelformset_factory(PurchaseReturnLine, form=PurchaseReturnLineForm, extra=2, can_delete=True)
    if request.method == 'POST':
        form = PurchaseReturnForm(request.POST)
        formset = LineFormSet(request.POST, queryset=PurchaseReturnLine.objects.none())
        if form.is_valid() and formset.is_valid():
            ret = form.save(commit=False)
            ret.created_by = request.user
            ret.save()
            for lf in formset.save(commit=False):
                lf.purchase_return = ret
                lf.save()
            post_purchase_return(ret, request.user)
            messages.success(request, 'تم إنشاء المرتجع وترحيله')
            return redirect('purchases:returns_list')
    else:
        form = PurchaseReturnForm()
        formset = LineFormSet(queryset=PurchaseReturnLine.objects.none())
    return render(request, 'purchases/return_form.html', {'form': form, 'formset': formset})


@login_required
@transaction.atomic
def return_edit(request, pk):
    ret = get_object_or_404(PurchaseReturn, pk=pk)
    LineFormSet = modelformset_factory(PurchaseReturnLine, form=PurchaseReturnLineForm, extra=0, can_delete=True)
    if request.method == 'POST':
        form = PurchaseReturnForm(request.POST, instance=ret)
        formset = LineFormSet(request.POST, queryset=PurchaseReturnLine.objects.filter(purchase_return=ret))
        if form.is_valid() and formset.is_valid():
            unpost_purchase_return(ret)
            form.save()
            for obj in formset.deleted_objects:
                obj.delete()
            for lf in formset.save(commit=False):
                lf.purchase_return = ret
                lf.save()
            post_purchase_return(ret, request.user)
            messages.success(request, 'تم تعديل المرتجع وإعادة ترحيله')
            return redirect('purchases:returns_list')
    else:
        form = PurchaseReturnForm(instance=ret)
        formset = LineFormSet(queryset=PurchaseReturnLine.objects.filter(purchase_return=ret))
    return render(request, 'purchases/return_form.html', {'form': form, 'formset': formset, 'ret': ret})


@login_required

@login_required
def supplier_payment_view(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount') or '0')
        currency = request.POST.get('currency') or 'EGP'
        note = request.POST.get('note') or ''
        from .payments import supplier_payment
        supplier_payment(supplier, amount, currency, request.user, note)
        messages.success(request, 'تم تسجيل سداد المورد وتحديث الخزينة وكشف الحساب')
        return redirect('purchases:supplier_ledger', pk=supplier.pk)
    return render(request, 'purchases/supplier_payment.html', {'supplier': supplier})


@login_required
def supplier_ledger_export(request, pk):
    sup = get_object_or_404(Supplier, pk=pk)
    entries = SupplierAccount.objects.filter(supplier=sup).order_by('trans_date', 'id')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="supplier_ledger_{sup.code}.csv"'
    writer = csv.writer(response)
    writer.writerow(['التاريخ','الوصف','مدين','دائن','العملة'])
    for e in entries:
        writer.writerow([e.trans_date, e.description, e.debit, e.credit, e.currency])
    return response

@transaction.atomic
def return_delete(request, pk):
    ret = get_object_or_404(PurchaseReturn, pk=pk)
    if request.method == 'POST':
        unpost_purchase_return(ret)
        ret.delete()
        messages.success(request, 'تم حذف المرتجع وإلغاء أثره المحاسبي')
        return redirect('purchases:returns_list')
    return render(request, 'purchases/confirm_delete.html', {'object': ret, 'name': ret.return_number})


# Supplier ledger
@login_required
def supplier_ledger(request, pk):
    sup = get_object_or_404(Supplier, pk=pk)
    entries = SupplierAccount.objects.filter(supplier=sup).order_by('trans_date', 'id')
    # احسب الرصيد التراكمي سريعاً للعرض فقط
    running = []
    bal = Decimal('0')
    for e in entries:
        bal = bal + (e.credit or 0) - (e.debit or 0)
        running.append((e, bal))
    return render(request, 'purchases/supplier_ledger.html', {'supplier': sup, 'entries': running})

